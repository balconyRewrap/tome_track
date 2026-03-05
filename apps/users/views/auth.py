"""Authentication views for user registration, login, logout, and token refresh."""
import logging

from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.users.serializers import (
    AuthCheckSerializer,
    CustomTokenObtainPairSerializer,
    LogoutSerializer,
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
    throttle_classes = [RegisterThrottle]  # noqa: RUF012
    permission_classes = [AllowAny]  # noqa: RUF012

    def post(self, request: Request, *args, **kwargs) -> Response:  # noqa: ARG002, ANN002, ANN003
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
                "refresh": "token_refresh_string",
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
    """Custom view for obtaining JWT tokens that uses a custom serializer to include user role in the token payload."""

    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [LoginThrottle]  # noqa: RUF012


@extend_schema(
    summary="User Logout",
    description="Endpoint for logging out a user and blacklisting their refresh token.",
    request=LogoutSerializer,
    responses={205: OpenApiResponse(
        response=LogoutSerializer,
        ),
        400: OpenApiResponse(description="Invalid token."),
        401: OpenApiResponse(description="Authentication credentials were not provided."),
    },
    examples=[
        OpenApiExample(
            "Request example",
            value={
                "refresh": "token_refresh_string",
            },
            request_only=True,
        ),
        OpenApiExample(
            "Response example",
            response_only=True,
        ),
    ],
    tags=['Authentication'],
)
class LogoutView(GenericAPIView):
    """User logout endpoint that blacklists the refresh token."""

    permission_classes = [IsAuthenticated]  # noqa: RUF012
    serializer_class = LogoutSerializer

    def post(self, request: Request, *args, **kwargs) -> Response:  # noqa: ARG002, ANN002, ANN003
        """Logs out the user by blacklisting the provided refresh token.

        Returns:
            Response: HTTP 205 if successful, HTTP 400 if token is invalid.

        Raises:
            serializers.ValidationError: If the provided token is invalid.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        refresh_token = serializer.validated_data["refresh"]
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.exception("Error occurred while blacklisting refresh token")
            raise serializers.ValidationError({"refresh": "Invalid token."}) from e


# Used only for tagging in API docs
@extend_schema(
    summary="Token Refresh",
    description="Endpoint for refreshing JWT tokens. Requires refresh token.",
    responses={200: OpenApiResponse(),
        401: OpenApiResponse(description="Token is blacklisted"),
    },
    examples=[
        OpenApiExample(
            "Request example",
            value={
                "refresh": "token_refresh_string",
            },
            request_only=True,
        ),
        OpenApiExample(
            "Response example",
            value={
                "refresh": "token_refresh_string",
                "access": "token_access_string",
            },
            response_only=True,
        ),
    ],
    tags=['Authentication'],
)
class CustomTokenRefreshView(TokenRefreshView):  # noqa: D101
    pass


@extend_schema(tags=['Authentication'])
class AuthCheckView(GenericAPIView):  # noqa: D101
    permission_classes = [IsAuthenticated]  # noqa: RUF012
    serializer_class = AuthCheckSerializer

    def get(self, request, *args, **kwargs):  # noqa: ANN201, ANN001, ANN002, ANN003, ARG002, PLR6301, D102
        data = {
            "detail": "Authenticated",
            "user_id": request.user.id,
            "email": request.user.email,
        }
        return Response(data)
