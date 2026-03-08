from typing import Final

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.core.exceptions import ValidationError
from django.db import models

from apps.common.models import TimestampedModel
from apps.common.validators import validate_cover_image

AUTHOR_MAX_COUNT: Final[int] = 10
TAG_MAX_COUNT: Final[int] = 20


# now nothing more than name and timestamp fields is usable now, but we can easily add more fields later if needed
class Author(TimestampedModel):
    """Model representing an author of books."""

    name = models.CharField(max_length=255, unique=True)

    def __str__(self) -> str:
        """Return the name of the author as its string representation.

        Returns:
            str: The name of the author.
        """
        return self.name


class Tag(TimestampedModel):
    """Model representing a tag for books."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)

    def __str__(self) -> str:
        """Return the name of the tag as its string representation.

        Returns:
            str: The name of the tag.
        """
        return self.name


class BookType(models.TextChoices):
    """Available types for a book."""

    BOOK = 'book', 'Book'
    COMIC = 'comic', 'Comic'


class Book(TimestampedModel):
    title = models.CharField(max_length=500)
    title_en = models.CharField(max_length=500)
    cover = models.ImageField(upload_to='covers/', null=True, blank=True, validators=[validate_cover_image])
    authors = models.ManyToManyField(Author, related_name='books')
    description = models.TextField(max_length=5000)
    tags = models.ManyToManyField(Tag, related_name='books')
    book_type = models.CharField(choices=BookType.choices, max_length=20, default=BookType.BOOK)
    country = models.CharField(max_length=100, default='Unknown')
    pages_total = models.PositiveIntegerField(null=True, blank=True)
    chapters_total = models.PositiveIntegerField(null=True, blank=True)
    edition = models.CharField(max_length=255, blank=True)
    parent_book = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='editions')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='books',
    )

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        indexes = [  # noqa: RUF012
            GinIndex(fields=['title'], name='book_title_trgm', opclasses=['gin_trgm_ops']),
            GinIndex(fields=['title_en'], name='book_title_en_trgm', opclasses=['gin_trgm_ops']),
            models.Index(fields=['book_type']),
            models.Index(fields=['country']),
        ]

    def clean(self) -> None:
        super().clean()
        if not self.pk:
            return

        if self.authors.count() > AUTHOR_MAX_COUNT:
            raise ValidationError({'authors': f'A book can have at most {AUTHOR_MAX_COUNT} authors.'})

        if self.tags.count() > TAG_MAX_COUNT:
            raise ValidationError({'tags': f'A book can have at most {TAG_MAX_COUNT} tags.'})

        author_ids = frozenset(self.authors.values_list('id', flat=True))
        duplicate = (
            Book.objects.exclude(pk=self.pk)
            .filter(title=self.title)
            .prefetch_related('authors')
        )
        for book in duplicate:
            if frozenset(book.authors.values_list('id', flat=True)) == author_ids:
                raise ValidationError(
                    'A book with this title and the same set of authors already exists.'
                )
