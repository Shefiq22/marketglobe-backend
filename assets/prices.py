"""Live price utilities shared by the refresh endpoint and management command."""

import logging
from datetime import date

import yfinance as yf
from django.utils import timezone

from .models import Asset, PriceSnapshot

logger = logging.getLogger(__name__)

# Fallback, in case a filter returns nothing to refresh.
DEFAULT_LOOKBACK_DAYS = 5


def fetch_live_price(ticker_symbol: str):
    """Return (last_price, change_pct) or None if the ticker has no data."""
    try:
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.fast_info
        if info is None or info.get("lastPrice", 0) == 0:
            return None
        hist = ticker.history(period="5d")
        if hist.empty:
            return None
        last_row = hist.iloc[-1]
        price = float(last_row["Close"])
        change_pct = 0.0
        if len(hist) >= 2:
            prev_close = float(hist.iloc[-2]["Close"])
            if prev_close:
                change_pct = ((price - prev_close) / prev_close) * 100
        return price, change_pct
    except Exception as e:  # noqa: BLE001
        logger.warning("Price fetch failed for %s: %s", ticker_symbol, e)
        return None


def refresh_asset_price(asset: Asset) -> bool:
    """Fetch a single asset's live price and persist it. Returns True on success."""
    snapshot = fetch_live_price(asset.yfinance_symbol)
    if snapshot is None:
        return False

    price, change_pct = snapshot
    PriceSnapshot.objects.update_or_create(
        asset=asset,
        snapshot_date=date.today(),
        defaults={
            "price": price,
            "change_pct": change_pct,
        },
    )
    Asset.objects.filter(pk=asset.pk).update(
        last_price=price,
        last_change_pct=change_pct,
    )
    asset.last_price = price
    asset.last_change_pct = change_pct
    return True


def refresh_prices(asset_id=None, asset_class=None, limit=None):
    """Refresh prices for active, non-delisted assets.

    Returns a dict with counts so callers can report progress.
    """
    queryset = Asset.objects.filter(is_active=True, is_delisted=False)

    if asset_id is not None:
        queryset = queryset.filter(id=asset_id)
    if asset_class:
        queryset = queryset.filter(asset_class=asset_class)
    if limit:
        queryset = queryset[: int(limit)]

    asset_ids = list(queryset.values_list("id", flat=True))
    success = 0
    failed = 0
    for asset_id in asset_ids:
        asset = Asset.objects.filter(pk=asset_id).first()
        if asset is None:
            continue
        if refresh_asset_price(asset):
            success += 1
        else:
            failed += 1

    return {"total": len(asset_ids), "success": success, "failed": failed}
