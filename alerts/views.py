import logging
from decimal import Decimal

from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Alert
from .serializers import AlertCreateSerializer, AlertSerializer

logger = logging.getLogger(__name__)


class AlertListView(generics.ListCreateAPIView):
    """GET/POST /api/alerts/"""

    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return AlertCreateSerializer
        return AlertSerializer

    def get_queryset(self):
        return Alert.objects.filter(user=self.request.user).select_related("asset")

    def perform_create(self, serializer):
        alert = serializer.save(user=self.request.user)
        # Return the full serialized alert to the client.
        self._created_alert = alert

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(
            AlertSerializer(self._created_alert).data,
            status=status.HTTP_201_CREATED,
        )


class AlertDetailView(generics.RetrieveDestroyAPIView):
    """PATCH (toggle active) / DELETE /api/alerts/{id}/"""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AlertSerializer

    def get_queryset(self):
        return Alert.objects.filter(user=self.request.user).select_related("asset")

    def patch(self, request, *args, **kwargs):
        alert = self.get_object()
        if "is_active" in request.data:
            alert.is_active = bool(request.data["is_active"])
            alert.save(update_fields=["is_active"])
        return Response(AlertSerializer(alert).data)

    def delete(self, request, *args, **kwargs):
        alert = self.get_object()
        alert.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AlertCheckView(APIView):
    """POST /api/alerts/check/

    Evaluates all active, untriggered alerts for the signed-in user against
    current asset prices and prediction confidence. Returns the list of alerts
    that just triggered so the frontend can notify the user.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from assets.models import Asset
        from predictions.models import Prediction

        active = Alert.objects.filter(
            user=request.user, is_active=True, triggered=False
        ).select_related("asset")

        if not active.exists():
            return Response({"triggered": [], "count": 0})

        asset_ids = list(active.values_list("asset_id", flat=True).distinct())
        assets = {a.id: a for a in Asset.objects.filter(id__in=asset_ids)}

        # Fetch latest predictions for these assets (1d horizon).
        predictions = {}
        for pred in Prediction.objects.filter(asset_id__in=asset_ids, horizon="1d"):
            predictions[pred.asset_id] = pred

        now = timezone.now()
        triggered = []

        for alert in active:
            asset = assets.get(alert.asset_id)
            if not asset:
                continue

            price = asset.last_price
            if price is None:
                continue

            price = Decimal(str(price))
            should_fire = False

            if alert.alert_type == "price_above" and price >= alert.target_value:
                should_fire = True
            elif alert.alert_type == "price_below" and price <= alert.target_value:
                should_fire = True
            elif alert.alert_type == "probability_above":
                pred = predictions.get(alert.asset_id)
                if pred:
                    confidence = Decimal(str(pred.confidence))
                    if confidence * 100 >= alert.target_value:
                        should_fire = True

            if should_fire:
                alert.triggered = True
                alert.triggered_at = now
                alert.save(update_fields=["triggered", "triggered_at"])
                triggered.append(AlertSerializer(alert).data)

        return Response({"triggered": triggered, "count": len(triggered)})
