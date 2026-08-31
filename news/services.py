import logging
from datetime import date, timedelta

import requests
import yfinance as yf
from django.conf import settings
from django.utils import timezone

from .models import AssetNews, EconomicEvent, MarketNews

logger = logging.getLogger(__name__)

FRED_SERIES = {
    "CPIAUCSL": ("Consumer Price Index for All Urban Consumers", "high"),
    "FEDFUNDS": ("Federal Funds Effective Rate", "high"),
    "UNRATE": ("Unemployment Rate", "high"),
    "GDPC1": ("Real Gross Domestic Product", "high"),
    "DGS10": ("10-Year Treasury Constant Maturity Rate", "medium"),
    "DGS2": ("2-Year Treasury Constant Maturity Rate", "medium"),
    "DGS30": ("30-Year Treasury Constant Maturity Rate", "low"),
    "T10Y2Y": ("10-Year minus 2-Year Treasury Spread", "medium"),
    "VIXCLS": ("CBOE Volatility Index (VIX)", "high"),
    "DXY": ("Trade Weighted U.S. Dollar Index", "medium"),
}


def fetch_fred_events(days_ahead: int = 30) -> int:
    """Fetch recent economic events from FRED API. Returns count of new events."""
    api_key = getattr(settings, "FRED_API_KEY", "")
    if not api_key:
        logger.info("FRED_API_KEY not set, skipping FRED fetch.")
        return 0

    count = 0
    end_date = date.today() + timedelta(days=days_ahead)
    start_date = date.today() - timedelta(days=7)

    for series_id, (title, importance) in FRED_SERIES.items():
        try:
            url = (
                f"https://api.stlouisfed.org/fred/series/observations"
                f"?series_id={series_id}"
                f"&api_key={api_key}"
                f"&file_type=json"
                f"&observation_start={start_date.isoformat()}"
                f"&observation_end={end_date.isoformat()}"
                f"&sort_order=desc"
                f"&limit=5"
            )
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            observations = data.get("observations", [])
            for obs in observations:
                if obs.get("value") == ".":
                    continue

                obs_date = date.fromisoformat(obs["date"])
                EconomicEvent.objects.update_or_create(
                    title=title,
                    event_date=obs_date,
                    defaults={
                        "category": series_id,
                        "importance": importance,
                        "actual_value": obs.get("value", ""),
                        "source": "FRED",
                        "source_url": f"https://fred.stlouisfed.org/series/{series_id}",
                    },
                )
                count += 1

        except Exception as e:
            logger.warning(f"FRED fetch failed for {series_id}: {e}")

    return count


def fetch_market_news(max_results: int = 20) -> int:
    """Fetch general market news from NewsAPI. Returns count of new articles."""
    api_key = getattr(settings, "NEWS_API_KEY", "")
    if not api_key:
        logger.info("NEWS_API_KEY not set, skipping news fetch.")
        return 0

    count = 0
    try:
        url = (
            f"https://newsapi.org/v2/top-headlines"
            f"?category=business"
            f"&language=en"
            f"&pageSize={max_results}"
            f"&apiKey={api_key}"
        )
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        articles = resp.json().get("articles", [])

        for article in articles:
            if not article.get("title") or article["title"] == "[Removed]":
                continue

            published = article.get("publishedAt", "")
            if published:
                from django.utils.dateparse import parse_datetime
                pub_dt = parse_datetime(published)
            else:
                pub_dt = timezone.now()

            MarketNews.objects.update_or_create(
                headline=article["title"],
                defaults={
                    "summary": article.get("description", ""),
                    "source_name": article.get("source", {}).get("name", ""),
                    "source_url": article.get("url", ""),
                    "published_at": pub_dt or timezone.now(),
                },
            )
            count += 1

    except Exception as e:
        logger.warning(f"NewsAPI fetch failed: {e}")

    return count


def fetch_asset_news(symbol: str, max_results: int = 10) -> int:
    """Fetch ticker-specific news using yfinance. Returns count of new articles."""
    from assets.models import Asset

    try:
        asset = Asset.objects.get(yfinance_symbol=symbol)
    except Asset.DoesNotExist:
        logger.warning(f"Asset {symbol} not found in DB.")
        return 0

    count = 0
    try:
        ticker = yf.Ticker(symbol)
        news_items = ticker.news or []

        for item in news_items[:max_results]:
            title = item.get("title", "")
            if not title:
                continue

            from django.utils.dateparse import parse_datetime

            pub_ts = item.get("providerPublishTime")
            if pub_ts:
                pub_dt = timezone.datetime.fromtimestamp(pub_ts, tz=timezone.utc)
            else:
                pub_dt = timezone.now()

            AssetNews.objects.update_or_create(
                asset=asset,
                headline=title,
                defaults={
                    "summary": item.get("summary", ""),
                    "source_name": item.get("publisher", ""),
                    "source_url": item.get("link", ""),
                    "published_at": pub_dt,
                },
            )
            count += 1

    except Exception as e:
        logger.warning(f"yfinance news fetch failed for {symbol}: {e}")

    return count


def refresh_all_news() -> dict:
    """Run all news fetchers. Returns summary dict."""
    return {
        "fred_events": fetch_fred_events(),
        "market_news": fetch_market_news(),
    }
