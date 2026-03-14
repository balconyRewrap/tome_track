"""Views for the books app."""
import hashlib
import json
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.contrib.postgres.search import TrigramSimilarity
from django.core.cache import cache
from django.db.models import Avg, Count, Q, Value
from django.db.models.functions import Coalesce, Greatest
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

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

BOOKS_CACHE_PREFIX = 'books'
AUTHOR_CACHE_PREFIX = 'authors'
TAG_CACHE_PREFIX = 'tags'
SEARCH_CACHE_PREFIX = 'search'

BOOKS_CACHE_TTL = getattr(settings, 'BOOKS_CACHE_TTL', 60 * 5)  # 5 minutes
BOOKS_DETAIL_CACHE_TTL = getattr(settings, 'BOOKS_DETAIL_CACHE_TTL', 60 * 10)  # 10 min
AUTHOR_CACHE_TTL = getattr(settings, 'AUTHOR_CACHE_TTL', 60 * 60)  # 1 hour
TAG_CACHE_TTL = getattr(settings, 'TAG_CACHE_TTL', 60 * 60)  # 1 hour
SEARCH_CACHE_TTL = getattr(settings, 'SEARCH_CACHE_TTL', 60 * 3)  # 3 minutes


@extend_schema_view(
    list=extend_schema(
        summary='List books',
        description=(
            'Returns a paginated list of all books. Public endpoint, cached. '
            'Supports ordering via ?ordering=average_rating, -average_rating, '
            'ratings_count, -ratings_count, created_at, -created_at.'
        ),
        parameters=[
            OpenApiParameter(
                'ordering',
                str,
                description=(
                    'Sort results. Allowed values: average_rating, -average_rating, '
                    'ratings_count, -ratings_count, created_at, -created_at.'
                ),
            ),
        ],
        responses={200: BookSerializer(many=True)},
        tags=['Books'],
    ),
    retrieve=extend_schema(
        summary='Retrieve a book',
        description='Returns details of a single book by ID. Public endpoint, cached.',
        responses={
            200: BookSerializer,
            404: OpenApiResponse(description='Book not found.'),
        },
        tags=['Books'],
    ),
    create=extend_schema(
        summary='Create a book',
        description='Creates a new book. Requires authentication.',
        request=BookWriteSerializer,
        responses={
            201: BookWriteSerializer,
            400: OpenApiResponse(description='Validation error.'),
            401: OpenApiResponse(description='Authentication credentials were not provided.'),
        },
        examples=[
            OpenApiExample(
                'Request example',
                value={
                    'title': 'Dune',
                    'title_en': 'Dune',
                    'authors': [1],
                    'book_type': 'book',
                    'description': 'A sci-fi epic.',
                    'pages_total': 412,
                    'tags': [1, 2],
                    'country': 'US',
                },
                request_only=True,
            ),
        ],
        tags=['Books'],
    ),
    update=extend_schema(
        summary='Update a book',
        description='Fully replaces a book. Requires ownership or admin role.',
        request=BookWriteSerializer,
        responses={
            200: BookWriteSerializer,
            400: OpenApiResponse(description='Validation error.'),
            401: OpenApiResponse(description='Authentication credentials were not provided.'),
            403: OpenApiResponse(description='You do not have permission to perform this action.'),
            404: OpenApiResponse(description='Book not found.'),
        },
        tags=['Books'],
    ),
    partial_update=extend_schema(
        summary='Partially update a book',
        description='Updates one or more fields of a book. Requires ownership or admin role.',
        request=BookWriteSerializer,
        responses={
            200: BookWriteSerializer,
            400: OpenApiResponse(description='Validation error.'),
            401: OpenApiResponse(description='Authentication credentials were not provided.'),
            403: OpenApiResponse(description='You do not have permission to perform this action.'),
            404: OpenApiResponse(description='Book not found.'),
        },
        tags=['Books'],
    ),
    destroy=extend_schema(
        summary='Delete a book',
        description='Permanently deletes a book. Requires ownership or admin role.',
        responses={
            204: OpenApiResponse(description='Book deleted successfully.'),
            401: OpenApiResponse(description='Authentication credentials were not provided.'),
            403: OpenApiResponse(description='You do not have permission to perform this action.'),
            404: OpenApiResponse(description='Book not found.'),
        },
        tags=['Books'],
    ),
)
class BookViewSet(ActionPermissionsMixin, viewsets.ModelViewSet):
    """BookViewSet provides CRUD operations for books.

    List and retrieve are public and cached, while create, update, partial_update
    and destroy require authentication and appropriate permissions.
    Cache is invalidated on create, update and destroy.
    """

    queryset = Book.objects.select_related('parent_book', 'user').prefetch_related('authors', 'tags').annotate(
        average_rating=Coalesce(
            Avg('userbooks__rating', filter=Q(userbooks__rating__isnull=False)),
            Value(Decimal(0)),
        ),
        ratings_count=Count('userbooks__rating', filter=Q(userbooks__rating__isnull=False)),
    ).order_by('id')
    serializer_class = BookSerializer
    # MultiPartParser + FormParser are required for file (cover image) uploads.
    # JSONParser is kept so that requests without a file still work normally.
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = BookFilter
    ordering_fields = ['average_rating', 'ratings_count', 'created_at']
    ordering = ['id']
    permission_classes_by_action = {
        'list': [AllowAny],
        'retrieve': [AllowAny],
        'search': [AllowAny],
        'create': [IsAuthenticated],
        'update': [IsOwnerOrAdmin],
        'partial_update': [IsOwnerOrAdmin],
        'destroy': [IsOwnerOrAdmin],
    }

    def get_serializer_class(self) -> BookSerializer:  # pyright: ignore[reportIncompatibleMethodOverride]
        """Return serializer based on action.

        Create, update or partial_update - BookWriteSerializer, otherwise Bookserializer.

        Returns:
            serializer (BookSerializer)
        """
        if self.action in {'create', 'update', 'partial_update'}:
            return BookWriteSerializer  # pyright: ignore[reportReturnType]

        # pyright somehow complains that the return type is not compatible with the declared return type of
        # BookSerializer, even though it clearly is. So we ignore the type check here.
        return BookSerializer  # pyright: ignore[reportReturnType]

    @method_decorator(cache_page(BOOKS_CACHE_TTL, key_prefix=BOOKS_CACHE_PREFIX))
    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """List books. Public endpoint, cached.

        Returns:
            Response: Paginated list of books.
        """
        return super().list(request, *args, **kwargs)

    @method_decorator(cache_page(BOOKS_DETAIL_CACHE_TTL, key_prefix=BOOKS_CACHE_PREFIX))
    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Retrieve a book by ID. Public endpoint, cached.

        Returns:
            Response: The requested book.
        """
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary='Search books',
        description=(
            'Search books by title with trigram similarity (supports typos). '
            'Combine with author, tag, book_type, and country filters. '
            'Omitting q returns all books. Results are cached for 3 minutes.'
        ),
        parameters=[
            OpenApiParameter('q', str, description='Search query — supports typos via trigram similarity.'),
            OpenApiParameter('author', int, many=True, description='Filter by author ID (repeatable).'),
            OpenApiParameter('tag', int, many=True, description='Filter by tag ID (repeatable).'),
            OpenApiParameter('book_type', str, description='Filter by book type (book / comic).'),
            OpenApiParameter('country', str, description='Filter by country (case-insensitive contains).'),
            OpenApiParameter(
                'ordering',
                str,
                description=(
                    'Sort results. Allowed values: average_rating, -average_rating, '
                    'ratings_count, -ratings_count, created_at, -created_at. '
                    'When q is set, defaults to trigram similarity.'
                ),
            ),
        ],
        responses={200: BookSerializer(many=True)},
        tags=['Books'],
    )
    @action(detail=False, methods=['get'])
    def search(self, request: Request) -> Response:
        """Search books by title (trigram) with optional filters. Public, cached.

        Returns:
            Response: Paginated list of matching books.
        """
        q = request.query_params.get('q', '').strip()

        params = dict(sorted(request.query_params.items()))
        cache_key = f'{SEARCH_CACHE_PREFIX}:{hashlib.sha256(json.dumps(params).encode()).hexdigest()}'

        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        qs = Book.objects.select_related('parent_book', 'user').prefetch_related('authors', 'tags').annotate(
            average_rating=Coalesce(
                Avg('userbooks__rating', filter=Q(userbooks__rating__isnull=False)),
                Value(Decimal(0)),
            ),
            ratings_count=Count('userbooks__rating', filter=Q(userbooks__rating__isnull=False)),
        )

        if q:
            qs = qs.annotate(
                similarity=Greatest(
                    TrigramSimilarity('title', q),
                    TrigramSimilarity('title_en', q),
                ),
            ).filter(similarity__gte=0.2).order_by('-similarity')
        else:
            qs = qs.order_by('id')

        book_filter = BookFilter(request.query_params, queryset=qs)
        if not book_filter.is_valid():
            return Response(book_filter.errors, status=400)
        qs = book_filter.qs
        if 'ordering' in request.query_params:
            qs = OrderingFilter().filter_queryset(self.request, qs, self)

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = BookSerializer(page, many=True, context={'request': request})
            result = self.get_paginated_response(serializer.data)
            cache.set(cache_key, result.data, SEARCH_CACHE_TTL)
            return result

        serializer = BookSerializer(qs, many=True, context={'request': request})
        data = serializer.data
        cache.set(cache_key, data, SEARCH_CACHE_TTL)
        return Response(data)

    def perform_create(self, serializer: BookSerializer) -> None:
        """Create a book. Invalidate books and search cache."""
        serializer.save(user=self.request.user)
        self._invalidate_book_cache()

    def perform_update(self, serializer: BookSerializer) -> None:
        """Update a book. Invalidate books and search cache."""
        serializer.save()
        self._invalidate_book_cache()

    def perform_destroy(self, instance: Book) -> None:
        """Destroy a book. Invalidate books and search cache."""
        self._invalidate_book_cache()
        return super().perform_destroy(instance)

    def _invalidate_book_cache(self) -> None:  # noqa: PLR6301
        """Helper to invalidate books cache."""
        invalidate_cache_prefix(BOOKS_CACHE_PREFIX)
        invalidate_cache_by_key_prefix(SEARCH_CACHE_PREFIX)


@extend_schema_view(
    list=extend_schema(
        summary='List authors',
        description='Returns a paginated list of all authors. Public endpoint, cached.',
        responses={200: AuthorSerializer(many=True)},
        tags=['Authors'],
    ),
    retrieve=extend_schema(
        summary='Retrieve an author',
        description='Returns details of a single author by ID. Public endpoint, cached.',
        responses={
            200: AuthorSerializer,
            404: OpenApiResponse(description='Author not found.'),
        },
        tags=['Authors'],
    ),
    create=extend_schema(
        summary='Create an author',
        description='Creates a new author. Requires authentication.',
        responses={
            201: AuthorSerializer,
            400: OpenApiResponse(description='Validation error.'),
            401: OpenApiResponse(description='Authentication credentials were not provided.'),
        },
        tags=['Authors'],
    ),
    destroy=extend_schema(
        summary='Delete an author',
        description='Permanently deletes an author. Requires admin role.',
        responses={
            204: OpenApiResponse(description='Author deleted successfully.'),
            401: OpenApiResponse(description='Authentication credentials were not provided.'),
            403: OpenApiResponse(description='You do not have permission to perform this action.'),
            404: OpenApiResponse(description='Author not found.'),
        },
        tags=['Authors'],
    ),
)
class AuthorViewSet(ActionPermissionsMixin, viewsets.ModelViewSet):
    """AuthorViewSet provides CRUD operations for authors.

    List and retrieve are public and cached, while create and destroy require authentication and appropriate permissions
    Cache is invalidated on create and destroy.
    """

    queryset = Author.objects.all().order_by('id')
    serializer_class = AuthorSerializer
    permission_classes_by_action = {
        'list': [AllowAny],
        'retrieve': [AllowAny],
        'create': [IsAuthenticated],
        'destroy': [IsAdminRole],
    }

    @method_decorator(cache_page(AUTHOR_CACHE_TTL, key_prefix=AUTHOR_CACHE_PREFIX))
    def list(self, request: Request, *args, **kwargs):  # noqa: ANN201, ANN002, ANN003
        """List authors. Public endpoint, cached.

        Returns:
            Response: Paginated list of authors.
        """
        return super().list(request, *args, **kwargs)

    @method_decorator(cache_page(AUTHOR_CACHE_TTL, key_prefix=AUTHOR_CACHE_PREFIX))
    def retrieve(self, request: Request, *args, **kwargs):  # noqa: ANN201, ANN002, ANN003
        """Retrieve an author by ID. Public endpoint, cached.

        Returns:
            Response: The requested author.
        """
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer: AuthorSerializer) -> None:  # noqa: PLR6301
        """Create an author. Invalidate authors cache."""
        serializer.save()
        invalidate_cache_prefix(AUTHOR_CACHE_PREFIX)

    def perform_destroy(self, instance) -> None:  # noqa: ANN001
        """Destroy an author. Invalidate authors cache."""
        invalidate_cache_prefix(AUTHOR_CACHE_PREFIX)
        return super().perform_destroy(instance)


@extend_schema_view(
    list=extend_schema(
        summary='List tags',
        description='Returns a paginated list of all tags. Public endpoint, cached.',
        responses={200: TagSerializer(many=True)},
        tags=['Tags'],
    ),
    retrieve=extend_schema(
        summary='Retrieve a tag',
        description='Returns details of a single tag by ID. Public endpoint, cached.',
        responses={
            200: TagSerializer,
            404: OpenApiResponse(description='Tag not found.'),
        },
        tags=['Tags'],
    ),
    create=extend_schema(
        summary='Create a tag',
        description='Creates a new tag. Requires admin role.',
        responses={
            201: TagSerializer,
            400: OpenApiResponse(description='Validation error.'),
            401: OpenApiResponse(description='Authentication credentials were not provided.'),
            403: OpenApiResponse(description='You do not have permission to perform this action.'),
        },
        tags=['Tags'],
    ),
    destroy=extend_schema(
        summary='Delete a tag',
        description='Permanently deletes a tag. Requires admin role.',
        responses={
            204: OpenApiResponse(description='Tag deleted successfully.'),
            401: OpenApiResponse(description='Authentication credentials were not provided.'),
            403: OpenApiResponse(description='You do not have permission to perform this action.'),
            404: OpenApiResponse(description='Tag not found.'),
        },
        tags=['Tags'],
    ),
)
class TagViewSet(ActionPermissionsMixin, viewsets.ModelViewSet):
    """TagViewSet provides CRUD operations for tags.

    List and retrieve are public and cached, while create and destroy require authentication and appropriate permissions
    Cache is invalidated on create and destroy.
    """

    queryset = Tag.objects.all().order_by('id')
    serializer_class = TagSerializer
    permission_classes_by_action = {
        'list': [AllowAny],
        'retrieve': [AllowAny],
        'create': [IsAdminRole],
        'destroy': [IsAdminRole],
    }

    @method_decorator(cache_page(TAG_CACHE_TTL, key_prefix=TAG_CACHE_PREFIX), name='dispatch')
    def list(self, request: Request, *args, **kwargs):  # noqa: ANN201, ANN002, ANN003
        """List tags. Public endpoint, cached.

        Returns:
            Response: Paginated list of tags.
        """
        return super().list(request, *args, **kwargs)

    @method_decorator(cache_page(TAG_CACHE_TTL, key_prefix=TAG_CACHE_PREFIX), name='dispatch')
    def retrieve(self, request: Request, *args, **kwargs):  # noqa: ANN201, ANN002, ANN003
        """Retrieve a tag by ID. Public endpoint, cached.

        Returns:
            Response: The requested tag.
        """
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer: TagSerializer) -> None:  # noqa: PLR6301
        """Create a tag. Invalidate tags cache."""
        serializer.save()
        invalidate_cache_prefix(TAG_CACHE_PREFIX)

    def perform_destroy(self, instance) -> None:  # noqa: ANN001
        """Destroy a tag. Invalidate tags cache."""
        invalidate_cache_prefix(TAG_CACHE_PREFIX)
        return super().perform_destroy(instance)
