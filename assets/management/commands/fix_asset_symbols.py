"""Fix asset symbols that yfinance can no longer resolve.

Several tickers in the seed catalog get delisted or renamed over time, which
leaves them permanently stuck at a null price. This command remaps/removes the
known-bad symbols in the existing database.
"""

from django.core.management.base import BaseCommand

from assets.models import Asset

# Tickers yfinance can no longer resolve, mapped to their current replacement.
RENAMES = {
    "DISCA": {"symbol": "WBD", "yfinance_symbol": "WBD", "name": "Warner Bros. Discovery Inc."},
    "SQ": {"symbol": "XYZ", "yfinance_symbol": "XYZ", "name": "Block Inc."},
}

# Tickers that are redundant/dead and should be deactivated.
REMOVE = ["RDS-A"]


class Command(BaseCommand):
    help = "Remap/disable asset symbols that yfinance can no longer resolve."

    def handle(self, *args, **options):
        for old_sym, new in RENAMES.items():
            asset = Asset.objects.filter(yfinance_symbol=old_sym).first()
            if asset is None:
                self.stdout.write(f"  No asset found for {old_sym}")
                continue
            clash = Asset.objects.filter(yfinance_symbol=new["yfinance_symbol"]).exclude(pk=asset.pk).exists()
            if clash:
                self.stdout.write(self.style.WARNING(f"  {new['yfinance_symbol']} already exists; deactivating {old_sym}"))
                asset.is_active = False
                asset.save(update_fields=["is_active", "updated_at"])
                continue
            asset.symbol = new["symbol"]
            asset.yfinance_symbol = new["yfinance_symbol"]
            asset.name = new["name"]
            asset.is_active = True
            asset.save(update_fields=["symbol", "yfinance_symbol", "name", "is_active", "updated_at"])
            self.stdout.write(self.style.SUCCESS(f"  Remapped {old_sym} -> {new['yfinance_symbol']}"))

        for old_sym in REMOVE:
            asset = Asset.objects.filter(yfinance_symbol=old_sym).first()
            if asset is None:
                self.stdout.write(f"  No asset found for {old_sym}")
                continue
            asset.is_active = False
            asset.save(update_fields=["is_active", "updated_at"])
            self.stdout.write(self.style.SUCCESS(f"  Deactivated {old_sym}"))

        self.stdout.write(self.style.SUCCESS("\nDone fixing asset symbols."))
