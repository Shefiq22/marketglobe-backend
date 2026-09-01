"""Live price utilities shared by the refresh endpoint and management command."""

import logging
from datetime import date

import yfinance as yf
from django.utils import timezone

from .binance import fetch_live_price as _binance_live_price
from .models import Asset, PriceSnapshot

logger = logging.getLogger(__name__)

# Fallback, in case a filter returns nothing to refresh.
DEFAULT_LOOKBACK_DAYS = 5


def fetch_live_price(ticker_symbol, asset_class=None):
    """Return (last_price, change_pct) or None if the ticker has no data.

    Crypto assets are sourced from Binance (real-time spot prices). Stock and
    forex assets keep using yfinance. Falls back to yfinance for crypto when
    Binance has no data for the ticker.
    """
    if asset_class == "crypto":
        binance_snapshot = _binance_live_price(ticker_symbol)
        if binance_snapshot is not None:
            return binance_snapshot
        logger.debug("Binance had no data for %s; falling back to yfinance.", ticker_symbol)

    try:
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.fast_info
        if info is None:
            return None
        last_price = info.get("lastPrice", 0)
        if not last_price:
            return None

        price = float(last_price)
        change_pct = 0.0
        try:
            hist = ticker.history(period="5d")
            if not hist.empty:
                last_row = hist.iloc[-1]
                close = float(last_row["Close"])
                if close:
                    price = close
                if len(hist) >= 2:
                    prev_close = float(hist.iloc[-2]["Close"])
                    if prev_close:
                        change_pct = ((price - prev_close) / prev_close) * 100
        except Exception as e:  # noqa: BLE001
            logger.debug("History unavailable for %s, using fast_info price: %s", ticker_symbol, e)

        return price, change_pct
    except Exception as e:  # noqa: BLE001
        logger.warning("Price fetch failed for %s: %s", ticker_symbol, e)
        return None


def refresh_asset_price(asset: Asset) -> bool:
    """Fetch a single asset's live price and persist it. Returns True on success."""
    snapshot = fetch_live_price(asset.yfinance_symbol, asset.asset_class)
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


def fetch_quotes(assets) -> dict:
    """Return accurate live quotes for the given assets keyed by asset id.

    Fetching a live quote for every asset on every list render is expensive, so
    this is exposed as a dedicated endpoint the app calls to overlay fresh
    prices on top of the (possibly cached) asset list. For each asset we return:

        {id: {"price": float, "change_pct": float|None}}

    Assets that fail to quote (or that are not active) are omitted, so the
    consumer can fall back to the stored snapshot price for those.
    """
    quotes = {}
    for asset in assets:
        if not asset.is_active or asset.is_delisted:
            continue
        price, change_pct = _quote(asset)
        if price is not None:
            quotes[asset.pk] = {"price": price, "change_pct": change_pct}
    return quotes


def _quote(asset: Asset):
    """Best-effort live quote for a single asset; returns (price, change_pct)
    or (None, None). Crypto uses Binance; stocks/forex use yfinance fast_info."""
    try:
        snapshot = fetch_live_price(asset.yfinance_symbol, asset.asset_class)
    except Exception as e:  # noqa: BLE001
        logger.warning("Quote fetch failed for %s: %s", asset.symbol, e)
        return None, None
    if snapshot is None:
        return None, None
    return snapshot
