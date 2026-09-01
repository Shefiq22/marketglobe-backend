"""Fetch real OHLCV candle history for the charting feature.

Stock and forex candles come from yfinance. Crypto candles come from CoinGecko
(Binance is geo-blocked on Render's datacenter IPs, so it only remains as a
fallback), which keeps the chart consistent with the CoinGecko live price.
"""

import logging

import yfinance as yf

from .binance import fetch_candles as _binance_candles
from . import coingecko

logger = logging.getLogger(__name__)

# TradingView-style timeframes -> (yfinance interval, lookback period, max bars)
TIMEFRAMES = {
    # intraday
    "1m": ("1m", "7d", 1000),
    "5m": ("5m", "30d", 1000),
    "15m": ("15m", "60d", 1000),
    "30m": ("30m", "60d", 1000),
    "1h": ("60m", "90d", 1000),
    "4h": ("60m", "90d", 800),
    # daily
    "1D": ("1d", "1y", 1000),
    "1W": ("1wk", "3y", 800),
    "1M": ("1mo", "10y", 800),
    "3M": ("3mo", "10y", 800),
}

DEFAULT_TIMEFRAME = "1D"


def fetch_candles(ticker_symbol: str, timeframe: str = DEFAULT_TIMEFRAME, asset_class=None) -> list:
    """Return a list of candle dicts:
    {"ts": iso8601, "open":..., "high":..., "low":..., "close":..., "volume":...}
    Ordered oldest -> newest.

    Crypto assets use CoinGecko history (Binance fallback) so the chart matches
    the live CoinGecko price. Stock and forex assets use yfinance history.
    """
    if timeframe not in TIMEFRAMES:
        timeframe = DEFAULT_TIMEFRAME
    interval, period, max_bars = TIMEFRAMES[timeframe]

    if asset_class == "crypto":
        candles = coingecko.fetch_candles(ticker_symbol, timeframe, max_bars)
        if candles:
            return candles
        return _binance_candles(ticker_symbol, timeframe, max_bars)

    try:
        df = yf.Ticker(ticker_symbol).history(period=period, interval=interval, auto_adjust=True)
    except Exception as e:  # noqa: BLE001
        logger.warning("Candle fetch failed for %s (%s): %s", ticker_symbol, timeframe, e)
        return []

    if df is None or df.empty:
        return []

    # 4h is approximated by resampling 60m data daily into 4h buckets.
    if timeframe == "4h":
        df = df.resample("4h").agg(
            {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
        ).dropna()

    candles = []
    for idx, row in df.iterrows():
        candles.append(
            {
                "ts": _iso(idx),
                "open": _num(row.get("Open")),
                "high": _num(row.get("High")),
                "low": _num(row.get("Low")),
                "close": _num(row.get("Close")),
                "volume": _num(row.get("Volume")),
            }
        )

    if len(candles) > max_bars:
        candles = candles[-max_bars:]
    return candles


def _iso(idx):
    if hasattr(idx, "tz_localize") and idx.tzinfo is None:
        try:
            idx = idx.tz_localize("UTC")
        except Exception:  # noqa: BLE001
            pass
    try:
        return idx.isoformat()
    except Exception:  # noqa: BLE001
        return str(idx)


def _num(v):
    try:
        f = float(v)
        if f != f:  # NaN
            return None
        return round(f, 8)
    except (TypeError, ValueError):
        return None
