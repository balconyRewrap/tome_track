"""Views for the books app."""
from django.conf import settings
from django.db.models import Avg, Count, Q
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request

from apps.books.models import Author, Book, Tag
from apps.books.serializers import (
    AuthorSerializer,
    BookSerializer,
    # BookUpdateSerializer,
    BookWriteSerializer,
    TagSerializer,
)
from apps.common.mixins import ActionPermissionsMixin
from apps.common.permissions import IsAdminRole, IsOwnerOrAdmin
from apps.common.utils import invalidate_cache_prefix

BOOKS_CACHE_PREFIX = 'books'
AUTHOR_CACHE_PREFIX = 'authors'
TAG_CACHE_PREFIX = 'tags'


@extend_schema_view(
    list=extend_schema(
        summary='List books',
        description='Returns a paginated list of all books. Public endpoint, cached.',
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
        request=BookSerializer,
        responses={
            201: BookSerializer,
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
        request=BookSerializer,
        responses={
            200: BookSerializer,
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
        request=BookSerializer,
        responses={
            200: BookSerializer,
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

    queryset = Book.objects.annotate(
        average_rating=Avg('userbooks__rating', filter=Q(userbooks__rating__isnull=False)),
        ratings_count=Count('userbooks__rating', filter=Q(userbooks__rating__isnull=False)),
    ).order_by('id')
    serializer_class = BookSerializer
    # MultiPartParser + FormParser are required for file (cover image) uploads.
    # JSONParser is kept so that requests without a file still work normally.
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    permission_classes_by_action = {
        'list': [AllowAny],
        'retrieve': [AllowAny],
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

    @method_decorator(cache_page(settings.BOOK_CACHE_TTL, key_prefix=BOOKS_CACHE_PREFIX))
    def list(self, request: Request, *args, **kwargs):  # noqa: ANN201, ANN002, ANN003
        """List books. Public endpoint, cached.

        Returns:
            Response: Paginated list of books.
        """
        return super().list(request, *args, **kwargs)

    @method_decorator(cache_page(settings.BOOK_CACHE_TTL, key_prefix=BOOKS_CACHE_PREFIX))
    def retrieve(self, request: Request, *args, **kwargs):  # noqa: ANN201, ANN002, ANN003
        """Retrieve a book by ID. Public endpoint, cached.

        Returns:
            Response: The requested book.
        """
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer: BookSerializer) -> None:
        """Create a book. Invalidate books cache."""
        serializer.save(user=self.request.user)
        invalidate_cache_prefix(BOOKS_CACHE_PREFIX)

    def perform_update(self, serializer: BookSerializer) -> None:  # noqa: PLR6301
        """Update a book. Invalidate books cache."""
        serializer.save()
        invalidate_cache_prefix(BOOKS_CACHE_PREFIX)

    def perform_destroy(self, instance) -> None:  # noqa: ANN001
        """Destroy a book. Invalidate books cache."""
        invalidate_cache_prefix(BOOKS_CACHE_PREFIX)
        return super().perform_destroy(instance)


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

    @method_decorator(cache_page(settings.AUTHOR_CACHE_TTL, key_prefix=AUTHOR_CACHE_PREFIX), name='dispatch')
    def list(self, request: Request, *args, **kwargs):  # noqa: ANN201, ANN002, ANN003
        """List authors. Public endpoint, cached.

        Returns:
            Response: Paginated list of authors.
        """
        return super().list(request, *args, **kwargs)

    @method_decorator(cache_page(settings.AUTHOR_CACHE_TTL, key_prefix=AUTHOR_CACHE_PREFIX), name='dispatch')
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

    @method_decorator(cache_page(settings.AUTHOR_CACHE_TTL, key_prefix=TAG_CACHE_PREFIX), name='dispatch')
    def list(self, request: Request, *args, **kwargs):  # noqa: ANN201, ANN002, ANN003
        """List tags. Public endpoint, cached.

        Returns:
            Response: Paginated list of tags.
        """
        return super().list(request, *args, **kwargs)

    @method_decorator(cache_page(settings.AUTHOR_CACHE_TTL, key_prefix=TAG_CACHE_PREFIX), name='dispatch')
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
