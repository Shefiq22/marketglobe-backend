from django.conf import settings
from django.db import models


class Watchlist(models.Model):
    """User-specific list of tracked assets."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="watchlists",
    )
    name = models.CharField(max_length=100, default="My Watchlist")
    assets = models.ManyToManyField("assets.Asset", blank=True, related_name="watchlists")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "watchlist_watchlist"
        unique_together = ["user", "name"]
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.user.username} — {self.name} ({self.assets.count()} assets)"

    @property
    def asset_count(self):
        return self.assets.count()


class WatchlistItem(models.Model):
    """Individual item in a watchlist with optional user notes."""

    watchlist = models.ForeignKey(Watchlist, on_delete=models.CASCADE, related_name="items")
    asset = models.ForeignKey("assets.Asset", on_delete=models.CASCADE)
    notes = models.TextField(blank=True, default="")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "watchlist_item"
        unique_together = ["watchlist", "asset"]
        ordering = ["-added_at"]

    def __str__(self):
        return f"{self.watchlist.name}: {self.asset.symbol}"
