from django.conf import settings
from django.db import models


class AppNotification(models.Model):
    """A per-user in-app notification (e.g. a new market headline).

    Rows are materialized by the API from the latest market news the first
    time a user opens the notifications screen / checks the unread badge, so
    the dashboard bell shows exactly how many headlines the user has not read
    yet. ``source_ref`` makes materialization idempotent per user.
    """

    KIND_MARKET_NEWS = "market_news"
    KIND_CHOICES = [
        (KIND_MARKET_NEWS, "Market news"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="app_notifications",
    )
    kind = models.CharField(max_length=30, choices=KIND_CHOICES, default=KIND_MARKET_NEWS)
    title = models.CharField(max_length=500)
    body = models.TextField(blank=True, default="")
    source_ref = models.CharField(max_length=200, blank=True, default="")
    link_url = models.URLField(blank=True, default="")
    image_url = models.URLField(blank=True, default="")
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "notifications_appnotification"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "source_ref"],
                name="uniq_user_source_ref",
            )
        ]

    def __str__(self):
        return f"{self.user_id}: {self.title[:60]}"