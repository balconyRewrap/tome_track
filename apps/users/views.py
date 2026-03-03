from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from apps.users.serializers import RegisterSerializer
from apps.users.throttles import RegisterThrottle


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
                "password_confirm": "StrongPass123",
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

    def post(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        data = {
            "id": user.id,
            "email": user.email,
            "username": user.username,
        }
        return Response(data, status=status.HTTP_201_CREATED)