import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Refresh market news (and optional economic events / asset news) from external sources."

    def add_arguments(self, parser):
        parser.add_argument(
            "--market-only",
            action="store_true",
            help="Only fetch market news (skip FRED events and per-asset news).",
        )
        parser.add_argument(
            "--max-news",
            type=int,
            default=20,
            help="Maximum market news articles to fetch.",
        )

    def handle(self, *args, **options):
        from news.services import (
            fetch_asset_news,
            fetch_fred_events,
            fetch_market_news,
            fetch_xoomar_events,
        )

        max_news = options["max_news"]

        market = fetch_market_news(max_results=max_news)
        self.stdout.write(self.style.SUCCESS(f"Market news fetched: {market}"))

        if options["market_only"]:
            return

        fred = fetch_fred_events()
        self.stdout.write(self.style.SUCCESS(f"Economic events fetched: {fred}"))

        xoomar = fetch_xoomar_events()
        self.stdout.write(self.style.SUCCESS(f"Xoomar economic events fetched: {xoomar}"))

        # Fetch per-asset news for a handful of the most relevant assets.
        from assets.models import Asset

        symbols = ["AAPL", "MSFT", "TSLA", "NVDA", "BTC-USD", "ETH-USD", "EURUSD=X"]
        total = 0
        for symbol in symbols:
            try:
                total += fetch_asset_news(symbol)
            except Exception as e:  # pragma: no cover
                logger.warning(f"asset news failed for {symbol}: {e}")
        self.stdout.write(self.style.SUCCESS(f"Asset news fetched: {total}"))
