from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import filters, serializers, status, viewsets
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.users.models import User
from apps.users.permissions import IsAdminRole
from apps.users.serializers import (
    AdminUserSerializer,
    CustomTokenObtainPairSerializer,
    LogoutSerializer,
    RegisterSerializer,
)
from apps.users.throttles import LoginThrottle, RegisterThrottle


@extend_schema(
    tags=["Admin"],
    summary="Admin user management",
    description="list all users or retrieve/update a specific user. Only accessible by admin users.",
    responses={
        200: AdminUserSerializer,
        201: AdminUserSerializer,
        400: OpenApiResponse(description="Bad request"),
        403: OpenApiResponse(description="Forbidden"),
        404: OpenApiResponse(description="Not found"),
    },
    examples=[
        OpenApiExample(
            "User list example",
            value={
                "count": 2,
                "results": [
                    {"id": 1, "email": "admin@example.com", "username": "admin", "role": "admin", "is_active": 'true', "created_at": "2024-01-01T12:00:00Z"},
                    {"id": 2, "email": "user@example.com", "username": "user", "role": "user", "is_active": 'true', "created_at": "2024-01-02T12:00:00Z"}
                ],
            },
            response_only=True,
        ),
        OpenApiExample(
            "User detail example",
            value={"id": 1, "email": "admin@example.com", "username": "admin", "role": "admin", "is_active": 'true', "created_at": "2024-01-01T12:00:00Z"},
            response_only=True,
        ),
    ],
)
class AdminUserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by('id')
    serializer_class = AdminUserSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]  # noqa: RUF012
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]  # noqa: RUF012
    filterset_fields = ['role', 'is_active']  # noqa: RUF012
    search_fields = ['email', 'username']  # noqa: RUF012
