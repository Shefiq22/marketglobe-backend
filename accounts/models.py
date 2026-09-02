import secrets
import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


class User(AbstractUser):
    """Custom user model for Pulse Markets."""

    email_verified = models.BooleanField(default=False)

    class Meta:
        db_table = "accounts_user"
        ordering = ["-date_joined"]

    def __str__(self):
        return self.username


class UserSettings(models.Model):
    """Per-user app preferences (theme, currency, security switches).

    Stored server-side so the same experience follows the user to any device.
    Auto-created for every account via a post_save signal.
    """

    THEME_CHOICES = [
        ("dark", "Dark"),
        ("light", "Light"),
        ("system", "System"),
    ]
    CURRENCY_CHOICES = [
        ("USD", "US Dollar"),
        ("EUR", "Euro"),
    ]

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="user_settings"
    )
    theme = models.CharField(max_length=10, choices=THEME_CHOICES, default="dark")
    currency = models.CharField(max_length=8, choices=CURRENCY_CHOICES, default="USD")
    notifications_enabled = models.BooleanField(default=True)
    price_alerts = models.BooleanField(default=True)
    probability_alerts = models.BooleanField(default=True)
    daily_market_summary = models.BooleanField(default=True)
    breaking_news = models.BooleanField(default=False)
    product_updates = models.BooleanField(default=False)
    biometric_enabled = models.BooleanField(default=False)
    two_factor_enabled = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "accounts_user_settings"

    def __str__(self):
        return f"{self.user.username} settings"


@receiver(post_save, sender=User)
def _create_user_settings(sender, instance, created, **kwargs):
    if created:
        UserSettings.objects.get_or_create(user=instance)


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
