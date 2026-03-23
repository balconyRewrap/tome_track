"""Serializers for User Application."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import Token

from apps.common.validators import validate_serializer_name

User = get_user_model()


class AuthCheckSerializer(serializers.Serializer):
    """Serializer for authentication check test endpoint."""

    detail = serializers.CharField()
    user_id = serializers.IntegerField()
    email = serializers.EmailField()


class RegisterSerializer(serializers.Serializer):
    """Serializer for user registration."""

    email = serializers.EmailField(validators=[EmailValidator()])
    username = serializers.CharField(max_length=50, validators=[validate_serializer_name])
    password = serializers.CharField(write_only=True, min_length=8)

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
        except ValidationError as e:
            raise serializers.ValidationError("Password is too weak.") from e
        return value

    def create(self, validated_data: dict) -> AbstractUser:  # noqa: PLR6301
        """Create a new user instance with the validated data.

        Returns:
            AbstractUser: The created user instance.
        """
        user = User.objects.create_user(
            email=validated_data["email"],
            username=validated_data["username"],
            password=validated_data["password"],
        )
        return user  # noqa: RET504


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom serializer for obtaining JWT tokens that includes the user's role in the token payload."""

    @classmethod
    def get_token(cls, user) -> Token:  # noqa: ANN001
        """Get JWT token.

        Returns:
            token (Token): JWT token of user.
        """
        token = super().get_token(user)
        # custom claims will be added later if needed
        token["token_version"] = user.token_version
        token["role"] = user.role
        return token

    def validate(self, attrs: dict) -> dict:
        """Validate serializer data.

        Returns:
            dict: validated attributes.

        Raises:
            serializers.ValidationError: if account is disabled.
        """
        data = super().validate(attrs)
        # User has it, but pylance doesn't recognize it, so we ignore the type errors here
        if not self.user:
            raise serializers.ValidationError("Unable to log in with provided credentials.")
        if not self.user.is_active:
            raise serializers.ValidationError("User account is disabled.")
        data["user_id"] = self.user.id  # pyright: ignore[reportOptionalMemberAccess, reportAttributeAccessIssue]
        data["email"] = self.user.email  # pyright: ignore[reportOptionalMemberAccess, reportAttributeAccessIssue]
        data["role"] = self.user.role  # pyright: ignore[reportOptionalMemberAccess, reportAttributeAccessIssue]
        return data


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile."""

    class Meta:
        """Meta class for UserProfileSerializer."""

        model = User
        fields = ['id', 'email', 'username', 'role', 'page_coefficient']
        read_only_fields = ['id', 'email', 'role']

    def validate_page_coefficient(self, value: float) -> float:  # noqa: PLR6301
        """Validate that the page_coefficient is non-negative.

        Returns:
            float: The validated page_coefficient value.

        Raises:
            serializers.ValidationError: If the page_coefficient is negative.
        """
        if value is None:
            return value
        if value < 0:
            raise serializers.ValidationError('page_coefficient must be non-negative.')
        return value


class ChangeEmailSerializer(serializers.Serializer):
    """Serializer for changing user email."""

    new_email = serializers.EmailField(validators=[EmailValidator()])
    password = serializers.CharField(write_only=True)

    def validate_new_email(self, value: str) -> str:
        """Validate that the new email is unique.

        Returns:
            str: The validated email address.

        Raises:
            serializers.ValidationError:
                If a user with the given email already exists or the new email is the same as the current email.
        """
        user = self.context['request'].user
        if user.email == value:
            raise serializers.ValidationError("New email cannot be the same as the current email.")
        if User.objects.exclude(pk=user.pk).filter(email=value).exists():
            raise serializers.ValidationError("User with this email already exists.")
        return value

    def validate(self, attrs: dict) -> dict:
        """Validate that the provided password is correct.

        Returns:
            dict: The validated data.

        Raises:
            serializers.ValidationError: If the provided password is incorrect.
        """
        user = self.context['request'].user
        if not user.check_password(attrs['password']):
            raise serializers.ValidationError({"password": "Incorrect password."})
        return attrs


class PasswordResetSerializer(serializers.Serializer):
    """Serializer for requesting a password reset."""

    email = serializers.EmailField(validators=[EmailValidator()])


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer for confirming a password reset."""

    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_new_password(self, value: str) -> str:  # noqa: PLR6301
        """Validate the new password using Django's built-in validators and ensure it contains both letters and numbers.

        Returns:
            str: The validated new password.

        Raises:
            serializers.ValidationError: If the new password does not meet the validation criteria.
        """
        try:
            validate_password(value)
        except ValidationError as e:
            raise serializers.ValidationError("Password is too weak.") from e
        return value


class PasswordChangeSerializer(serializers.Serializer):
    """Serializer for changing user password."""

    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_new_password(self, value: str) -> str:  # noqa: PLR6301
        """Validate the new password using Django's built-in validators and ensure it contains both letters and numbers.

        Returns:
            str: The validated new password.

        Raises:
            serializers.ValidationError: If the new password does not meet the validation criteria.
        """
        try:
            validate_password(value)
        except ValidationError as e:
            raise serializers.ValidationError("Password is too weak.") from e
        return value

    def validate(self, attrs: dict) -> dict:
        """Validate that the provided current password is correct.

        Returns:
            dict: The validated data.

        Raises:
            serializers.ValidationError: If the provided current password is incorrect.
        """
        user = self.context['request'].user
        if not user.check_password(attrs['current_password']):
            raise serializers.ValidationError({"current_password": "Incorrect password."})
        return attrs


class AdminUserSerializer(serializers.ModelSerializer):
    """Serializer for admin user management."""

    class Meta:  # noqa: D106
        model = User
        fields = ['id', 'email', 'username', 'role', 'is_active', 'created_at', 'page_coefficient']
        read_only_fields = ['id', 'email', 'username', 'created_at']
