"""Models for User Application."""
from typing import Any

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models

from apps.common.models import TimestampedModel


class UserRole(models.TextChoices):
    """Available roles for a user."""

    USER = 'user', 'User'
    ADMIN = 'admin', 'Admin'


class UserManager(BaseUserManager):
    """Custom user manager for the User model."""

    def create_user(self, email: str, username: str, password: str, **extra_fields: Any) -> "User":  # noqa: ANN401
        """Creates and saves a User with the given email, username, and password.

        Args:
            email (str): The email address of the user.
            username (str): The username of the user.
            password (str): The password for the user.
            **extra_fields: Additional fields to set on the user.

        Returns:
            User: The created user instance.

        Raises:
            ValueError: If email, username, or password is not provided.
        """
        if not email:
            raise ValueError("Email is required")
        if not username:
            raise ValueError("Username is required")
        if not password:
            raise ValueError("Password is required")
        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, username: str, password: str, **extra_fields: Any) -> "User":  # noqa: ANN401
        """Creates and saves a superuser with the given email, username, and password.

        Args:
            email (str): The email address of the superuser.
            username (str): The username of the superuser.
            password (str): The password for the superuser.
            **extra_fields: Additional fields to set on the superuser.

        Returns:
            User: The created superuser instance.

        Raises:
            ValueError: If email, username, or password is not provided, raised in create_user().
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, username, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin, TimestampedModel):
    """Custom user model for the Tome Track application.

    Fields:
    - email: Unique email address for authentication.
    - username: Unique username for display purposes.
    - role: User role, either 'user' or 'admin'.
    - is_active: Boolean indicating if the user account is active.
    - is_staff: Boolean indicating if the user can access the admin site.
    - created_at: Timestamp when the user was created (inherited from TimestampedModel).
    - updated_at: Timestamp when the user was last updated (inherited from TimestampedModel
    """

    email = models.EmailField(unique=True)
    username = models.CharField(max_length=50, unique=True)
    role = models.CharField(choices=UserRole.choices, max_length=10, default=UserRole.USER)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    token_version = models.PositiveIntegerField(default=0)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']  # noqa: RUF012
    objects = UserManager()


class PasswordResetToken(TimestampedModel):
    """Model for storing password reset tokens."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_reset_tokens')
    token = models.CharField(max_length=255, unique=True)
    used = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"PasswordResetToken(user={self.user.email}, token={self.token}, used={self.used}), created_at={self.created_at})"