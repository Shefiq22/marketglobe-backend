"""Live price utilities shared by the refresh endpoint and management command.

Price sources, chosen for what actually works on Render's datacenter IPs:

* All markets — stock, forex AND crypto — quote from yfinance ``download``
  (Yahoo's crumb-free chart endpoint) in small multi-ticker batches, so
  crypto (BTC-USD etc.) reports from the same source as stocks.
* Crypto that Yahoo cannot price falls back to CoinGecko, then Binance.

A 20-second in-memory cache backs ``fetch_quotes`` so the app's 4s polling keeps
prices visibly moving without hammering upstreams. Every asset
gets a value: if an upstream fetch fails we fall back to the stored snapshot so
a price and a percentage always reach the app.
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pandas as pd
import yfinance as yf

from . import coingecko
from .binance import fetch_live_price as _binance_live_price
from .models import Asset, PriceSnapshot

logger = logging.getLogger(__name__)

DEFAULT_LOOKBACK_DAYS = 5

# How long the in-memory quote cache stays fresh before the next upstream round.
QUOTE_CACHE_TTL_SECONDS = 20
# Max tickers per yfinance download call (keeps each call fast and friendly).
MAX_STOCK_BATCH = 25

_quote_cache = {"ts": 0.0, "data": {}}
_cache_lock = threading.Lock()


def fetch_live_price(ticker_symbol, asset_class=None):
    """Return (last_price, change_pct) or None if the ticker has no data.

    Stock, forex AND crypto all quote from yfinance — crypto tickers are
    mapped to their Yahoo pairs (e.g. BTC-USD) — so every market reports the
    same consistent source. Crypto falls back to CoinGecko, then Binance, only
    when Yahoo has no data for the ticker.
    """
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
            logger.debug(
                "History unavailable for %s, using fast_info price: %s", ticker_symbol, e
            )

        return price, change_pct
    except Exception as e:  # noqa: BLE001
        logger.debug("Yahoo price fetch failed for %s: %s", ticker_symbol, e)

    if asset_class == "crypto":
        quote = coingecko.fetch_quotes([ticker_symbol]).get(ticker_symbol)
        if quote and quote.get("price"):
            return quote["price"], quote.get("change_pct") or 0.0
        binance_snapshot = _binance_live_price(ticker_symbol)
        if binance_snapshot is not None:
            return binance_snapshot
        logger.debug(
            "CoinGecko/Binance had no data for %s either.", ticker_symbol
        )
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
    """Return accurate live quotes for the given assets keyed by asset id:
        {id: {"price": float, "change_pct": float}}

    Quotes are served from a 20s in-memory cache. Refreshes batch upstream calls
    (crypto = 1 CoinGecko request; stocks/forex = small yfinance batches), and
    every active asset is included — falling back to its stored snapshot when an
    upstream fetch fails — so the app always has a price and a percentage.
    """
    active = [a for a in assets if a.is_active and not a.is_delisted]
    if not active:
        return {}

    with _cache_lock:
        if time.time() - _quote_cache["ts"] > QUOTE_CACHE_TTL_SECONDS:
            try:
                _refresh_quote_cache(active)
            except Exception as e:  # noqa: BLE001
                logger.warning("Quote cache refresh failed: %s", e)
        data = _quote_cache["data"]
        return {a.pk: data[a.pk] for a in active if a.pk in data}


def _refresh_quote_cache(active):
    # Mark the cache fresh *before* fetching so concurrent pollers use the
    # previous data instead of triggering another upstream round.
    _quote_cache["ts"] = time.time()
    fresh = _bulk_quotes(active)
    if fresh:
        merged = dict(_quote_cache["data"])
        merged.update(fresh)
        _quote_cache["data"] = merged


def _bulk_quotes(active):
    """Quote every asset — stocks, forex AND crypto — from one source:

    yfinance batches (crypto tickers are Yahoo pairs like BTC-USD), so prices
    and change percentages are consistent across all markets. Crypto assets
    Yahoo cannot price fall back to CoinGecko, then the stored snapshot, so a
    value always reaches the app.
    """
    result = {}
    missing = []

    batches = [active[i : i + MAX_STOCK_BATCH] for i in range(0, len(active), MAX_STOCK_BATCH)]
    with ThreadPoolExecutor(
        max_workers=min(6, len(batches)), thread_name_prefix="quote"
    ) as pool:
        futures = {pool.submit(_fetch_yf_batch, batch): batch for batch in batches}
        for future, batch in futures.items():
            try:
                batch_quotes = future.result(timeout=45)
            except Exception as e:  # noqa: BLE001
                logger.warning("Quote batch failed: %s", e)
                batch_quotes = {}
            for asset in batch:
                quote = batch_quotes.get(asset.yfinance_symbol)
                if quote:
                    result[asset.pk] = _round_quote(quote)
                else:
                    missing.append(asset)

    crypto_missing = [a for a in missing if a.asset_class == "crypto"]
    if crypto_missing:
        try:
            quotes = coingecko.fetch_quotes([a.yfinance_symbol for a in crypto_missing])
        except Exception as e:  # noqa: BLE001
            logger.warning("CoinGecko fallback failed: %s", e)
            quotes = {}
        for asset in crypto_missing:
            quote = quotes.get(asset.yfinance_symbol)
            if quote:
                result[asset.pk] = _round_quote(quote)
                continue
            _stored_fallback(result, asset)

    for asset in missing:
        if asset.pk in result or asset.asset_class == "crypto":
            continue
        _stored_fallback(result, asset)

    return result


def _fetch_yf_batch(assets):
    """Fetch (price, change_pct) for a batch of stock/forex/crypto assets with a
    single yfinance ``download`` (uses Yahoo's crumb-free chart endpoint). Crypto
    symbols are already Yahoo pairs (BTC-USD) so they price in this same batch."""
    tickers = [a.yfinance_symbol for a in assets]
    out = {}
    try:
        frame = yf.download(
            " ".join(tickers),
            period="5d",
            interval="1d",
            group_by="ticker",
            threads=False,
            progress=False,
            auto_adjust=False,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("yfinance download failed for %s: %s", tickers[:3], e)
        return out

    if frame is None or frame.empty:
        return out

    multi = isinstance(frame.columns, pd.MultiIndex)
    for asset in assets:
        try:
            if multi:
                close = frame[asset.yfinance_symbol]["Close"]
            else:
                close = frame["Close"]
        except Exception:  # noqa: BLE001
            continue
        close = close.dropna()
        if close.empty:
            continue
        last = float(close.iloc[-1])
        prev = float(close.iloc[-2]) if len(close) >= 2 else last
        change = ((last - prev) / prev * 100) if prev else 0.0
        out[asset.yfinance_symbol] = {"price": last, "change_pct": change}
    return out


def _stored_fallback(result, asset):
    """Fall back to the stored snapshot so a price always reaches the app."""
    try:
        price = float(asset.last_price)
    except (TypeError, ValueError):
        price = None
    if not price:
        return
    try:
        change = float(asset.last_change_pct) if asset.last_change_pct is not None else 0.0
    except (TypeError, ValueError):
        change = 0.0
    result[asset.pk] = {"price": round(price, 6), "change_pct": round(change, 4)}


def _round_quote(quote):
    price = quote.get("price")
    change = quote.get("change_pct")
    try:
        price = round(float(price), 6)
    except (TypeError, ValueError):
        return quote
    try:
        change = round(float(change), 4)
    except (TypeError, ValueError):
        change = 0.0
    return {"price": price, "change_pct": change}