from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import UserSettings

User = get_user_model()


class EmailOrUsernameTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Login with either the username OR the email address.

    SimpleJWT's default validates against `username` only. The Pulse Markets
    frontend labels the login field "Email", so we resolve the entered value to
    a user by username or email before issuing tokens.
    """

    def validate(self, attrs):
        identifier = attrs.get("username", "")
        password = attrs.get("password", "")

        user = None
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
                "Unable to log in with provided credentials."
            )
        if not user.is_active:
            raise serializers.ValidationError("This account is inactive.")

        data = super().validate({"username": user.username, "password": password})
        return data


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
