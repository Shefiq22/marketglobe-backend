from datetime import timedelta

from django.utils import timezone

from news.models import MarketNews

from .models import AppNotification

# How many of the latest headlines are materialized into a user's notifications
# list the first time they look (keeps the initial badge count sensible).
MATERIALIZE_TOP = 20


def materialize_news(user) -> int:
    """Create notification rows for the latest market news the user has not
    seen yet. Idempotent (unique user + source_ref) — safe to call on every
    list/unread request. Returns the number of new rows created."""
    latest = MarketNews.objects.order_by("-published_at")[:MATERIALIZE_TOP]
    cutoff = timezone.now() - timedelta(days=7)
    created = 0
    for article in latest:
        if article.published_at < cutoff:
            continue
        ref = f"news:{article.pk}"
        _, was_created = AppNotification.objects.get_or_create(
            user=user,
            source_ref=ref,
            defaults={
                "kind": AppNotification.KIND_MARKET_NEWS,
                "title": article.headline,
                "body": article.summary,
                "link_url": article.source_url,
                "image_url": article.image_url,
                "created_at": article.published_at,
            },
        )
        if was_created:
            created += 1
    return created