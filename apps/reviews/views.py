"""Views for the reviews app."""
from collections.abc import Callable
from typing import Any

from django.conf import settings
from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import Q, QuerySet
from django.db.models.functions import Greatest
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import generics, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.cache_utils import cache_response, invalidate_cache_by_key_prefix
from apps.common.mixins import ActionPermissionsMixin
from apps.common.permissions import IsOwnerOrAdmin
from apps.reviews.models import Review
from apps.reviews.serializers import ReviewSerializer, ReviewWriteSerializer
from apps.users.models import User

REVIEWS_CACHE_TTL = getattr(settings, 'REVIEWS_CACHE_TTL', 60 * 5)  # 5 minutes
REVIEWS_DETAIL_CACHE_TTL = getattr(settings, 'REVIEWS_DETAIL_CACHE_TTL', 60 * 60)  # 1 hour


def review_cache_key(
    view_instance: "ReviewViewSet",  # noqa: ARG001
    view_method: Callable,
    request: Request,
    *args: Any,  # noqa: ARG001
    **kwargs: Any,
) -> str:
    """Return a cache key for reviews list and detail views, based on user ID, book ID and view method.

    Returns:
        str: The cache key for the review list or detail view.
    """
    book_id = kwargs.get('book_pk')
    user_id = request.user.pk if request.user.is_authenticated else 'anon'
    return f"reviews:book:{book_id}:{view_method.__name__}:user:{user_id}"


