from typing import Any

from django.conf import settings
from django.contrib.postgres.search import TrigramSimilarity
from django.core.cache import cache
from django.db.models import Avg, Count, Q, QuerySet
from django.db.models.functions import Greatest
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_extensions.cache.decorators import cache_response
from apps.books.filters import BookFilter
from apps.books.models import Author, Book, Tag
from apps.books.serializers import (
    AuthorSerializer,
    BookSerializer,
    BookWriteSerializer,
    TagSerializer,
)
from apps.common.cache_utils import invalidate_cache_by_key_prefix, invalidate_cache_prefix
from apps.common.mixins import ActionPermissionsMixin
from apps.common.permissions import IsAdminRole, IsOwnerOrAdmin
from apps.userbooks.filters import UserBookFilter
from apps.userbooks.models import ReadingStatus, UserBook
from apps.userbooks.serializers import UserBookSerializer, UserBookWriteSerializer

USERBOOKS_CACHE_KEY_PREFIX = 'userbooks_list_user_'

USERBOOKS_CACHE_TTL = getattr(settings, 'USERBOOKS_CACHE_TTL', 60 * 60)
USERBOOKS_DETAIL_CACHE_TTL = getattr(settings, 'USERBOOKS_DETAIL_CACHE_TTL', 60 * 120)


class UserBookViewSet(ActionPermissionsMixin, viewsets.ModelViewSet):
    """ViewSet for managing UserBook relationships."""

    http_method_names = ['get', 'post', 'patch', 'delete']
    queryset = UserBook.objects.select_related('book', 'user').all()
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
        if self.action in {'create', 'partial_update'}:
            # check apps/books/views.py for these ignores.
            return UserBookWriteSerializer  # pyright: ignore[reportReturnType]
        return UserBookSerializer  # pyright: ignore[reportReturnType]

    # queryset isn't Never by default, pyright is wrong.
    def get_queryset(self) -> QuerySet[UserBook]:  # pyright: ignore[reportIncompatibleMethodOverride]
        """Override of get_queryset to filter by user by default.

        So, user can only see their own UserBook objects, unless they are admin,
        then they can see all.

        Returns:
            QuerySet: the queryset of UserBook objects for the current user or all if admin.
        """
        if self.request.user.is_staff:
            return UserBook.objects.all()

        return UserBook.objects.filter(user=self.request.user)

    @method_decorator(cache_page(settings.USERBOOKS_CACHE_TTL, key_prefix=USERBOOKS_CACHE_KEY_PREFIX))
    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """List UserBook objects for the current user, cached.

        Returns:
            Response: A paginated list of UserBook objects.
        """
        return super().list(request, *args, **kwargs)

    @method_decorator(cache_page(settings.USERBOOKS_DETAIL_CACHE_TTL, key_prefix=USERBOOKS_CACHE_KEY_PREFIX))
    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Retrieve a UserBook object by ID, cached.

        Returns:
            Response: The details of the UserBook object.
        """
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer: UserBookSerializer) -> None:
        """Override perform_create to set the user and invalidate cache."""
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

    def _invalidate_userbooks_cache(self) -> None:  # noqa: PLR6301
        """Helper to invalidate userbooks cache."""
        invalidate_cache_prefix(USERBOOKS_CACHE_KEY_PREFIX)