from django.test import TestCase
from rest_framework import status


class WatchlistCreateTests(TestCase):
    def _register(self, username="wluser", email="wluser@example.com"):
        resp = self.client.post(
            "/api/auth/register/",
            {
                "username": username,
                "email": email,
                "password": "WatchlistPass123!",
                "password_confirm": "WatchlistPass123!",
            },
            content_type="application/json",
        )
        self.client.defaults["HTTP_AUTHORIZATION"] = "Bearer " + resp.json()["tokens"]["access"]

    def test_create_is_idempotent_per_user(self):
        self._register()
        first = self.client.post(
            "/api/watchlist/",
            {"name": "My Watchlist"},
            content_type="application/json",
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        second = self.client.post(
            "/api/watchlist/",
            {"name": "My Watchlist"},
            content_type="application/json",
        )
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(second.json()["id"], first.json()["id"])

    def test_two_users_keep_separate_watchlists(self):
        self._register("wluserA", "wluserA@example.com")
        a = self.client.post("/api/watchlist/", {"name": "A"}, content_type="application/json")
        self.assertEqual(a.status_code, status.HTTP_201_CREATED)

        self._register("wluserB", "wluserB@example.com")
        b = self.client.post("/api/watchlist/", {"name": "B"}, content_type="application/json")
        self.assertEqual(b.status_code, status.HTTP_201_CREATED)
        self.assertNotEqual(a.json()["id"], b.json()["id"])