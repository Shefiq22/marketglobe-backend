import logging
from datetime import date, timedelta

import yfinance as yf
from django.core.management.base import BaseCommand
from django.utils import timezone

from assets.models import Asset, PriceSnapshot
from predictions.models import Prediction

logger = logging.getLogger(__name__)

HORIZONS = ["1d", "5d", "1mo", "3mo", "1y"]


class Command(BaseCommand):
    help = (
        "Refresh predictions for all active, non-delisted assets. "
        "Also detects delisted assets and updates price snapshots."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print actions without saving.",
        )
        parser.add_argument(
            "--asset-id",
            type=int,
            help="Refresh only this specific asset.",
        )
        parser.add_argument(
            "--horizon",
            type=str,
            choices=HORIZONS,
            help="Refresh only this horizon (default: all).",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        asset_id = options.get("asset_id")
        horizon_filter = options.get("horizon")

        if asset_id:
            assets = Asset.objects.filter(id=asset_id, is_active=True)
        else:
            assets = Asset.objects.filter(is_active=True, is_delisted=False)

        self.stdout.write(f"Refreshing predictions for {assets.count()} assets...")

        success_count = 0
        fail_count = 0
        delist_count = 0

        for asset in assets:
            # ── Delisting detection ──────────────────────────────────────────
            try:
                ticker = yf.Ticker(asset.yfinance_symbol)
                info = ticker.fast_info
                if info is None or info.get("lastPrice", 0) == 0:
                    self.stdout.write(
                        self.style.WARNING(f"  DELISTED: {asset.symbol} ({asset.yfinance_symbol})")
                    )
                    if not dry_run:
                        asset.is_delisted = True
                        asset.delisted_at = timezone.now()
                        asset.delisted_reason = "Ticker returned no data from yfinance"
                        asset.save()
                    delist_count += 1
                    continue
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f"  ERROR validating {asset.symbol}: {e}")
                )
                fail_count += 1
                continue

            # ── Update price snapshot ────────────────────────────────────────
            if not dry_run:
                try:
                    hist = ticker.history(period="5d")
                    if not hist.empty:
                        last_row = hist.iloc[-1]
                        price = float(last_row["Close"])
                        if len(hist) >= 2:
                            prev_close = float(hist.iloc[-2]["Close"])
                            change_pct = ((price - prev_close) / prev_close) * 100
                        else:
                            change_pct = 0.0

                        PriceSnapshot.objects.update_or_create(
                            asset=asset,
                            snapshot_date=date.today(),
                            defaults={
                                "price": price,
                                "change_pct": change_pct,
                            },
                        )
                        asset.last_price = price
                        asset.last_change_pct = change_pct
                        asset.save(update_fields=["last_price", "last_change_pct"])
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f"  Price snapshot failed for {asset.symbol}: {e}")
                    )

            # ── Run predictions for each horizon ─────────────────────────────
            horizons = [horizon_filter] if horizon_filter else HORIZONS
            for horizon in horizons:
                try:
                    from ml.predict import predict

                    result = predict(asset.yfinance_symbol, horizon=horizon)

                    if not dry_run:
                        Prediction.objects.update_or_create(
                            asset=asset,
                            horizon=horizon,
                            defaults={
                                "probability_up": result["probability_up"],
                                "probability_down": result["probability_down"],
                                "has_clear_signal": result["has_clear_signal"],
                                "call": result["call"],
                                "last_close": result.get("last_close"),
                                "as_of_date": result.get("as_of_date"),
                                "indicators": result.get("indicators", {}),
                                "features_used": result.get("features_used", []),
                                "summary": result.get("summary", ""),
                            },
                        )

                    self.stdout.write(
                        f"  OK: {asset.symbol} {horizon} → {result['call']} "
                        f"(UP={result['probability_up']:.2%})"
                    )
                    success_count += 1

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"  FAIL: {asset.symbol} {horizon}: {e}")
                    )
                    fail_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone! Predictions: {success_count} OK, {fail_count} failed. "
                f"Delisted: {delist_count}"
            )
        )
