"""Admin configuration for review app."""
from django.contrib import admin
from django.db.models import QuerySet
from django.http.request import HttpRequest

from apps.common.cache_utils import invalidate_cache_by_key_prefix
from apps.reviews.models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    """Admin configuration for the Review model."""

    list_display = ['user', 'book', 'is_public', 'created_at']
    list_filter = ['is_public']
    actions = ['make_private', 'make_public']

    @admin.action(description="Make selected reviews private")
    def make_private(self, request: HttpRequest, queryset: QuerySet[Review]) -> None:
        """Admin action to make selected reviews private.

        Args:
            request (HttpRequest): The request object.
            queryset (QuerySet[Review]): The queryset of Review to make private.
        """
        updated = []
        for review in queryset:
            review.is_public = False
            review.save(update_fields=["is_public"])
            updated.append(review)
        self.message_user(request, f"{updated} reviews marked as private.")

    @admin.action(description="Make selected reviews public")
    def make_public(self, request: HttpRequest, queryset: QuerySet[Review]) -> None:
        """Admin action to make selected reviews public.

        Args:
            request (HttpRequest): The request object.
            queryset (QuerySet[Review]): The queryset of Review to make public.
        """
        updated = []
        for review in queryset:
            review.is_public = True
            review.save(update_fields=["is_public"])
            updated.append(review)
        self.message_user(request, f"{len(updated)} reviews marked as public.")

    def _invalidate_review_cache(self, review: Review) -> None:  # noqa: PLR6301
        """Helper to invalidate cache for a review."""
        invalidate_cache_by_key_prefix(f"reviews:book:{review.book.id}:list")  # pyright: ignore[reportAttributeAccessIssue]
        invalidate_cache_by_key_prefix(f"reviews:book:{review.book.id}:retrieve")  # pyright: ignore[reportAttributeAccessIssue]
