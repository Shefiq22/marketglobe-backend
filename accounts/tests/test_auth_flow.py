import re

from django.core import mail
from django.test import TestCase, override_settings
from rest_framework import status


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class OtpAuthFlowTests(TestCase):
    def _register(self, email="otpflow@example.com"):
        return self.client.post(
            "/api/auth/register/",
            {
                "username": "otpflowuser",
                "email": email,
                "password": "StrongPass123!",
                "password_confirm": "StrongPass123!",
            },
            content_type="application/json",
        )

    def _code_from_outbox(self):
        body = mail.outbox[-1].body
        return re.search(r"\b(\d{6})\b", body).group(1)

    def test_verify_otp_round_trip(self):
        reg = self._register()
        self.assertEqual(reg.status_code, status.HTTP_201_CREATED)

        sent = self.client.post(
            "/api/auth/request-otp/",
            {"email": "otpflow@example.com"},
            content_type="application/json",
        )
        self.assertEqual(sent.status_code, status.HTTP_200_OK)
        code = self._code_from_outbox()

        bad = self.client.post(
            "/api/auth/verify-otp/",
            {"email": "otpflow@example.com", "code": "000000"},
            content_type="application/json",
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

        good = self.client.post(
            "/api/auth/verify-otp/",
            {"email": "otpflow@example.com", "code": code},
            content_type="application/json",
        )
        self.assertEqual(good.status_code, status.HTTP_200_OK)
        self.assertIn("tokens", good.json())
        me = self.client.get(
            "/api/auth/me/",
            HTTP_AUTHORIZATION="Bearer " + good.json()["tokens"]["access"],
        )
        self.assertTrue(me.json()["email_verified"])

    def test_reset_password_round_trip(self):
        self._register()
        sent = self.client.post(
            "/api/auth/request-otp/",
            {"email": "otpflow@example.com", "purpose": "password_reset"},
            content_type="application/json",
        )
        self.assertEqual(sent.status_code, status.HTTP_200_OK)
        code = self._code_from_outbox()

        reset = self.client.post(
            "/api/auth/reset-password/",
            {
                "email": "otpflow@example.com",
                "code": code,
                "new_password": "ResetPass456!",
            },
            content_type="application/json",
        )
        self.assertEqual(reset.status_code, status.HTTP_200_OK)

        replayed = self.client.post(
            "/api/auth/reset-password/",
            {
                "email": "otpflow@example.com",
                "code": code,
                "new_password": "ReplayAttack123!",
            },
            content_type="application/json",
        )
        self.assertEqual(replayed.status_code, status.HTTP_400_BAD_REQUEST)

        login = self.client.post(
            "/api/auth/login/",
            {"username": "otpflowuser", "password": "ResetPass456!"},
            content_type="application/json",
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)