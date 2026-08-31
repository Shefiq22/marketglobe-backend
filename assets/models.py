import yfinance as yf
from django.db import models


class Asset(models.Model):
    ASSET_CLASS_CHOICES = [
        ("stock", "Stock"),
        ("forex", "Forex"),
        ("crypto", "Crypto"),
    ]

    symbol = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        help_text="Display symbol (e.g. EUR/USD, AAPL, BTC)",
    )
    yfinance_symbol = models.CharField(
        max_length=30,
        unique=True,
        help_text="yfinance ticker (e.g. EURUSD=X, AAPL, BTC-USD)",
    )
    name = models.CharField(max_length=200)
    asset_class = models.CharField(max_length=10, choices=ASSET_CLASS_CHOICES, db_index=True)
    is_active = models.BooleanField(default=True)
    is_delisted = models.BooleanField(default=False)
    delisted_at = models.DateTimeField(null=True, blank=True)
    delisted_reason = models.TextField(blank=True, default="")
    last_price = models.DecimalField(max_digits=16, decimal_places=6, null=True, blank=True)
    last_change_pct = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "assets_asset"
        ordering = ["symbol"]

    def __str__(self):
        return f"{self.symbol} ({self.asset_class})"

    @staticmethod
    def validate_yfinance_symbol(ticker_symbol: str):
        """Validate a ticker against yfinance. Returns info dict or None."""
        try:
            ticker = yf.Ticker(ticker_symbol)
            info = ticker.fast_info
            if info is None or info.get("lastPrice", 0) == 0:
                return None
            return {"lastPrice": info.get("lastPrice"), "name": ticker_symbol}
        except Exception:
            return None

    @property
    def change_pct_display(self) -> str:
        if self.last_change_pct is not None:
            return f"{self.last_change_pct:+.2f}%"
        return "0.00%"


class PriceSnapshot(models.Model):
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="price_snapshots")
    price = models.DecimalField(max_digits=16, decimal_places=6)
    change_pct = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    snapshot_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "assets_price_snapshot"
        unique_together = ["asset", "snapshot_date"]
        ordering = ["-snapshot_date"]

    def __str__(self):
        return f"{self.asset.symbol} @ {self.snapshot_date}: {self.price}"
