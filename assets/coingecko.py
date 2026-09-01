"""CoinGecko market data provider for crypto assets.

Binance geo-blocks US/EU datacenter IPs (HTTP 451) — which is exactly where
Render runs — and Yahoo's free finance API is increasingly walled off for cloud
IPs. Live crypto prices and candle history therefore come from the public
CoinGecko REST API (no key required). It supports batching many coins into a
single request, which keeps free-tier rate limits happy.
"""

import logging
import time

import pandas as pd
import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.coingecko.com/api/v3"

_TIME_MS = 64.0  # be generous with a single POLL; keep simple

# Asset.symbol (e.g. "BTC", "MATIC") -> CoinGecko coin id. These were verified
# against the /simple/price endpoint so the whole crypto list resolves.
COINGECKO_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "BNB": "binancecoin",
    "SOL": "solana",
    "XRP": "ripple",
    "ADA": "cardano",
    "DOGE": "dogecoin",
    "AVAX": "avalanche-2",
    "DOT": "polkadot",
    "LINK": "chainlink",
    "MATIC": "polygon-ecosystem-token",  # Polygon rebranded to POL
    "SHIB": "shiba-inu",
    "LTC": "litecoin",
    "UNI": "uniswap",
    "ATOM": "cosmos",
    "FIL": "filecoin",
    "APT": "aptos",
    "ARB": "arbitrum",
    "OP": "optimism",
    "NEAR": "near",
    "PEPE": "pepe",
    "SUI": "sui",
    "SEI": "sei-network",
    "INJ": "injective",
    "TIA": "celestia",
    "JUP": "jupiter-exchange-solana",
    "WIF": "dogwifcoin",
    "RENDER": "render-token",
    "FET": "fetch-ai",
    "GRT": "the-graph",
}

# TradingView-style timeframe -> CoinGecko data interval (kept coarse so free
# tier stays happy) and the resample rule used to build OHLC candles.
_CHART_INTERVAL = {
    "1m": "5m",
    "5m": "5m",
    "15m": "5m",
    "30m": "5m",
    "1h": "1h",
    "4h": "1h",
}
_CHART_DAYS = {
    "1m": 1,
    "5m": 1,
    "15m": 1,
    "30m": 1,
    "1h": 2,
    "4h": 8,
    "1D": 365,
    "1W": 365,
    "1M": 365,
    "3M": 365,
}
_RESAMPLE_RULES = {
    "1m": "5min",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "1h",
    "4h": "4h",
    "1D": "1D",
    "1W": "1W",
    "1M": "M",
    "3M": "3M",
}

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "PulseMarkets/1.0 (market data client)"})
_REQUEST_TIMEOUT = 15

# Cheap per-symbol candle cache: {key: (expires_ts, candles)}.
_candle_cache = {}
_CANDLE_CACHE_TTL = 120.0


def coingecko_id(yfinance_symbol):
    """Map a yfinance crypto ticker (``BTC-USD``) to a CoinGecko id, or None."""
    ticker = (yfinance_symbol or "").upper()
    if not ticker.endswith("-USD"):
        return None
    return COINGECKO_IDS.get(ticker[:-4])


def fetch_quotes(yfinance_symbols):
    """Return {yfinance_symbol: {"price": ..., "change_pct": ...}} for the given
    crypto tickers using ONE batched CoinGecko request.

    ``change_pct`` is CoinGecko's 24-hour percentage change. Unknown/missing
    coins are omitted so callers can fall back to stored prices.
    """
    ids, by_id = [], {}
    seen = set()
    for ticker in yfinance_symbols:
        cid = coingecko_id(ticker)
        if cid and cid not in seen:
            seen.add(cid)
            ids.append(cid)
            by_id[cid] = ticker
    if not ids:
        return {}

    try:
        resp = _SESSION.get(
            f"{BASE_URL}/simple/price",
            params={
                "ids": ",".join(ids),
                "vs_currencies": "usd",
                "include_24hr_change": "true",
            },
            timeout=_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
    except Exception as e:  # noqa: BLE001
        logger.warning("CoinGecko quote batch failed: %s", e)
        return {}

    data = resp.json() or {}
    out = {}
    for cid, ticker in by_id.items():
        row = data.get(cid)
        if not row:
            continue
        price = _num(row.get("usd"))
        if price is None:
            continue
        change = _num(row.get("usd_24h_change"))
        out[ticker] = {"price": round(price, 6), "change_pct": change if change is not None else 0.0}
    return out


def fetch_candles(yfinance_symbol, timeframe="1D", max_bars=1000):
    """Return CoinGecko candle dicts:
    {"ts": iso8601, "open":.., "high":.., "low":.., "close":.., "volume":..}
    Ordered oldest -> newest."""
    cid = coingecko_id(yfinance_symbol)
    if cid is None:
        return []
    timeframe = timeframe if timeframe in _CHART_DAYS else "1D"

    cache_key = f"{cid}:{timeframe}"
    cached = _candle_cache.get(cache_key)
    if cached and cached[0] > time.time():
        return cached[1]

    params = {"vs_currency": "usd", "days": _CHART_DAYS[timeframe]}
    interval = _CHART_INTERVAL.get(timeframe)
    if interval:
        params["interval"] = interval

    try:
        resp = _SESSION.get(
            f"{BASE_URL}/coins/{cid}/market_chart", params=params, timeout=_REQUEST_TIMEOUT
        )
        resp.raise_for_status()
    except Exception as e:  # noqa: BLE001
        logger.warning("CoinGecko candle fetch failed for %s: %s", yfinance_symbol, e)
        return []

    body = resp.json() or {}
    points = body.get("prices") or []
    if not points:
        return []

    df = pd.DataFrame(points, columns=["ts", "close"])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)

    volumes = None
    volumes_raw = body.get("total_volumes") or []
    if volumes_raw:
        vol_df = pd.DataFrame(volumes_raw, columns=["ts", "volume"])
        vol_df["ts"] = pd.to_datetime(vol_df["ts"], unit="ms", utc=True)
        volumes = vol_df.set_index("ts")["volume"]

    series = df.set_index("ts")["close"]
    rule = _RESAMPLE_RULES.get(timeframe, "1D")
    agg = series.resample(rule).ohlc().dropna()

    candles = []
    if agg.empty:
        for ts, price in points:
            candles.append(_candle(ts, price, price, price, price, None))
    else:
        vol_index = volumes if volumes is not None else None
        for idx, row in agg.iterrows():
            volume = None
            if vol_index is not None and not vol_index.empty:
                volume = _num(vol_index.asof(idx))
            candles.append(
                {
                    "ts": idx.isoformat(),
                    "open": _num(row["open"]),
                    "high": _num(row["high"]),
                    "low": _num(row["low"]),
                    "close": _num(row["close"]),
                    "volume": volume,
                }
            )

    if len(candles) > max_bars:
        candles = candles[-max_bars:]

    _candle_cache[cache_key] = (time.time() + _CANDLE_CACHE_TTL, candles)
    return candles


def _candle(ts, o, h, l, c, v):
    return {
        "ts": pd.to_datetime(ts, unit="ms", utc=True).isoformat(),
        "open": _num(o),
        "high": _num(h),
        "low": _num(l),
        "close": _num(c),
        "volume": _num(v) if v is not None else None,
    }


def _num(v):
    try:
        f = float(v)
        if f != f:  # NaN
            return None
        return round(f, 8)
    except (TypeError, ValueError):
        return None