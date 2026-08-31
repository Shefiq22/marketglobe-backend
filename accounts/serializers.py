from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

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


class RequestPasswordResetSerializer(serializers.Serializer):
    """Email address to send a password-reset link to."""

    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    """Validate a reset token and set a new password.

    The actual user + token check happens in the view (it needs DB + generator
    access), so this only validates the new password strength.
    """

    email = serializers.EmailField()
    token = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])


class RequestOtpSerializer(serializers.Serializer):
    """Email address to send a one-time verification code to."""

    email = serializers.EmailField()


class VerifyOtpSerializer(serializers.Serializer):
    """Verify a one-time code and return JWT tokens for the owner."""

    email = serializers.EmailField()
    code = serializers.CharField()
