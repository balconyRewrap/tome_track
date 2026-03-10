"""Models for the UserBooks application."""
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.books.models import Book
from apps.common.models import TimestampedModel


class ReadingStatus(models.TextChoices):
    """Available reading statuses for a UserBook.

    Attributes:
        READING: The user is currently reading the book.
        COMPLETED: The user has completed reading the book.
        DROPPED: The user has dropped the book.
        PLAN_TO_READ: The user plans to read the book in the future.
    """

    READING = 'reading', 'Reading'
    COMPLETED = 'completed', 'Completed'
    DROPPED = 'dropped', 'Dropped'
    PLAN_TO_READ = 'plan_to_read', 'Plan to Read'


class UserBook(TimestampedModel):
    """Model representing a user's relationship with a book.

    Attributes:
        user (User): User of this relationship.
        book (Book): Book of this relationship.
        status (ReadingStatus): Is book currently being read, completed, dropped, or planned to read.
        current_page (int): Current page, can be blank.
        current_chapter (int): Current chapter, can be blank.
        reread_times (int): How many times user readed the book of relationship.
        is_masterpiece (bool): Boolean of user's opinion whether the book is a masterpiece or not.
        rating (Decimal): User's rating of the book, can be blank.
        created_at (DateTimeField): Timestamp when the user_book was created (inherited from TimestampedModel).
        updated_at (DateTimeField): Timestamp when the user_book was last updated (inherited from TimestampedModel).
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='userbooks')
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='userbooks')
    status = models.CharField(choices=ReadingStatus.choices, max_length=20)
    current_page = models.PositiveIntegerField(null=True, blank=True)
    current_chapter = models.PositiveIntegerField(null=True, blank=True)
    reread_times = models.PositiveIntegerField(default=0)
    is_masterpiece = models.BooleanField(default=False)
    rating = models.DecimalField(
        max_digits=3,  # 10.0, 9.5, etc.
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
    )

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Meta class for UserBook model."""

        unique_together = [['user', 'book']]
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['book']),
        ]

    def __str__(self) -> str:
        """Return a string representation of the UserBook.

        Returns:
            str: the string of object.
        """
        return f'{self.user} — {self.book} ({self.status})'
