from django_filters import rest_framework as filters
from rest_framework import generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from assets.models import Asset

from .models import ModelMetric, Prediction
from .serializers import ModelMetricSerializer, PredictionSerializer


class PredictionFilter(filters.FilterSet):
    asset = filters.NumberFilter(field_name="asset_id")
    asset_class = filters.CharFilter(field_name="asset__asset_class")
    horizon = filters.CharFilter(field_name="horizon")
    has_clear_signal = filters.BooleanFilter(field_name="has_clear_signal")
    call = filters.CharFilter(field_name="call")

    class Meta:
        model = Prediction
        fields = ["asset", "asset_class", "horizon", "has_clear_signal", "call"]


class PredictionListView(generics.ListAPIView):
    """GET /api/predictions/ — list all predictions (public)."""

    queryset = Prediction.objects.select_related("asset").all()
    serializer_class = PredictionSerializer
    filterset_class = PredictionFilter
    ordering_fields = ["as_of_date", "probability_up", "created_at"]


class PredictionDetailView(generics.RetrieveAPIView):
    """GET /api/predictions/<id>/ — single prediction detail (public)."""

    queryset = Prediction.objects.select_related("asset").all()
    serializer_class = PredictionSerializer


class ModelMetricListView(generics.ListAPIView):
    """GET /api/predictions/metrics/ — model performance metrics (public)."""

    queryset = ModelMetric.objects.all()
    serializer_class = ModelMetricSerializer
    ordering_fields = ["measured_at", "metric_value"]


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def refresh_prediction(request, asset_id):
    """POST /api/predictions/refresh/<asset_id>/ — run prediction on-demand (auth required)."""
    try:
        asset = Asset.objects.get(id=asset_id, is_active=True, is_delisted=False)
    except Asset.DoesNotExist:
        return Response(
            {"detail": "Asset not found or is delisted."},
            status=404,
        )

    from ml.predict import predict

    horizon = request.data.get("horizon", "5d")
    try:
        result = predict(asset.yfinance_symbol, horizon=horizon)
    except Exception as e:
        return Response(
            {"detail": f"Prediction failed: {str(e)}"},
            status=500,
        )

    # Save or update the prediction
    prediction, created = Prediction.objects.update_or_create(
        asset=asset,
        horizon=horizon,
        defaults={
            "probability_up": result["probability_up"],
            "probability_down": result["probability_down"],
            "has_clear_signal": result["has_clear_signal"],
            "call": result["call"],
            "last_close": result.get("last_close"),
            "as_of_date": result.get("as_of_date"),
            "indicators": result.get("indicators", {}),
            "features_used": result.get("features_used", []),
            "summary": result.get("summary", ""),
        },
    )

    return Response(
        {
            "detail": "Prediction refreshed.",
            "prediction": PredictionSerializer(prediction).data,
        }
    )
