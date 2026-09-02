from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from news.models import MarketNews
from notifications.models import AppNotification


class NotificationApiTests(APITestCase):
    def setUp(self):
        self.user = self._create_user("notifuser", "notif@example.com", "Pass1234!")
        self.client.force_authenticate(self.user)

    @staticmethod
    def _create_user(username, email, password):
        from django.contrib.auth import get_user_model

        return get_user_model().objects.create_user(
            username=username, email=email, password=password
        )

    def _seed_news(self, n=3):
        for i in range(n):
            MarketNews.objects.create(
                headline=f"Headline {i}",
                summary=f"Summary {i}",
                source_name="Yahoo Finance",
                source_url="https://example.com/article",
                image_url="https://example.com/img.png",
                published_at=timezone.now() - timezone.timedelta(hours=i),
            )

    def test_unread_count_materializes_from_news(self):
        self._seed_news(3)
        resp = self.client.get("/api/notifications/unread-count/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["count"], 3)
        self.assertEqual(AppNotification.objects.filter(user=self.user).count(), 3)

    def test_mark_read_clears_badge(self):
        self._seed_news(2)
        self.client.get("/api/notifications/unread-count/")
        first = AppNotification.objects.filter(user=self.user).first()
        resp = self.client.post(
            "/api/notifications/mark-read/", {"ids": [first.pk]}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["count"], 1)
        first.refresh_from_db()
        self.assertTrue(first.is_read)

    def test_mark_all_read(self):
        self._seed_news(2)
        self.client.get("/api/notifications/unread-count/")
        resp = self.client.post("/api/notifications/mark-read/", {"all": True}, format="json")
        self.assertEqual(resp.json()["count"], 0)
        remaining = AppNotification.objects.filter(user=self.user, is_read=False).count()
        self.assertEqual(remaining, 0)

    def test_list_returns_serialized_notifications(self):
        self._seed_news(1)
        resp = self.client.get("/api/notifications/")
        payload = resp.json()
        items = payload["results"]
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item["title"], "Headline 0")
        self.assertEqual(item["image_url"], "https://example.com/img.png")
        self.assertFalse(item["is_read"])

    def test_requires_auth(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(
            self.client.get("/api/notifications/").status_code, status.HTTP_401_UNAUTHORIZED
        )

    def test_settings_persist_notification_prefs(self):
        resp = self.client.patch(
            "/api/auth/settings/",
            {
                "price_alerts": False,
                "breaking_news": True,
                "daily_market_summary": False,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        self.assertFalse(body["price_alerts"])
        self.assertTrue(body["breaking_news"])
        self.assertFalse(body["daily_market_summary"])