import hashlib
import os

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import send_mail, BadHeaderError
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import OtpCode
from .serializers import (
    ChangePasswordSerializer,
    EmailOrUsernameTokenObtainPairSerializer,
    RegisterSerializer,
    RequestOtpSerializer,
    RequestPasswordResetSerializer,
    ResetPasswordSerializer,
    UserSerializer,
    VerifyOtpSerializer,
)

User = get_user_model()
password_reset_token = PasswordResetTokenGenerator()


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


class ChangePasswordView(APIView):
    """POST /api/auth/change-password/"""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save()
        return Response({"detail": "Password updated successfully."})


class RequestPasswordResetView(APIView):
    """POST /api/auth/request-password-reset/

    Accepts an email address. If the address belongs to an account, a
    password-reset token is generated and emailed. Always returns success (even
    for unknown emails) to avoid leaking which addresses are registered.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RequestPasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()

        user = User.objects.filter(email__iexact=email).first()
        if user is not None:
            token = password_reset_token.make_token(user)
            uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
            frontend_url = os.getenv("FRONTEND_URL", "https://marketglobe-web.onrender.com")
            reset_url = f"{frontend_url}/reset-password?uidb64={uidb64}&token={token}"
            try:
                send_mail(
                    subject="Reset your MarketGlobe password",
                    message=(
                        f"Hi {user.username or user.email},\n\n"
                        f"Use this link to set a new password (it expires soon):\n{reset_url}\n\n"
                        "If you didn't request this, you can safely ignore this email."
                    ),
                    from_email=None,
                    recipient_list=[user.email],
                    fail_silently=False,
                )
            except (BadHeaderError, Exception):
                # Email sending is best-effort; never fail the API call for it.
                pass

        return Response({"detail": "If that email is registered, a reset link has been sent."})


class ResetPasswordView(APIView):
    """POST /api/auth/reset-password/

    Validates the emailed token and sets a new password. Body:
    {email, token, new_password}
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"].strip().lower()
        user = User.objects.filter(email__iexact=email).first()
        token = serializer.validated_data["token"]

        if user is None or not password_reset_token.check_token(user, token):
            return Response(
                {"detail": "This reset link is invalid or has expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(serializer.validated_data["new_password"])
        user.save()
        return Response({"detail": "Password reset successfully. You can now sign in."})


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def _issue_tokens(user):
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


class RequestOtpView(APIView):
    """POST /api/auth/request-otp/ — email a one-time verification code.

    Body: {email}. Always returns success to avoid leaking which emails exist.
    When an account matches, a 6-digit code is emailed (or logged to console in
    development where SMTP is not configured).
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RequestOtpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()

        user = User.objects.filter(email__iexact=email).first()
        if user is not None:
            code = OtpCode.generate_code()
            OtpCode.objects.filter(user=user, purpose="email_verify", used=False).update(used=True)
            OtpCode.objects.create(
                user=user,
                code_hash=_hash_code(code),
                purpose="email_verify",
                expires_at=timezone.now() + timezone.timedelta(minutes=10),
            )
            try:
                send_mail(
                    subject="Your MarketGlobe verification code",
                    message=(
                        f"Hi {user.username or user.email},\n\n"
                        f"Your verification code is: {code}\n\n"
                        "It expires in 10 minutes. If you didn't request this, "
                        "you can safely ignore this email."
                    ),
                    from_email=None,
                    recipient_list=[user.email],
                    fail_silently=False,
                )
            except Exception:
                # Email is best-effort; never fail the API call for it.
                pass

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
