"""Binance market data provider for crypto assets.

Pulse Markets reads crypto live prices and candle history from the public
Binance REST API (no API key required). This gives users real-time prices that
match the actual spot market, rather than the delayed/aggregated quotes from
yfinance.

Stock and forex assets continue to use yfinance (see assets/prices.py).
"""

import logging
from datetime import datetime, timezone
from typing import Optional

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.binance.com/api/v3"

# yfinance crypto ticker -> Binance symbol base. We strip the "-USD" suffix and
# quote in USDT, which is Binance's deepest, most liquid market for these pairs.
# A few symbols have a Binance listing name that differs from the display name.
SYMBOL_ALIASES = {
    "MATIC": "POL",
}

# TradingView-style timeframe -> Binance kline interval.
KLINES_INTERVALS = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "4h": "4h",
    "1D": "1d",
    "1W": "1w",
    "1M": "1M",
    "3M": "3M",
}

# TradingView-style timeframe -> maximum number of candles Binance returns.
MAX_KLINES = {
    "1m": 1000,
    "5m": 1000,
    "15m": 1000,
    "30m": 1000,
    "1h": 1000,
    "4h": 1000,
    "1D": 1000,
    "1W": 1000,
    "1M": 1000,
    "3M": 1000,
}


def binance_symbol(yfinance_symbol: str) -> Optional[str]:
    """Convert a yfinance crypto ticker (e.g. ``BTC-USD``) to a Binance symbol
    (e.g. ``BTCUSDT``). Returns None if the ticker is not a supported crypto."""
    if not yfinance_symbol or not yfinance_symbol.upper().endswith("-USD"):
        return None
    base = yfinance_symbol[:-4].upper()  # strip "-USD"
    if not base:
        return None
    base = SYMBOL_ALIASES.get(base, base)
    return f"{base}USDT"


def _get(path: str, params=None, timeout: int = 15):
    resp = requests.get(f"{BASE_URL}{path}", params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def fetch_live_price(yfinance_symbol: str):
    """Return (last_price, change_pct) from Binance's 24hr ticker, or None on
    failure. ``change_pct`` is the 24-hour percent change reported by Binance."""
    symbol = binance_symbol(yfinance_symbol)
    if symbol is None:
        return None
    try:
        data = _get("/ticker/24hr", {"symbol": symbol})
        price = float(data.get("lastPrice", 0))
        if not price:
            return None
        change_pct_str = data.get("priceChangePercent", "0")
        try:
            change_pct = float(change_pct_str)
        except (TypeError, ValueError):
            change_pct = 0.0
        return price, change_pct
    except Exception as e:  # noqa: BLE001
        logger.warning("Binance price fetch failed for %s (%s): %s", symbol, yfinance_symbol, e)
        return None


def fetch_candles(yfinance_symbol: str, timeframe: str = "1D", max_bars: int = 1000) -> list:
    """Return Binance klines as candle dicts:
    {"ts": iso8601, "open":..., "high":..., "low":..., "close":..., "volume":...}
    Ordered oldest -> newest."""
    symbol = binance_symbol(yfinance_symbol)
    if symbol is None:
        return []
    interval = KLINES_INTERVALS.get(timeframe, "1d")
    if interval not in ("1d", "1w", "1M", "3M", "1h", "4h", "1m", "5m", "15m", "30m"):
        interval = "1d"

    try:
        data = _get("/klines", {"symbol": symbol, "interval": interval, "limit": max_bars})
    except Exception as e:  # noqa: BLE001
        logger.warning("Binance klines fetch failed for %s (%s): %s", symbol, timeframe, e)
        return []

    candles = []
    for row in data:
        try:
            candles.append(
                {
                    "ts": _iso_ms(int(row[0])),
                    "open": _num(row[1]),
                    "high": _num(row[2]),
                    "low": _num(row[3]),
                    "close": _num(row[4]),
                    "volume": _num(row[5]),
                }
            )
        except (IndexError, TypeError, ValueError):
            continue
    return candles


def _iso_ms(ms: int) -> str:
    try:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()
    except (OverflowError, OSError, ValueError):
        return str(ms)


def _num(v):
    try:
        f = float(v)
        if f != f:  # NaN
            return None
        return round(f, 8)
    except (TypeError, ValueError):
        return None
