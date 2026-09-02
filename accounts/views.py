import hashlib
import logging
import time

import requests
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
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
    GoogleLoginSerializer,
    RegisterSerializer,
    RequestOtpSerializer,
    ResetPasswordSerializer,
    TwoFactorCodeSerializer,
    TwoFactorLoginSerializer,
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
    """POST /api/auth/login/ — accepts either username or email.

    Handles two-step login for accounts with two-factor authentication:
      * No 2FA           -> returns {access, refresh} tokens immediately.
      * 2FA, no code     -> returns {"requires_2fa": true, "email": ...} so the
                            client can show the "enter your authenticator code"
                            screen, then POST /api/auth/2fa/login/ to finish.
      * 2FA + code       -> the code is validated before tokens are issued.
    """

    serializer_class = EmailOrUsernameTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        from . import totp

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.user

        settings_obj, _ = UserSettings.objects.get_or_create(user=user)

        # Two-factor enabled: require a TOTP code before issuing tokens.
        if settings_obj.two_factor_enabled and settings_obj.totp_secret:
            supplied = serializer.validated_data.get("two_factor_code", "")
            if not supplied:
                return Response(
                    {"detail": "Two-factor authentication is required.", "requires_2fa": True, "email": user.email or user.username},
                    status=status.HTTP_200_OK,
                )
            if not totp.verify(settings_obj.totp_secret, supplied.strip().replace(" ", "")):
                return Response(
                    {"detail": "Invalid two-factor code."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        tokens = _issue_tokens(user)
        return Response(tokens, status=status.HTTP_200_OK)


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


class GoogleLoginView(APIView):
    """POST /api/auth/google/

    Body: {id_token, email?, first_name?, last_name?}

    Verifies a Google ID token against Google's tokeninfo endpoint, then either
    finds or creates the matching account (keyed by the verified email) and
    returns JWT tokens. Existing accounts with a password are fine — Google
    simply logs them in too.
    """

    permission_classes = [permissions.AllowAny]
    serializer_class = GoogleLoginSerializer

    def _verify_token(self, id_token):
        """Verify a Google ID token. Returns the verified claim dict or None."""
        try:
            resp = requests.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"id_token": id_token},
                timeout=10,
            )
            if resp.status_code != 200:
                logger.warning("Google tokeninfo rejected token: %s", resp.status_code)
                return None
            return resp.json()
        except requests.RequestException as e:
            logger.warning("Google tokeninfo request failed: %s", e)
            return None

    def post(self, request):
        serializer = GoogleLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        payload = self._verify_token(serializer.validated_data["id_token"])
        if not payload or not payload.get("email"):
            return Response(
                {"detail": "Could not verify the Google account."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Sanity-check that the app's audience matches this token. When the app
        # posts an Android/Web client id as the aud, this prevents a token minted
        # for a different OAuth client from being accepted.
        allowed_aud = getattr(settings, "GOOGLE_OAUTH_CLIENT_IDS", [])
        if allowed_aud and payload.get("aud") not in allowed_aud:
            logger.warning("Google token audience mismatch: %s", payload.get("aud"))
            return Response(
                {"detail": "Google token audience is not valid for this app."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = payload["email"].lower()
        first = serializer.validated_data.get("first_name") or payload.get("given_name", "")
        last = serializer.validated_data.get("last_name") or payload.get("family_name", "")

        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            base_username = (first or email.split("@")[0]).lower().replace(" ", "")
            username = base_username
            suffix = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{suffix}"
                suffix += 1
            user = User.objects.create_user(
                username=username,
                email=email,
                password=None,
                first_name=first,
                last_name=last,
            )
            # Google accounts are pre-verified.
            user.email_verified = True
            user.save(update_fields=["email_verified"])

        if not user.is_active:
            return Response(
                {"detail": "This account is inactive."},
                status=status.HTTP_403_FORBIDDEN,
            )

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": UserSerializer(user).data,
                "tokens": {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                },
            }
        )


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


class TwoFactorSetupView(APIView):
    """GET /api/auth/2fa/setup/ — start (or restart) 2FA enrollment.

    Returns a fresh TOTP secret, its otpauth URI, and a base64 QR image. The
    secret is saved now but 2FA is not enabled until the user verifies a code.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from . import totp

        settings_obj, _ = UserSettings.objects.get_or_create(user=request.user)
        secret = totp.new_secret()
        settings_obj.totp_secret = secret
        # Keep the current on/off state — enrollment just refreshes the secret.
        settings_obj.save(update_fields=["totp_secret"])

        uri = totp.provisioning_uri(request.user.email or request.user.username, secret)
        return Response(
            {
                "secret": secret,
                "otpauth_uri": uri,
                "qr_base64": totp.qr_base64(uri),
                "manual_entry_key": secret,
            },
            status=status.HTTP_200_OK,
        )


class TwoFactorVerifyView(APIView):
    """POST /api/auth/2fa/verify/ — confirm a TOTP code and enable 2FA.

    Body: {code}. On a match, `two_factor_enabled` becomes True.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from . import totp

        serializer = TwoFactorCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        settings_obj, _ = UserSettings.objects.get_or_create(user=request.user)
        if not settings_obj.totp_secret:
            return Response(
                {"detail": "Run 2FA setup first to generate a secret."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        code = serializer.validated_data["code"].strip().replace(" ", "")
        if not totp.verify(settings_obj.totp_secret, code):
            return Response(
                {"detail": "That code is invalid. Check the time on your authenticator app and try again."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        settings_obj.two_factor_enabled = True
        settings_obj.save(update_fields=["two_factor_enabled"])
        return Response(
            {"detail": "Two-factor authentication is now enabled.", "two_factor_enabled": True},
            status=status.HTTP_200_OK,
        )


class TwoFactorDisableView(APIView):
    """POST /api/auth/2fa/disable/ — disable 2FA (requires a valid code).

    Body: {code}. Requires a correct TOTP code so a stolen session can't just
    switch security off. Clears the secret afterwards.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from . import totp

        serializer = TwoFactorCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        settings_obj, _ = UserSettings.objects.get_or_create(user=request.user)
        if not settings_obj.two_factor_enabled:
            return Response(
                {"detail": "Two-factor authentication is not enabled."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        code = serializer.validated_data["code"].strip().replace(" ", "")
        if not settings_obj.totp_secret or not totp.verify(settings_obj.totp_secret, code):
            return Response(
                {"detail": "That code is invalid. Check the time on your authenticator app and try again."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        settings_obj.two_factor_enabled = False
        settings_obj.totp_secret = ""
        settings_obj.save(update_fields=["two_factor_enabled", "totp_secret"])
        return Response(
            {"detail": "Two-factor authentication is now disabled.", "two_factor_enabled": False},
            status=status.HTTP_200_OK,
        )


class TwoFactorLoginView(APIView):
    """POST /api/auth/2fa/login/ — complete a 2FA-protected login.

    Body: {email, code}. Verifies the TOTP code for the matching account and
    issues JWT tokens. This is an alternative to passing the code through the
    normal login endpoint, and is used by the "enter your 2FA code" screen.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        from . import totp

        serializer = TwoFactorLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"].strip().lower()
        code = serializer.validated_data["code"].strip().replace(" ", "")

        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            return Response({"detail": "Invalid email or code."}, status=status.HTTP_400_BAD_REQUEST)

        settings_obj, _ = UserSettings.objects.get_or_create(user=user)
        if not settings_obj.two_factor_enabled or not settings_obj.totp_secret:
            return Response(
                {"detail": "Two-factor authentication is not enabled for this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not totp.verify(settings_obj.totp_secret, code):
            return Response({"detail": "Invalid code."}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {"detail": "Success.", "tokens": _issue_tokens(user)},
            status=status.HTTP_200_OK,
        )
