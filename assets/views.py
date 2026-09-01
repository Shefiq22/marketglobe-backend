from django_filters import rest_framework as filters
from rest_framework import generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .candles import TIMEFRAMES, DEFAULT_TIMEFRAME, fetch_candles
from .models import Asset
from .prices import refresh_prices, fetch_quotes
from .serializers import AssetCreateSerializer, AssetSerializer


class AssetFilter(filters.FilterSet):
    asset_class = filters.CharFilter(field_name="asset_class", lookup_expr="exact")
    is_active = filters.BooleanFilter(field_name="is_active")
    is_delisted = filters.BooleanFilter(field_name="is_delisted")

    class Meta:
        model = Asset
        fields = ["asset_class", "is_active", "is_delisted"]


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


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def refresh_prices_view(request):
    """POST /api/assets/refresh-prices/ — pull live prices from yfinance (auth required).

    Optional body: {"asset_id": id, "asset_class": "forex", "limit": n}
    """
    data = request.data or {}
    asset_id = data.get("asset_id")
    asset_class = data.get("asset_class")
    limit = data.get("limit")

    if asset_class not in (None, "stock", "forex", "crypto"):
        return Response(
            {"detail": "asset_class must be one of: stock, forex, crypto."},
            status=400,
        )

    try:
        result = refresh_prices(
            asset_id=int(asset_id) if asset_id is not None else None,
            asset_class=asset_class,
            limit=limit,
        )
    except (TypeError, ValueError):
        return Response({"detail": "Invalid parameters."}, status=400)
    except Exception as e:  # pragma: no cover
        return Response({"detail": f"Price refresh failed: {str(e)}"}, status=500)

    return Response(result)


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def asset_candles_view(request, pk):
    """GET /api/assets/<id>/candles/?timeframe=1D — real OHLCV history (public).

    Returns {symbol, timeframe, timeframes, candles: [...]}. The candles are
    ordered oldest -> newest, each with ts/open/high/low/close/volume.
    """
    asset = Asset.objects.filter(id=pk, is_active=True, is_delisted=False).first()
    if asset is None:
        return Response({"detail": "Asset not found."}, status=404)

    timeframe = request.query_params.get("timeframe", DEFAULT_TIMEFRAME)
    if timeframe not in TIMEFRAMES:
        return Response(
            {"detail": f"timeframe must be one of: {', '.join(TIMEFRAMES)}."},
            status=400,
        )

    candles = fetch_candles(asset.yfinance_symbol, timeframe, asset.asset_class)
    return Response(
        {
            "symbol": asset.symbol,
            "yfinance_symbol": asset.yfinance_symbol,
            "timeframe": timeframe,
            "last_price": asset.last_price,
            "last_change_pct": asset.last_change_pct,
            "candles": candles,
        }
    )


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def asset_quotes_view(request):
    """POST /api/assets/quotes/ — accurate live prices for a set of assets.

    Body: {"ids": [1,2,3]} (optional; empty -> all active assets).
    Returns {id: {"price": ..., "change_pct": ...}} for each asset priced.
    Crypto is quoted from CoinGecko (batched); stocks/forex from yfinance.
    Responses are served from a short-lived cache and every active asset gets a
    price + change_pct (stored snapshot fallback) so the app never shows blanks.
    """
    ids = (request.data or {}).get("ids") or []
    try:
        ids = [int(i) for i in ids]
    except (TypeError, ValueError):
        return Response({"detail": "ids must be a list of integers."}, status=400)

    queryset = Asset.objects.filter(is_active=True)
    if ids:
        queryset = queryset.filter(id__in=ids)

    # Cap the number of simultaneous upstream requests per call.
    assets = list(queryset[:200])
    quotes = fetch_quotes(assets)
    return Response(quotes)
