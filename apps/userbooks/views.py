"""Views for UserBook model, including caching and permissions."""
from collections.abc import Callable
from typing import Any

from django.conf import settings
from django.db.models import QuerySet
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.cache_utils import cache_response, invalidate_cache_by_key_prefix
from apps.common.mixins import ActionPermissionsMixin
from apps.common.permissions import IsOwnerOrAdmin
from apps.userbooks.filters import UserBookFilter
from apps.userbooks.models import UserBook
from apps.userbooks.serializers import UserBookSerializer, UserBookUpdateSerializer, UserBookWriteSerializer

USERBOOKS_CACHE_TTL = getattr(settings, 'USERBOOKS_CACHE_TTL', 60 * 60)
USERBOOKS_DETAIL_CACHE_TTL = getattr(settings, 'USERBOOKS_DETAIL_CACHE_TTL', 60 * 120)

# books cache won't be invalidated when userbook with rating created, updated or deleted
# because TTL of book already small, so calculating average rating on the fly is not a problem.
# But userbooks cache should be invalidated immediately when userbook is created, updated or deleted,
# so we can set shorter TTL for userbooks cache.
# Also, book cache can be shared among all users, so we can set longer TTL for books cache.
# But userbooks cache is per-user, so it should be invalidated immediately when userbook is created, updated or deleted,
# so we can set shorter TTL for userbooks cache.  Also, book cache can be shared among all users,


def userbook_cache_key(
    view_instance: "UserBookViewSet",  # noqa: ARG001
    view_method: Callable,
    request: Request,
    *args: Any,  # noqa: ARG001
    **kwargs: Any,  # noqa: ARG001
) -> str:
    """Return a cache key for userbooks list and detail views, based on user ID and view method.

    Returns:
        str: The cache key for the userbooks list or detail view.
    """
    return f"userbooks:user:{request.user.pk}:{view_method.__name__}"


@extend_schema_view(
    list=extend_schema(
        summary='List user books',
        description='Returns a paginated list of the current user\'s books. Cached per user.',
        responses={200: UserBookSerializer(many=True)},
        tags=['UserBooks'],
    ),
    retrieve=extend_schema(
        summary='Retrieve a user book',
        description='Returns details of a single UserBook by ID. Requires ownership or admin role.',
        responses={
            200: UserBookSerializer,
            404: OpenApiResponse(description='UserBook not found.'),
        },
        tags=['UserBooks'],
    ),
    create=extend_schema(
        summary='Add a book to user list',
        description='Creates a new UserBook entry for the current user.',
        request=UserBookWriteSerializer,
        responses={
            201: UserBookWriteSerializer,
            400: OpenApiResponse(description='Validation error.'),
            401: OpenApiResponse(description='Authentication credentials were not provided.'),
        },
        tags=['UserBooks'],
    ),
    update=extend_schema(exclude=True),
    partial_update=extend_schema(
        summary='Update a user book',
        description='Partially updates a UserBook entry. The book field cannot be changed.',
        request=UserBookUpdateSerializer,
        responses={
            200: UserBookUpdateSerializer,
            400: OpenApiResponse(description='Validation error.'),
            401: OpenApiResponse(description='Authentication credentials were not provided.'),
            403: OpenApiResponse(description='You do not have permission to perform this action.'),
            404: OpenApiResponse(description='UserBook not found.'),
        },
        tags=['UserBooks'],
    ),
    destroy=extend_schema(
        summary='Delete a user book',
        description='Removes a UserBook entry. Requires ownership or admin role.',
        responses={
            204: OpenApiResponse(description='UserBook deleted successfully.'),
            401: OpenApiResponse(description='Authentication credentials were not provided.'),
            403: OpenApiResponse(description='You do not have permission to perform this action.'),
            404: OpenApiResponse(description='UserBook not found.'),
        },
        tags=['UserBooks'],
    ),
)
class UserBookViewSet(ActionPermissionsMixin, viewsets.ModelViewSet):
    """ViewSet for managing UserBook relationships."""

    http_method_names = ['get', 'post', 'patch', 'delete']
    queryset = UserBook.objects.select_related('book', 'user').all().order_by('id')
    serializer_class = UserBookSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = UserBookFilter
    permission_classes_by_action = {
        'list': [IsAuthenticated],
        'create': [IsAuthenticated],
        'retrieve': [IsOwnerOrAdmin],
        'update': [IsOwnerOrAdmin],
        'partial_update': [IsOwnerOrAdmin],
        'destroy': [IsOwnerOrAdmin],
    }

    def get_serializer_class(self) -> UserBookSerializer:  # pyright: ignore[reportIncompatibleMethodOverride]
        """Return the appropriate serializer class based on the action.

        Create, update or partial_update - UserBookWriteSerializer, otherwise - UserBookSerializer.

        Returns:
            serializer (UserBookSerializer)
        """
        if self.action == 'create':
            # check apps/books/views.py for these ignores.
            return UserBookWriteSerializer  # pyright: ignore[reportReturnType]
        if self.action == 'partial_update':
            return UserBookUpdateSerializer  # pyright: ignore[reportReturnType]
        return UserBookSerializer  # pyright: ignore[reportReturnType]

    # queryset isn't Never by default, pyright is wrong.
    def get_queryset(self) -> QuerySet[UserBook]:  # pyright: ignore[reportIncompatibleMethodOverride]
        """Override of get_queryset to filter by user by default.

        So, user can only see their own UserBook objects, unless they are admin,
        then they can see all.

        Returns:
            QuerySet: the queryset of UserBook objects for the current user or all if admin.
        """
        if self.request.user.is_authenticated and self.request.user.role == 'admin':
            return UserBook.objects.all()

        return UserBook.objects.filter(user=self.request.user).order_by('id')

    # pyright is ignored, because cache_response decorator changes the signature of the method
    # but we know that it will still return Response.
    @cache_response(timeout=USERBOOKS_CACHE_TTL, key_func=userbook_cache_key)
    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:  # pyright: ignore[reportIncompatibleMethodOverride]
        """List UserBook objects for the current user, cached.

        Returns:
            Response: A paginated list of UserBook objects.
        """
        return super().list(request, *args, **kwargs)

    @cache_response(timeout=USERBOOKS_CACHE_TTL, key_func=userbook_cache_key)
    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:  # pyright: ignore[reportIncompatibleMethodOverride]
        """Retrieve a UserBook object by ID, cached.

        Returns:
            Response: The details of the UserBook object.
        """
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer: UserBookSerializer) -> None:
        """Override perform_create to set the user and invalidate cache.

        After the object is saved we need to know whether it contains a
        ``rating`` so that book-level cache can be invalidated.  ``rating`` is
        always available on the returned instance, so inspect it directly.
        """
        serializer.save(user=self.request.user)
        self._invalidate_userbooks_cache()

    def perform_update(self, serializer: UserBookSerializer) -> None:
        """Update a UserBook, invalidate cache."""
        serializer.save()
        self._invalidate_userbooks_cache()

    def perform_destroy(self, instance: UserBook) -> None:
        """Delete a UserBook, invalidate cache."""
        self._invalidate_userbooks_cache()
        return super().perform_destroy(instance)

    def _invalidate_userbooks_cache(self) -> None:
        """Helper to invalidate userbooks cache."""
        invalidate_cache_by_key_prefix(f'userbooks:user:{self.request.user.pk}:')
