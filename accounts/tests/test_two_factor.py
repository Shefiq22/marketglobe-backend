from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from accounts import totp
from accounts.models import UserSettings

User = get_user_model()


class TwoFactorTestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="Secret123!",
        )
        self.settings = UserSettings.objects.get(user=self.user)
        self.client.force_authenticate(self.user)

    def _setup_secret(self):
        secret = totp.new_secret()
        self.settings.totp_secret = secret
        self.settings.save(update_fields=["totp_secret"])
        return secret

    def test_setup_returns_secret_and_qr(self):
        resp = self.client.get("/api/auth/2fa/setup/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("secret", resp.data)
        self.assertIn("otpauth_uri", resp.data)
        self.assertIn("qr_base64", resp.data)
        self.assertNotEqual(resp.data["qr_base64"], "")
        # secret was persisted for later verify
        self.settings.refresh_from_db()
        self.assertEqual(self.settings.totp_secret, resp.data["secret"])

    def test_verify_enables_2fa(self):
        secret = self._setup_secret()
        valid_code = totp._totp(secret).now()
        resp = self.client.post(
            "/api/auth/2fa/verify/", {"code": valid_code}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.settings.refresh_from_db()
        self.assertTrue(self.settings.two_factor_enabled)

    def test_verify_rejects_bad_code(self):
        self._setup_secret()
        resp = self.client.post("/api/auth/2fa/verify/", {"code": "000000"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.settings.refresh_from_db()
        self.assertFalse(self.settings.two_factor_enabled)

    def test_login_requires_2fa_code(self):
        secret = self._setup_secret()
        self.settings.two_factor_enabled = True
        self.settings.save(update_fields=["two_factor_enabled"])

        # Step 1: without a code -> requires_2fa
        self.client.force_authenticate(None)
        resp = self.client.post(
            "/api/auth/login/",
            {"username": "alice@example.com", "password": "Secret123!"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data.get("requires_2fa"))
        self.assertNotIn("access", resp.data)

        # Step 2: with a valid code -> tokens
        code = totp._totp(secret).now()
        resp = self.client.post(
            "/api/auth/login/",
            {"username": "alice@example.com", "password": "Secret123!", "two_factor_code": code},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", resp.data)
        self.assertIn("refresh", resp.data)

    def test_two_factor_login_endpoint(self):
        secret = self._setup_secret()
        self.settings.two_factor_enabled = True
        self.settings.save(update_fields=["two_factor_enabled"])

        self.client.force_authenticate(None)
        code = totp._totp(secret).now()
        resp = self.client.post(
            "/api/auth/2fa/login/",
            {"email": "alice@example.com", "code": code},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", resp.data["tokens"])

    def test_disable_requires_valid_code(self):
        secret = self._setup_secret()
        self.settings.two_factor_enabled = True
        self.settings.save(update_fields=["two_factor_enabled"])

        resp = self.client.post("/api/auth/2fa/disable/", {"code": "000000"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

        code = totp._totp(secret).now()
        resp = self.client.post("/api/auth/2fa/disable/", {"code": code}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.settings.refresh_from_db()
        self.assertFalse(self.settings.two_factor_enabled)
        self.assertEqual(self.settings.totp_secret, "")


class GoogleLoginTestCase(APITestCase):
    def test_requires_id_token(self):
        resp = self.client.post("/api/auth/google/", {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_invalid_token(self):
        resp = self.client.post(
            "/api/auth/google/", {"id_token": "not-a-real-token"}, format="json"
        )
        # tokeninfo will return non-200 -> 400
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
