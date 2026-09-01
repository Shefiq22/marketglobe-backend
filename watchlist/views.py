from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Watchlist, WatchlistItem
from .serializers import (
    WatchlistCreateSerializer,
    WatchlistItemCreateSerializer,
    WatchlistItemSerializer,
    WatchlistSerializer,
)


class WatchlistListView(generics.ListCreateAPIView):
    """
    GET  /api/watchlist/          — list user's watchlists (auth required)
    POST /api/watchlist/          — create watchlist (auth required)
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = WatchlistSerializer

    def get_queryset(self):
        return Watchlist.objects.filter(user=self.request.user).prefetch_related(
            "items__asset"
        )

    def get_serializer_class(self):
        if self.request.method == "POST":
            return WatchlistCreateSerializer
        return WatchlistSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class WatchlistDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/watchlist/<id>/   — watchlist detail (auth required, owner only)
    PUT    /api/watchlist/<id>/   — update watchlist name (auth required, owner only)
    DELETE /api/watchlist/<id>/   — delete watchlist (auth required, owner only)
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = WatchlistSerializer

    def get_queryset(self):
        return Watchlist.objects.filter(user=self.request.user).prefetch_related(
            "items__asset"
        )


class WatchlistAddAssetView(APIView):
    """POST /api/watchlist/<id>/add/ — add asset to watchlist (auth required, owner only)."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            watchlist = Watchlist.objects.get(id=pk, user=request.user)
        except Watchlist.DoesNotExist:
            return Response({"detail": "Watchlist not found."}, status=404)

        serializer = WatchlistItemCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        item, created = WatchlistItem.objects.get_or_create(
            watchlist=watchlist,
            asset=serializer.validated_data["asset"],
            defaults={"notes": serializer.validated_data.get("notes", "")},
        )

        if not created:
            return Response(
                WatchlistItemSerializer(item).data,
                status=status.HTTP_200_OK,
            )

        return Response(
            WatchlistItemSerializer(item).data,
            status=status.HTTP_201_CREATED,
        )


class WatchlistRemoveAssetView(APIView):
    """DELETE /api/watchlist/<id>/remove/<asset_id>/ — remove asset from watchlist."""

    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, pk, asset_id):
        try:
            watchlist = Watchlist.objects.get(id=pk, user=request.user)
        except Watchlist.DoesNotExist:
            return Response({"detail": "Watchlist not found."}, status=404)

        deleted_count, _ = WatchlistItem.objects.filter(
            watchlist=watchlist, asset_id=asset_id
        ).delete()

        if deleted_count == 0:
            return Response({"detail": "Asset not in this watchlist."}, status=404)

        return Response(status=204)
