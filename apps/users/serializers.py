"""Serializers for User Application."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.password_validation import validate_password
from django.core.validators import EmailValidator
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import Token

from apps.users.models import User as UserModel

User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    """Serializer for user registration."""

    email = serializers.EmailField(validators=[EmailValidator()])
    username = serializers.CharField(max_length=50)
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, min_length=8)

    def validate_email(self, value: str) -> str:  # noqa: PLR6301
        """Validate that the email is unique.

        Returns:
            str: The validated email address.

        Raises:
            serializers.ValidationError: If a user with the given email already exists.
        """
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("User with this email already exists.")
        return value

    def validate_username(self, value: str) -> str:  # noqa: PLR6301
        """Validate that the username is unique.

        Returns:
            str: The validated username.

        Raises:
            serializers.ValidationError: If a user with the given username already exists.
        """
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("User with this username already exists.")
        return value

    def validate_password(self, value: str) -> str:  # noqa: PLR6301
        """Validate the password using Django's built-in validators and ensure it contains both letters and numbers.

        Returns:
            str: The validated password.

        Raises:
            serializers.ValidationError: If the password does not meet the validation criteria.
        """
        try:
            validate_password(value)
        except serializers.ValidationError as e:
            raise serializers.ValidationError("Password is too weak.") from e
        if value.isdigit():
            raise serializers.ValidationError("Password must contain both letters and numbers.")
        return value

    def validate(self, attrs: dict) -> dict:  # noqa: PLR6301
        """Validate that the password and password_confirm fields match.

        Returns:
            dict: The validated data.

        Raises:
            serializers.ValidationError: If the password and password_confirm fields do not match.
        """
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        return attrs

    def create(self, validated_data: dict) -> AbstractUser:  # noqa: PLR6301
        """Create a new user instance with the validated data.

        Returns:
            AbstractUser: The created user instance.
        """
        validated_data.pop("password_confirm")
        user = User.objects.create_user(
            email=validated_data["email"],
            username=validated_data["username"],
            password=validated_data["password"],
        )
        return user  # noqa: RET504


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom serializer for obtaining JWT tokens that includes the user's role in the token payload."""

    @classmethod
    def get_token(cls, user) -> Token:
        token = super().get_token(user)
        # custom claims will be added later if needed
        token["role"] = user.role
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        # User has it, but pylance doesn't recognize it, so we ignore the type errors here
        data["user_id"] = self.user.id  # pyright: ignore[reportOptionalMemberAccess, reportAttributeAccessIssue]
        data["email"] = self.user.email  # pyright: ignore[reportOptionalMemberAccess, reportAttributeAccessIssue]
        data["role"] = self.user.role  # pyright: ignore[reportOptionalMemberAccess, reportAttributeAccessIssue]
        return data


class LogoutSerializer(serializers.Serializer):
    """Serializer for user logout."""

    refresh = serializers.CharField()