@extend_schema_view(
    list=extend_schema(
        summary="List reviews",
        description="Returns a paginated list of reviews for a book. "
        "Authenticated users also see their own private reviews. Staff see all reviews.",
        parameters=[
            OpenApiParameter(name='book_pk', location=OpenApiParameter.PATH, description="Book ID", type=int),
        ],
        responses={200: ReviewSerializer(many=True)},
        tags=['Reviews'],
    ),
    retrieve=extend_schema(
        summary="Retrieve a review",
        description="Returns the details of a single review. "
        "Anonymous users can only retrieve public reviews."
        "Authenticated users can also retrieve their own private reviews.",
        parameters=[
            OpenApiParameter(name='book_pk', location=OpenApiParameter.PATH, description="Book ID", type=int),
            OpenApiParameter(name='id', location=OpenApiParameter.PATH, description="Review ID", type=int),
        ],
        responses={
            200: ReviewSerializer,
            404: OpenApiResponse(description="Review not found."),
        },
        tags=['Reviews'],
    ),
    create=extend_schema(
        summary="Create a review",
        description="Creates a new review for a book. Each user can leave only one review per book.",
        parameters=[
            OpenApiParameter(name='book_pk', location=OpenApiParameter.PATH, description="Book ID", type=int),
        ],
        request=ReviewWriteSerializer,
        responses={
            201: ReviewSerializer,
            400: OpenApiResponse(description="Validation error (e.g. already reviewed this book)."),
            401: OpenApiResponse(description="Authentication credentials were not provided."),
        },
        tags=['Reviews'],
    ),
    partial_update=extend_schema(
        summary="Partial update a review",
        description="Updates one or more fields of an existing review. Only the owner or admin can update.",
        parameters=[
            OpenApiParameter(name='book_pk', location=OpenApiParameter.PATH, description="Book ID", type=int),
            OpenApiParameter(name='id', location=OpenApiParameter.PATH, description="Review ID", type=int),
        ],
        request=ReviewWriteSerializer,
        responses={
            200: ReviewSerializer,
            400: OpenApiResponse(description="Validation error."),
            403: OpenApiResponse(description="Forbidden — not the owner or admin."),
            404: OpenApiResponse(description="Review not found."),
        },
        tags=['Reviews'],
    ),
    destroy=extend_schema(
        summary="Delete a review",
        description="Deletes a review. Only the owner or admin can delete.",
        parameters=[
            OpenApiParameter(name='book_pk', location=OpenApiParameter.PATH, description="Book ID", type=int),
            OpenApiParameter(name='id', location=OpenApiParameter.PATH, description="Review ID", type=int),
        ],
        responses={
            204: OpenApiResponse(description="Review deleted successfully."),
            403: OpenApiResponse(description="Forbidden — not the owner or admin."),
            404: OpenApiResponse(description="Review not found."),
        },
        tags=['Reviews'],
    ),
    search=extend_schema(
        summary="Search reviews",
        description="Searches reviews of a book by name and body using trigram similarity. "
        "Returns results ordered by relevance.",
        parameters=[
            OpenApiParameter(name='book_pk', location=OpenApiParameter.PATH, description="Book ID", type=int),
            OpenApiParameter(
                name='query',
                location=OpenApiParameter.QUERY,
                description="Search query string",
                type=str,
                required=True,
            ),
        ],
        responses={
            200: ReviewSerializer(many=True),
            400: OpenApiResponse(description="Query parameter is required."),
        },
        tags=['Reviews'],
    ),
)
class ReviewViewSet(ActionPermissionsMixin, viewsets.ModelViewSet):
    """ViewSet for Review model."""

    http_method_names = ['get', 'post', 'patch', 'delete']
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer

    permission_classes_by_action = {
        'list': [AllowAny],
        'create': [IsAuthenticated],
        'retrieve': [AllowAny],
        'search': [AllowAny],
        'partial_update': [IsOwnerOrAdmin],
        'destroy': [IsOwnerOrAdmin],
    }

    def get_serializer_class(self) -> ReviewSerializer:  # pyright: ignore[reportIncompatibleMethodOverride]
        """Returns the appropriate serializer class based on the action.

        For 'create' and 'partial_update' actions, it returns ReviewWriteSerializer,
        which includes validation for the name and body fields.

        Returns:
            serializer (ReviewSerializer): The serializer class to be used for the current action.
        """
        if self.action in {'create', 'partial_update'}:
            return ReviewWriteSerializer  # pyright: ignore[reportReturnType]
        return ReviewSerializer  # pyright: ignore[reportReturnType]

    def get_queryset(self) -> QuerySet[Review]:  # pyright: ignore[reportIncompatibleMethodOverride]
        """Override of get_queryset to filter reviews based on user permissions and book ID.

        - If the user is admin, they can see all reviews.
        - If the user is authenticated, they can see public reviews and their own reviews.
        - If the user is not authenticated, they can only see public reviews.
        - If book_id is provided in the URL, filter reviews by book_id.

        Returns:
            QuerySet: The queryset of reviews filtered by user permissions and book ID.
        """
        book_id = self.kwargs.get('book_pk')

        # If the user is staff, they can see all reviews.
        # if user.is_authenticated, he has role.
        if (
            self.request.user.is_authenticated
            and isinstance(self.request.user, User)
            and self.request.user.role == 'admin'
        ):
            qs = Review.objects.select_related('user', 'book').all()
        # If authenticated, they can see public reviews and their own reviews.
        elif self.request.user.is_authenticated:
            qs = Review.objects.select_related('user', 'book').filter(Q(is_public=True) | Q(user=self.request.user))
        # If not authenticated, they can only see public reviews.
        else:
            qs = Review.objects.select_related('user', 'book').filter(is_public=True)
        # If book_id is provided in the URL, filter reviews by book_id.
        if book_id is not None:
            qs = qs.filter(book_id=book_id)

        return qs.order_by('-updated_at')

    @cache_response(timeout=REVIEWS_CACHE_TTL, key_func=review_cache_key)
    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:  # pyright: ignore[reportIncompatibleMethodOverride]
        """List reviews for a book, cached.

        Returns:
            Response: A paginated list of reviews for the specified book.
        """
        return super().list(request, *args, **kwargs)

    @cache_response(timeout=REVIEWS_DETAIL_CACHE_TTL, key_func=review_cache_key)
    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:  # pyright: ignore[reportIncompatibleMethodOverride]
        """Retrieve a review, cached.

        Returns:
            Response: The details of the specified review.
        """
        return super().retrieve(request, *args, **kwargs)

    @action(detail=False, methods=['get'], url_path='search', permission_classes=[AllowAny])
    def search(self, request: Request, *args: Any, **kwargs: Any) -> Response:  # noqa: ARG002
        """Search reviews by name and body using trigram similarity.

        Returns:
            Response: A list of reviews matching the search query, ordered by relevance.
        """
        book_id = self.kwargs.get('book_pk')
        query = request.query_params.get('query', '')

        if not query:
            return Response({"detail": "Query parameter is required."}, status=400)
        qs = self.get_queryset()
        reviews = (
            qs.annotate(
                similarity=Greatest(
                    TrigramSimilarity('name', query),
                    TrigramSimilarity('body', query),
                ),
            )
            .filter(similarity__gt=0.1)
            .order_by('-similarity')  # Order by relevance.
        )

        page = self.paginate_queryset(reviews)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(reviews, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer: ReviewSerializer) -> None:
        """Create a review and invalidate the cache for the book's reviews list.

        Args:
            serializer (ReviewSerializer): The serializer instance with validated data for creating a review.
        """
        review = serializer.save(user=self.request.user, book_id=self.kwargs['book_pk'])
        self._invalidate_review_cache(review)

    def perform_update(self, serializer: ReviewSerializer) -> None:
        """Update a review and invalidate the cache for the book's reviews list and detail view."""
        review = serializer.save()
        self._invalidate_review_cache(review)

    def perform_destroy(self, instance: Review) -> None:
        """Delete a review and invalidate the cache for the book's reviews list and detail view."""
        super().perform_destroy(instance)
        self._invalidate_review_cache(instance)

    def _invalidate_review_cache(self, review: Review) -> None:  # noqa: PLR6301
        """Helper to invalidate cache for a review."""
        # Invalidate the cache for the reviews list of the book,
        # so that the updated/deleted review will be reflected in the list.
        invalidate_cache_by_key_prefix(f"reviews:book:{review.book.id}:list")  # pyright: ignore[reportAttributeAccessIssue]
        # Invalidate the cache for the review detail view,
        # so that the updated/deleted review will be reflected in the detail view.
        invalidate_cache_by_key_prefix(f"reviews:book:{review.book.id}:retrieve")  # pyright: ignore[reportAttributeAccessIssue]


@extend_schema(
    summary="My Reviews",
    description="Returns all reviews of the authenticated user, including private ones.",
    responses={
        200: OpenApiResponse(ReviewSerializer(many=True), description="List of user's reviews."),
        401: OpenApiResponse(description="Authentication credentials were not provided."),
    },
    tags=['Users'],
)
class UserMeReviewsView(generics.ListAPIView):
    """Endpoint for listing all reviews of the authenticated user, including private ones."""

    permission_classes = [IsAuthenticated]
    serializer_class = ReviewSerializer

    def get_queryset(self) -> QuerySet[Review]:  # pyright: ignore[reportIncompatibleMethodOverride]
        """Return all reviews belonging to the current authenticated user.

        Returns:
            QuerySet: All reviews of the authenticated user, ordered by updated_at.
        """
        if getattr(self, 'swagger_fake_view', False):
            return Review.objects.none()
        return Review.objects.filter(user=self.request.user).order_by('-updated_at')
