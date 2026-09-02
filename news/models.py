from django.db import models


class EconomicEvent(models.Model):
    """FRED-sourced economic calendar events (CPI, Fed funds rate, etc.)."""

    IMPORTANCE_CHOICES = [
        ("high", "High"),
        ("medium", "Medium"),
        ("low", "Low"),
    ]

    title = models.CharField(max_length=300)
    description = models.TextField(blank=True, default="")
    category = models.CharField(max_length=100, blank=True, default="")
    currency = models.CharField(max_length=10, blank=True, default="")
    importance = models.CharField(max_length=10, choices=IMPORTANCE_CHOICES, default="medium")
    event_date = models.DateField(db_index=True)
    actual_value = models.CharField(max_length=100, blank=True, default="")
    forecast_value = models.CharField(max_length=100, blank=True, default="")
    previous_value = models.CharField(max_length=100, blank=True, default="")
    source = models.CharField(max_length=50, default="FRED")
    source_url = models.URLField(blank=True, default="")
    fetched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "news_economic_event"
        ordering = ["-event_date", "-importance"]

    def __str__(self):
        return f"[{self.importance}] {self.title} @ {self.event_date}"


class MarketNews(models.Model):
    """General market news headlines (NewsAPI or yfinance-sourced)."""

    headline = models.CharField(max_length=500)
    summary = models.TextField(blank=True, default="")
    source_name = models.CharField(max_length=200, blank=True, default="")
    source_url = models.URLField(blank=True, default="")
    image_url = models.URLField(blank=True, default="")
    related_symbols = models.JSONField(default=list, blank=True)
    sentiment = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text="positive/negative/neutral or empty if unknown",
    )
    published_at = models.DateTimeField(db_index=True)
    fetched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "news_market_news"
        ordering = ["-published_at"]

    def __str__(self):
        return self.headline[:80]


class AssetNews(models.Model):
    """Ticker-specific news mapped to assets."""

    asset = models.ForeignKey(
        "assets.Asset", on_delete=models.CASCADE, related_name="news_items"
    )
    headline = models.CharField(max_length=500)
    summary = models.TextField(blank=True, default="")
    source_name = models.CharField(max_length=200, blank=True, default="")
    source_url = models.URLField(blank=True, default="")
    sentiment = models.CharField(max_length=20, blank=True, default="")
    published_at = models.DateTimeField(db_index=True)
    fetched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "news_asset_news"
        ordering = ["-published_at"]

    def __str__(self):
        return f"{self.asset.symbol}: {self.headline[:60]}"
