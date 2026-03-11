"""Views for user profile and password reset."""
import uuid
from typing import Any

from django.contrib.auth.models import AbstractUser, AnonymousUser
from django.utils import timezone
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import generics, serializers, status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.users.models import PasswordResetToken, User
from apps.users.serializers import (
    ChangeEmailSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetSerializer,
    UserProfileSerializer,
)
from apps.users.tasks import send_password_reset_email
from apps.users.throttles import PasswordResetThrottle


@extend_schema(
    summary="User Profile",
    description="Endpoint for retrieving and updating the authenticated user's profile information.",
    responses={
        405: OpenApiResponse(description="Method PUT not allowed."),
    },
    tags=['Users'],
)
class UserMeView(generics.RetrieveUpdateAPIView):
    """Endpoint for retrieving the authenticated user's profile information."""

    permission_classes = [IsAuthenticated]
    serializer_class = UserProfileSerializer

    # Override PUT method to return 405. Doesn't make anything else
    def put(self, request, *args, **kwargs):  # noqa: ARG002, ANN003, ANN002, ANN001, ANN201, PLR6301
        """Override PUT method to return 405 Method Not Allowed since we only allow GET and PATCH.

        Returns:
            Response: A response with status 405 Method Not Allowed.
        """
        return Response({"detail": "Method PUT not allowed."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    @property
    def allowed_methods(self) -> list[str]:
        """Override allowed methods to only allow GET and PATCH."""
        return ['GET', 'PATCH']

    @extend_schema(
        summary="Get user profile",
        description="Returns the profile information of the authenticated user.",
        responses={
            200: OpenApiResponse(UserProfileSerializer,
                                 description="User profile retrieved successfully.",
            ),
            401: OpenApiResponse(description="Authentication credentials were not provided."),
        },
        examples=[
            OpenApiExample(
                "Response example",
                value={
                    "id": 1,
                    "email": "user@example.com",
                    "username": "user1",
                    "role": "user",
                },
                response_only=True,
            ),
        ],
    )
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Get the profile information of the authenticated user. Used for adding OpenAPI schema.

        Returns:
            Response: The response from the original get method.
        """
        return super().get(request, *args, **kwargs)

    def get_object(self) -> AbstractUser | AnonymousUser:  # pyright: ignore[reportIncompatibleMethodOverride]
        """Override get_object to return the authenticated user.

        Returns:
            users.model.user: the user of the request.
        """
        return self.request.user

    @extend_schema(
        summary="Change username",
        description="Updates the username of the authenticated user.",
        responses={
            200: OpenApiResponse(UserProfileSerializer,
                                 description="User profile updated successfully.",
            ),
            400: OpenApiResponse(description="User with this username already exists."),
            401: OpenApiResponse(description="Authentication credentials were not provided."),
        },
        examples=[
            OpenApiExample(
                "Request example",
                value={
                    "username": "user1",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Response example",
                value={
                    "id": 1,
                    "email": "user@example.com",
                    "username": "user1",
                    "role": "user",
                },
                response_only=True,
            ),
        ],
    )
    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Method is overriden just to add OpenAPI schema.

        Returns:
            Response: The response from the original patch method.
        """
        return super().patch(request, *args, **kwargs)


@extend_schema(
    summary="Change user email",
    description="Endpoint for changing the authenticated user's email address. "
    "Requires the new email and current password for verification.",
    request=ChangeEmailSerializer,
    responses={
        200: OpenApiResponse(
            response=ChangeEmailSerializer,
            description="Email updated successfully.",
        ),
        400: OpenApiResponse(
            description="Validation error. New email is the same as current or already exists, or "
            "incorrect password provided.",
        ),
        401: OpenApiResponse(description="Authentication credentials were not provided or Token is no longer valid."),
    },
    examples=[
        OpenApiExample(
            "Request example",
            value={
                "new_email": "newemail@example.com",
                "password": "StrongPass123",
            },
            request_only=True,
        ),
        OpenApiExample(
            "Response example",
            value={
                "detail": "Email updated successfully.",
            },
            response_only=True,
        ),
    ],
    tags=['Users'],
)
class ChangeEmailView(GenericAPIView):
    """Endpoint for changing the authenticated user's email."""

    permission_classes = [IsAuthenticated]
    serializer_class = ChangeEmailSerializer

    def post(self, request: Request) -> Response:
        """Post method for changing the authenticated user's email.

        Returns:
            Response:
                A response with status 200 OK if email was updated successfully, or 400 Bad Request if validation failed
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        user.email = serializer.validated_data['new_email']
        user.token_version += 1
        user.save()
        return Response({"detail": "Email updated successfully."}, status=status.HTTP_200_OK)


@extend_schema(
    summary="Reset Password Request",
    description="Endpoint for requesting a password reset. "
    "The user provides their email, and if it exists, a password reset token is generated and emailed to them.",
    request=PasswordResetSerializer,
    responses={
        200: OpenApiResponse(
            response=PasswordResetSerializer,
            description="Request accepted. If the email exists, a reset link has been sent.",
        ),
    },
    examples=[
        OpenApiExample(
            "Request example",
            value={
                "email": "user@example.com",
            },
            request_only=True,
        ),
        OpenApiExample(
            "Response example",
            value={
                "detail": "If an account with that email exists, a password reset link has been sent.",
            },
            response_only=True,
        ),
    ],
    tags=['Users'],
)
class PasswordResetView(GenericAPIView):
    """Endpoint for requesting a password reset.

    The user provides their email, and if it exists, a password reset token is generated and emailed to them.
    """

    permission_classes = [AllowAny]
    serializer_class = PasswordResetSerializer
    throttle_classes = [PasswordResetThrottle]

    def post(self, request: Request) -> Response:
        """Post method for requesting a password reset.

        Returns:
            Response:
                A response with status 200 OK. Always returns the same message to avoid
                leaking whether an account with the given email exists.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        user = User.objects.filter(email=email).first()
        if user:
            token = uuid.uuid4().hex
            PasswordResetToken.objects.create(user=user, token=token)
            send_password_reset_email.delay(user.email, token)
        return Response(
            {"detail": "If an account with that email exists, a password reset link has been sent."},
            status=status.HTTP_200_OK,
        )


@extend_schema(
    summary="Confirm password reset",
    description="Endpoint for confirming a password reset. The user provides password reset token and a new password."
    "If the token is valid and not expired, the user's password is updated.",
     request=PasswordResetConfirmSerializer,
    responses={
        200: OpenApiResponse(
            response=PasswordResetConfirmSerializer,
            description="Password has been reset successfully.",
        ),
        400: OpenApiResponse(description="Invalid or expired confirm token, or new password validation failed."),
    },
    examples=[
        OpenApiExample(
            "Request example",
            value={
                "token": "reset_token_from_email",
                "new_password": "NewStrongPass123",
            },
            request_only=True,
        ),
        OpenApiExample(
            "Response example",
            value={
                "detail": "Password has been reset successfully.",
            },
            response_only=True,
        ),
    ],
    tags=['Users'],
)
class PasswordResetConfirmView(GenericAPIView):
    """Endpoint for confirming a password reset.

    The user provides the password reset token and a new password. If the token is valid and not expired, the user's
    password is updated.
    """

    permission_classes = [AllowAny]
    serializer_class = PasswordResetConfirmSerializer
    throttle_classes = [PasswordResetThrottle]

    def post(self, request: Request) -> Response:
        """Post method for confirming a password reset.

        Returns:
            Response:
                A response with status 200 OK if the password was reset successfully,
                or 400 Bad Request if validation failed.

        Raises:
            serializers.ValidationError: If the provided token is invalid or expired,
            or if the new password validation failed.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reset_token_uuid = serializer.validated_data["token"]
        new_password = serializer.validated_data["new_password"]
        reset_token = PasswordResetToken.objects.filter(token=reset_token_uuid, used=False).first()

        if not self._is_reset_token_valid(reset_token):
            raise serializers.ValidationError({"token": "Invalid or expired token."})
        user = reset_token.user
        user.set_password(new_password)
        user.token_version += 1
        user.save()
        reset_token.used = True
        reset_token.save()
        return Response({"detail": "Password has been reset successfully."}, status=status.HTTP_200_OK)

    def _is_reset_token_valid(self, reset_token: PasswordResetToken) -> bool:  # noqa: PLR6301
        """Check if the provided password reset token is valid.

        Args:
            reset_token (PasswordResetToken): The password reset token to check.

        Returns:
            bool: True if the token is valid, False otherwise.
        """
        if not reset_token:
            return False
        return not reset_token.created_at < timezone.now() - timezone.timedelta(hours=1)


@extend_schema(
    summary="Change user password",
    description="Endpoint for changing the authenticated user's password. "
    "Requires the current password for verification.",
    request=PasswordChangeSerializer,
    responses={
        200: OpenApiResponse(
            response=PasswordChangeSerializer,
            description="Password updated successfully.",
        ),
        400: OpenApiResponse(
            description="Validation error. Incorrect current password or new password validation failed."),
        401: OpenApiResponse(description="Authentication credentials were not provided or Token is no longer valid."),
    },
    examples=[
        OpenApiExample(
            "Request example",
            value={
                "current_password": "StrongPass123",
                "new_password": "NewStrongPass123",
            },
            request_only=True,
        ),
        OpenApiExample(
            "Response example",
            value={
                "detail": "Password updated successfully.",
            },
            response_only=True,
        ),
    ],
    tags=['Users'],
)
class PasswordChangeView(GenericAPIView):
    """Endpoint for changing the authenticated user's password."""

    permission_classes = [IsAuthenticated]
    serializer_class = PasswordChangeSerializer

    def post(self, request: Request) -> Response:
        """Post method for changing the authenticated user's password.

        Returns:
            Response:
                A response with status 200 OK if the password was changed successfully,
                or 400 Bad Request if validation failed.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.token_version += 1
        user.save()
        return Response({"detail": "Password updated successfully."}, status=status.HTTP_200_OK)
