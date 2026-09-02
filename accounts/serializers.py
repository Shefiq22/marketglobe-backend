from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import UserSettings

User = get_user_model()


class EmailOrUsernameTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Login with either the username OR the email address.

    Resolves the entered value to a user by username or email, validates the
    password, and exposes the matching user via ``self.user`` (populated in
    ``validate``). Token issuance happens in the view so two-factor-auth can be
    enforced between validation and token creation.
    """

    two_factor_code = serializers.CharField(write_only=True, required=False, allow_blank=True)

    def validate(self, attrs):
        self.user = None

        identifier = attrs.get("username", "")
        password = attrs.get("password", "")

        if User.objects.filter(email__iexact=identifier).exists():
            user = User.objects.filter(email__iexact=identifier).first()
        else:
            user = User.objects.filter(username=identifier).first()

        if user is None:
            raise serializers.ValidationError(
                "No account found with that email or username."
            )
        if not user.check_password(password):
            raise serializers.ValidationError(
                "The password you entered is incorrect."
            )
        if not user.is_active:
            raise serializers.ValidationError("This account is disabled.")

        self.user = user
        return attrs


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "date_joined", "email_verified"]
        read_only_fields = ["id", "date_joined", "email_verified"]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["username", "email", "password", "password_confirm"]

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        user = User.objects.create_user(**validated_data)
        return user


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])

    def validate_old_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value


class ResetPasswordSerializer(serializers.Serializer):
    """Validate a password-reset OTP and set a new password.

    The actual user + code check happens in the view (it needs DB access), so
    this only validates the new password strength.
    """

    email = serializers.EmailField()
    code = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])


class RequestOtpSerializer(serializers.Serializer):
    """Email address (and optional purpose) to send a one-time code to."""

    email = serializers.EmailField()
    purpose = serializers.ChoiceField(
        choices=[("email_verify", "email_verify"), ("password_reset", "password_reset")],
        required=False,
    )


class VerifyOtpSerializer(serializers.Serializer):
    """Verify a one-time code and return JWT tokens for the owner."""

    email = serializers.EmailField()
    code = serializers.CharField()


class GoogleLoginSerializer(serializers.Serializer):
    """Accept a Google ID token and (optionally) profile info.

    The token is verified against Google's tokeninfo endpoint in the view; the
    verification payload's email is trusted as the account identity.
    """

    id_token = serializers.CharField()
    email = serializers.EmailField(required=False, allow_blank=True)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)


class TwoFactorCodeSerializer(serializers.Serializer):
    """A TOTP code supplied by an authenticator app."""

    code = serializers.CharField(max_length=10)


class TwoFactorLoginSerializer(serializers.Serializer):
    """Email + TOTP code, used to complete a 2FA-protected login."""

    email = serializers.EmailField()
    code = serializers.CharField(max_length=10)


class UserSettingsSerializer(serializers.ModelSerializer):
    """Read/write user preferences for the Settings screen.

    Fields mirror the frontend toggles: theme (dark/light/system), display
    currency, and the notifications / biometric / two-factor switches.
    """

    class Meta:
        model = UserSettings
        fields = [
            "theme",
            "currency",
            "notifications_enabled",
            "price_alerts",
            "probability_alerts",
            "daily_market_summary",
            "breaking_news",
            "product_updates",
            "biometric_enabled",
            "two_factor_enabled",
            "updated_at",
        ]
        read_only_fields = ["updated_at"]

    def validate_theme(self, value):
        if value not in ("dark", "light", "system"):
            raise serializers.ValidationError("theme must be dark, light, or system.")
        return value

    def validate_currency(self, value):
        if value not in ("USD", "EUR"):
            raise serializers.ValidationError("currency must be USD or EUR.")
        return value
