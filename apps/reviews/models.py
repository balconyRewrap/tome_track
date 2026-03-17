"""Models for the reviews app."""
from django.db import models

from apps.books.models import Book
from apps.common.models import TimestampedModel
from apps.users.models import User

REVIEW_MAX_LENGTH = 50_000
NAME_MAX_LENGTH = 150


class Review(TimestampedModel):
    """Model representing a user's review of a book.

    Attributes:
        user (User): user that owns review.
        book (Book): book of review.
        name (str): name of review.
        body (str): text of review, max of 10,000.
        is_public (bool): whether the review is public or private.
        created_at (DateTimeField): Timestamp when the review was created (inherited from TimestampedModel).
        updated_at (DateTimeField): Timestamp when the review was last updated (inherited from TimestampedModel).
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='reviews')
    name = models.CharField(max_length=NAME_MAX_LENGTH)
    body = models.TextField(max_length=REVIEW_MAX_LENGTH)
    is_public = models.BooleanField(default=True)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Meta class for Review model."""

        constraints = [
            models.UniqueConstraint(
                fields=['user', 'book'],
                name='unique_user_book_review',
            ),
        ]

        indexes = [
            models.Index(fields=['book', 'is_public']),
            models.Index(fields=['user']),
        ]
