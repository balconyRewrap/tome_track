"""Admin configuration for review app."""
from django.contrib import admin
from django.db.models import QuerySet
from django.http.request import HttpRequest

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
        updated = queryset.update(is_public=False)
        self.message_user(request, f"{updated} reviews marked as private.")

    @admin.action(description="Make selected reviews public")
    def make_public(self, request: HttpRequest, queryset: QuerySet[Review]) -> None:
        """Admin action to make selected reviews public.

        Args:
            request (HttpRequest): The request object.
            queryset (QuerySet[Review]): The queryset of Review to make public.
        """
        updated = queryset.update(is_public=True)
        self.message_user(request, f"{updated} reviews marked as public.")
