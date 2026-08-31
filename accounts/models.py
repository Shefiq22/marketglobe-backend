import secrets
import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    """Custom user model for Pulse Markets."""

    email_verified = models.BooleanField(default=False)

    class Meta:
        db_table = "accounts_user"
        ordering = ["-date_joined"]

    def __str__(self):
        return self.username


class OtpCode(models.Model):
    """A one-time email verification code (OTP) for a user.

    Codes are stored hashed, are single-use, and expire after a short TTL.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="otp_codes")
    code_hash = models.CharField(max_length=128)
    purpose = models.CharField(max_length=20, default="email_verify")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)

    class Meta:
        db_table = "accounts_otp_code"
        ordering = ["-created_at"]

    @staticmethod
    def generate_code():
        """Returns a cryptographically random 6-digit code."""
        return f"{secrets.randbelow(1000000):06d}"

    def is_valid(self):
        return not self.used and self.expires_at > timezone.now()
