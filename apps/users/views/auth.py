"""Authentication views for user registration, login, logout, and token refresh."""
import logging
from typing import Any

from django.conf import settings
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.users.serializers import (
    AuthCheckSerializer,
    CustomTokenObtainPairSerializer,
    RegisterSerializer,
)
from apps.users.throttles import LoginThrottle, RegisterThrottle


@extend_schema(
    summary="User Registration",
    description="Endpoint for registering a new user. Requires email, username, password, and password confirmation.",
    request=RegisterSerializer,
    responses={201: OpenApiResponse(
        description="User created successfully.",
        response=RegisterSerializer,
        ),
        400: OpenApiResponse(description="Bad request. Password validation failed or email/username already exists."),
    },
    examples=[
        OpenApiExample(
            "Request example",
            value={
                "email": "user@example.com",
                "username": "user1",
                "password": "StrongPass123",
            },
            request_only=True,
        ),
        OpenApiExample(
            "Response example",
            value={
                "id": 1,
                "email": "user@example.com",
                "username": "user1",
            },
            response_only=True,
        ),
    ],
    tags=['Authentication'],
)
class RegisterView(GenericAPIView):
    """User registration endpoint."""

    serializer_class = RegisterSerializer
    throttle_classes = [RegisterThrottle]
    permission_classes = [AllowAny]

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:  # noqa: ARG002
        """Registers a new user with the provided email, username, password.

        Returns:
            Response: HTTP 201 with user info if successful, HTTP 400 if validation fails.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        data = {
            "id": user.id,
            "email": user.email,
            "username": user.username,
        }
        return Response(data, status=status.HTTP_201_CREATED)


@extend_schema(
    summary="User Authentication (JWT Token Obtain)",
    description="Endpoint for obtaining JWT tokens. Requires email and password.",
    request=CustomTokenObtainPairSerializer,
    responses={200: OpenApiResponse(
        response=CustomTokenObtainPairSerializer,
        ),
        401: OpenApiResponse(description="No active account found with the given credentials."),
    },
    examples=[
        OpenApiExample(
            "Request example",
            value={
                "email": "user@example.com",
                "password": "StrongPass123",
            },
            request_only=True,
        ),
        OpenApiExample(
            "Response example",
            value={
                "access": "token_access_string",
                "user_id": 1,
                "email": "user@example.com",
                "role": "user",
            },
            response_only=True,
        ),
    ],
    tags=['Authentication'],
)
class CustomTokenObtainPairView(TokenObtainPairView):
    """Custom view for obtaining JWT tokens. Returns access token in JSON, sets refresh token as httponly cookie."""

    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [LoginThrottle]

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Returns access token in body and sets refresh token as httponly cookie.

        Returns:
            Response: response.
        """
        response = super().post(request, *args, **kwargs)
        refresh_token = response.data.pop('refresh', None)  # pyright: ignore[reportOptionalMemberAccess]
        if refresh_token:
            response.set_cookie(
                key='refresh_token',
                value=refresh_token,
                httponly=True,
                secure=settings.SESSION_COOKIE_SECURE,
                samesite='Lax',
                max_age=int(settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds()),
            )
        return response


@extend_schema(
    summary="User Logout",
    description="Endpoint for logging out a user and blacklisting their refresh token. "
    "Reads refresh token from httponly cookie.",
    request=None,
    responses={
        205: OpenApiResponse(description="Successfully logged out."),
        400: OpenApiResponse(description="Invalid or missing refresh token."),
        401: OpenApiResponse(description="Authentication credentials were not provided."),
    },
    tags=['Authentication'],
)
class LogoutView(GenericAPIView):
    """User logout endpoint that blacklists the refresh token stored in the httponly cookie."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:  # noqa: ARG002, PLR6301
        """Logs out the user by blacklisting the refresh token from the cookie.

        Returns:
            Response: HTTP 205 if successful, HTTP 400 if token is invalid.

        Raises:
            serializers.ValidationError: If the token is missing or invalid.
        """
        refresh_token = request.COOKIES.get('refresh_token')
        if not refresh_token:
            raise serializers.ValidationError({'detail': 'Refresh token not found.'})
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.exception("Error occurred while blacklisting refresh token")
            raise serializers.ValidationError({'detail': 'Invalid token.'}) from e
        else:
            response = Response(status=status.HTTP_205_RESET_CONTENT)
            response.delete_cookie('refresh_token')
            return response


@extend_schema(
    summary="Token Refresh",
    description="Endpoint for refreshing JWT tokens. Reads refresh token "
    "from httponly cookie, returns new access token in body and rotates refresh cookie.",
    request=None,
    responses={
        200: OpenApiResponse(description="New access token."),
        401: OpenApiResponse(description="Refresh token missing, invalid, or blacklisted."),
    },
    examples=[
        OpenApiExample(
            "Response example",
            value={"access": "token_access_string"},
            response_only=True,
        ),
    ],
    tags=['Authentication'],
)
class CustomTokenRefreshView(TokenRefreshView):
    """Reads refresh token from httponly cookie and returns a new access token in JSON."""

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:  # noqa: ARG002
        """Refreshes the access token using the refresh token stored in cookie.

        Raises:
            InvalidToken: If the refresh token is missing, invalid, or blacklisted.

        Returns:
            Response: HTTP 200 with new access token, or HTTP 401 if token is missing/invalid.
        """
        refresh_token = request.COOKIES.get('refresh_token')
        if not refresh_token:
            return Response({'detail': 'Refresh token not found.'}, status=status.HTTP_401_UNAUTHORIZED)

        serializer = self.get_serializer(data={'refresh': refresh_token})
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            raise InvalidToken(e.args[0]) from e

        response = Response({'access': serializer.validated_data['access']}, status=status.HTTP_200_OK)
        new_refresh = serializer.validated_data.get('refresh')
        if new_refresh:
            response.set_cookie(
                key='refresh_token',
                value=new_refresh,
                httponly=True,
                secure=settings.SESSION_COOKIE_SECURE,
                samesite='Lax',
                max_age=int(settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds()),
            )
        return response


@extend_schema(tags=['Authentication', 'Testing'])
class AuthCheckView(GenericAPIView):  # noqa: D101
    permission_classes = [IsAuthenticated]
    serializer_class = AuthCheckSerializer

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:  # noqa: PLR6301, D102, ARG002
        data = {
            "detail": "Authenticated",
            "user_id": request.user.id,
            "email": request.user.email,
        }
        return Response(data)
