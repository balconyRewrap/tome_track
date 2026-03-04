"""Custom JWT authentication class that checks the token_version claim against the user's current token_version.

This module defines a custom JWT authentication scheme that includes token versioning to allow for token invalidation.
It also includes an OpenAPI extension to document the custom authentication scheme in the API schema.
"""
from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework_simplejwt.authentication import AuthUser, JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import Token

if TYPE_CHECKING:
    from drf_spectacular.openapi import AutoSchema

User = get_user_model()


class TokenVersionJWTAuthenticationScheme(OpenApiAuthenticationExtension):
    """OpenAPI authentication scheme extension for JWT authentication with token versioning."""

    target_class = 'apps.users.authentification.TokenVersionJWTAuthentication'
    name = 'JWTAuthWithTokenVersion'

    def get_security_definition(self, auto_schema: 'AutoSchema') -> dict:  # noqa: PLR6301, ARG002
        """Return the OpenAPI security scheme definition for JWT authentication with token versioning.

        Returns:
            dict: A dictionary representing the OpenAPI security scheme object for JWT authentication.
        """
        return {
            'type': 'http',
            'scheme': 'bearer',
            'bearerFormat': 'JWT',
        }


class TokenVersionJWTAuthentication(JWTAuthentication):
    """Custom JWT authentication class that checks the token_version claim against the user's current token_version."""

    def get_user(self, validated_token: Token) -> AuthUser:
        """Override the get_user method to include a check for token_version.

        Args:
            validated_token (Token): The validated JWT token containing user claims.

        Returns:
            AuthUser: The authenticated user if the token is valid and token_version matches.

        Raises:
            AuthenticationFailed:
                If the token is invalid or the token_version does not match the user's current token_version.
        """
        user = super().get_user(validated_token)
        token_version = validated_token.get("token_version")
        if token_version is None or user.token_version != token_version:
            raise AuthenticationFailed("Token is no longer valid (token_version mismatch).")
        return user
