from django.db import models
from django_filters import rest_framework as filters
from rest_framework import generics, permissions

from .models import Asset
from .serializers import AssetCreateSerializer, AssetSerializer


class AssetFilter(filters.FilterSet):
    asset_class = filters.CharFilter(field_name="asset_class", lookup_expr="exact")
    is_active = filters.BooleanFilter(field_name="is_active")
    is_delisted = filters.BooleanFilter(field_name="is_delisted")
    search = filters.CharFilter(method="filter_search")

    class Meta:
        model = Asset
        fields = ["asset_class", "is_active", "is_delisted"]

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            models.Q(symbol__icontains=value)
            | models.Q(name__icontains=value)
            | models.Q(yfinance_symbol__icontains=value)
        )


class AssetListView(generics.ListCreateAPIView):
    """
    GET  /api/assets/         — list all assets (public)
    POST /api/assets/         — create asset (auth required, validates against yfinance)
    """

    queryset = Asset.objects.all()
    serializer_class = AssetSerializer
    filterset_class = AssetFilter
    search_fields = ["symbol", "name", "yfinance_symbol"]
    ordering_fields = ["symbol", "asset_class", "last_price", "created_at"]

    def get_permissions(self):
        if self.request.method == "POST":
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return AssetCreateSerializer
        return AssetSerializer


class AssetDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/assets/<id>/   — asset detail (public)
    PUT    /api/assets/<id>/   — update asset (auth required)
    DELETE /api/assets/<id>/   — delete asset (auth required)
    """

    queryset = Asset.objects.all()
    serializer_class = AssetSerializer

    def get_permissions(self):
        if self.request.method in ("PUT", "PATCH", "DELETE"):
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]
