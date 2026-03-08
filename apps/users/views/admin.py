"""Admin views for user app."""
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import filters, viewsets
from rest_framework.permissions import IsAuthenticated

from apps.common.permissions import IsAdminRole
from apps.users.models import User
from apps.users.serializers import (
    AdminUserSerializer,
)


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
                    {
                        "id": 1,
                        "email": "admin@example.com",
                        "username": "admin",
                        "role": "admin",
                        "is_active": True,
                        "created_at": "2024-01-01T12:00:00Z",
                    },
                    {
                        "id": 2,
                        "email": "user@example.com",
                        "username": "user",
                        "role": "user",
                        "is_active": True,
                        "created_at": "2024-01-02T12:00:00Z",
                    },
                ],
            },
            response_only=True,
        ),
        OpenApiExample(
            "User detail example",
            value={
                "id": 1,
                "email": "admin@example.com",
                "username": "admin",
                "role": "admin",
                "is_active": True,
                "created_at": "2024-01-01T12:00:00Z",
            },
            response_only=True,
        ),
    ],
)
class AdminUserViewSet(viewsets.ModelViewSet):
    """ViewSet for admin management of users.

    Provides list, retrieve, update, and delete operations on User model.
    Only accessible by admin users.
    """

    queryset = User.objects.all().order_by('id')
    serializer_class = AdminUserSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    filterset_fields = ['role', 'is_active']
    search_fields = ['email', 'username']
