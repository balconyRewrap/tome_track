"""Throttles for users."""
from rest_framework.throttling import AnonRateThrottle


class RegisterThrottle(AnonRateThrottle):
    """Throttle for user registration endpoint."""

    scope = "register"


class LoginThrottle(AnonRateThrottle):
    """Throttle for user login endpoint."""

    scope = "login"


class PasswordResetThrottle(AnonRateThrottle):
    """Throttle for password reset endpoint."""

    scope = "password_reset"
