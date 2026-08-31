from datetime import date, timedelta

from django_filters import rest_framework as filters
from rest_framework import generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .models import AssetNews, EconomicEvent, MarketNews
from .serializers import AssetNewsSerializer, EconomicEventSerializer, MarketNewsSerializer


class EconomicEventFilter(filters.FilterSet):
    importance = filters.CharFilter(field_name="importance")
    category = filters.CharFilter(field_name="category")
    date_from = filters.DateFilter(field_name="event_date", lookup_expr="gte")
    date_to = filters.DateFilter(field_name="event_date", lookup_expr="lte")

    class Meta:
        model = EconomicEvent
        fields = ["importance", "category", "event_date"]


class EconomicEventListView(generics.ListAPIView):
    """GET /api/news/events/ — economic calendar events (public)."""

    queryset = EconomicEvent.objects.all()
    serializer_class = EconomicEventSerializer
    filterset_class = EconomicEventFilter
    ordering_fields = ["event_date", "importance"]


class MarketNewsListView(generics.ListAPIView):
    """GET /api/news/market/ — general market news (public)."""

    queryset = MarketNews.objects.all()
    serializer_class = MarketNewsSerializer
    ordering_fields = ["published_at"]


class AssetNewsListView(generics.ListAPIView):
    """GET /api/news/asset/<asset_id>/ — news for a specific asset (public)."""

    serializer_class = AssetNewsSerializer
    ordering_fields = ["published_at"]

    def get_queryset(self):
        asset_id = self.kwargs.get("asset_id")
        return AssetNews.objects.filter(asset_id=asset_id)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def refresh_news(request):
    """POST /api/news/refresh/ — fetch latest news from external APIs (auth required)."""
    from .services import refresh_all_news

    try:
        result = refresh_all_news()
        return Response(
            {
                "detail": "News refreshed.",
                "fred_events_fetched": result["fred_events"],
                "market_news_fetched": result["market_news"],
            }
        )
    except Exception as e:
        return Response(
            {"detail": f"News refresh failed: {str(e)}"},
            status=500,
        )
