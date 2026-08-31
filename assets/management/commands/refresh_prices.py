import logging

from django.core.management.base import BaseCommand

from assets.prices import refresh_prices

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Refresh live prices for all active, non-delisted assets from yfinance."

    def add_arguments(self, parser):
        parser.add_argument("--asset-id", type=int, help="Refresh only this specific asset.")
        parser.add_argument(
            "--asset-class",
            type=str,
            choices=["stock", "forex", "crypto"],
            help="Refresh only this asset class.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Only refresh the first N assets (useful for quick tests).",
        )

    def handle(self, *args, **options):
        result = refresh_prices(
            asset_id=options["asset_id"],
            asset_class=options.get("asset_class"),
            limit=options["limit"],
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Price refresh done: {result['success']} updated, "
                f"{result['failed']} failed, {result['total']} total."
            )
        )
