import hashlib
import logging
import time

from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import OtpCode, UserSettings
from .serializers import (
    ChangePasswordSerializer,
    EmailOrUsernameTokenObtainPairSerializer,
    RegisterSerializer,
    RequestOtpSerializer,
    ResetPasswordSerializer,
    UserSerializer,
    UserSettingsSerializer,
    VerifyOtpSerializer,
)

logger = logging.getLogger(__name__)

# OTP abuse protection: a sender waits at least OTP_COOLDOWN_SECONDS between
# codes and at most OTP_HOURLY_LIMIT codes per hour (per account + purpose).
OTP_COOLDOWN_SECONDS = 60
OTP_HOURLY_LIMIT = 5

User = get_user_model()


class EmailOrUsernameTokenObtainPairView(TokenObtainPairView):
    """POST /api/auth/login/ — accepts either username or email."""

    serializer_class = EmailOrUsernameTokenObtainPairSerializer


class RegisterView(generics.CreateAPIView):
    """POST /api/auth/register/"""

    queryset = User.objects.all()
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": UserSerializer(user).data,
                "tokens": {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                },
            },
            status=status.HTTP_201_CREATED,
        )


class MeView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/auth/me/"""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class UserSettingsView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/auth/settings/

    Read and update the signed-in user's app preferences (theme, currency,
    notifications/biometric/two-factor switches). The settings row is
    auto-created with the account, but we call get_or_create defensively for
    any pre-existing accounts.
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserSettingsSerializer

    def get_object(self):
        settings, _ = UserSettings.objects.get_or_create(user=self.request.user)
        return settings


class ChangePasswordView(APIView):
    """POST /api/auth/change-password/"""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save()
        return Response({"detail": "Password updated successfully."})


class ResetPasswordView(APIView):
    """POST /api/auth/reset-password/

    Validates an emailed one-time password-reset code and sets a new password.
    Body: {email, code, new_password}
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"].strip().lower()
        code = serializer.validated_data["code"].strip()
        user = User.objects.filter(email__iexact=email).first()

        if user is None:
            return Response(
                {"detail": "Invalid or expired code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        otp = (
            OtpCode.objects.filter(user=user, purpose="password_reset", used=False)
            .order_by("-created_at")
            .first()
        )
        if otp is None or not otp.is_valid() or otp.code_hash != _hash_code(code):
            return Response(
                {"detail": "Invalid or expired code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        otp.used = True
        otp.save(update_fields=["used"])
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        return Response({"detail": "Password reset successfully. You can now sign in."})


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def _issue_tokens(user):
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


def _send_with_retry(subject, message, recipient):
    """SMTP can transiently fail; retry with a small backoff before giving up."""
    last_exc = None
    for attempt in range(3):
        try:
            send_mail(subject, message, None, [recipient], fail_silently=False)
            return True
        except Exception as exc:
            last_exc = exc
            logger.warning("email send attempt %s/3 failed: %s", attempt + 1, exc)
            time.sleep(1)
    logger.error("email permanently failed for %s: %s", recipient, last_exc)
    return False


class RequestOtpView(APIView):
    """POST /api/auth/request-otp/ — email a one-time verification code.

    Body: {email}. Always returns success to avoid leaking which emails exist.
    When an account matches, a 6-digit code is emailed (or logged to console in
    development where SMTP is not configured). Cooldown/hourly limits prevent
    OTP-bombing an inbox.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RequestOtpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()
        purpose = serializer.validated_data.get("purpose", "email_verify")

        user = User.objects.filter(email__iexact=email).first()
        if user is not None:
            recent = OtpCode.objects.filter(user=user, purpose=purpose)
            now = timezone.now()

            if recent.filter(created_at__gte=now - timezone.timedelta(seconds=OTP_COOLDOWN_SECONDS)).exists():
                return Response(
                    {"detail": "A code was sent recently. Please wait a moment before requesting another."},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )
            if recent.filter(created_at__gte=now - timezone.timedelta(hours=1)).count() >= OTP_HOURLY_LIMIT:
                return Response(
                    {"detail": "Too many codes requested. Please wait an hour and try again."},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )

            code = OtpCode.generate_code()
            OtpCode.objects.filter(user=user, purpose=purpose, used=False).update(used=True)
            OtpCode.objects.create(
                user=user,
                code_hash=_hash_code(code),
                purpose=purpose,
                expires_at=now + timezone.timedelta(minutes=10),
            )
            if purpose == "password_reset":
                subject = "Your MarketGlobe password reset code"
                message = (
                    f"Hi {user.username or user.email},\n\n"
                    f"Your password-reset code is: {code}\n\n"
                    "Enter it in the app to set a new password. It expires in "
                    "10 minutes. If you didn't request this, you can safely "
                    "ignore this email."
                )
            else:
                subject = "Your MarketGlobe verification code"
                message = (
                    f"Hi {user.username or user.email},\n\n"
                    f"Your verification code is: {code}\n\n"
                    "It expires in 10 minutes. If you didn't request this, "
                    "you can safely ignore this email."
                )
            _send_with_retry(subject, message, user.email)

        return Response({"detail": "If that email is registered, a code has been sent."})


class VerifyOtpView(APIView):
    """POST /api/auth/verify-otp/ — verify a code and issue JWT tokens.

    Body: {email, code}. Marks the account email as verified on success and
    returns fresh access/refresh tokens so the user can proceed to the app.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = VerifyOtpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()
        code = serializer.validated_data["code"].strip()

        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            return Response({"detail": "Invalid or expired code."}, status=status.HTTP_400_BAD_REQUEST)

        otp = (
            OtpCode.objects.filter(user=user, purpose="email_verify", used=False)
            .order_by("-created_at")
            .first()
        )
        if otp is None or not otp.is_valid() or otp.code_hash != _hash_code(code):
            return Response({"detail": "Invalid or expired code."}, status=status.HTTP_400_BAD_REQUEST)

        otp.used = True
        otp.save(update_fields=["used"])
        if not user.email_verified:
            user.email_verified = True
            user.save(update_fields=["email_verified"])

        tokens = _issue_tokens(user)
        return Response(
            {"detail": "Email verified successfully.", "tokens": tokens},
            status=status.HTTP_200_OK,
        )
