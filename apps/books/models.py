"""Models for book app."""
from io import BytesIO
from typing import Any, Final

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.core.files.base import ContentFile
from django.db import models
from django.utils.text import slugify
from parler.models import TranslatableModel, TranslatedFields
from PIL import Image, ImageOps

from apps.common.models import TimestampedModel
from apps.common.validators import validate_model_cover_image

AUTHOR_MAX_COUNT: Final[int] = 10
TAG_MAX_COUNT: Final[int] = 20
TAG_TRANSLATION_LANGUAGES: Final[tuple[str, str, str]] = ('ru', 'en', 'de')


# now nothing more than name and timestamp fields is usable now, but we can easily add more fields later if needed
class Author(TimestampedModel):
    """Model representing an author.

    Attributes:
        name (str): The unique name of the author, with a maximum length of 255 characters.
        created_at (DateTimeField): Timestamp when the author was created (inherited from TimestampedModel).
        updated_at (DateTimeField): Timestamp when the author was last updated (inherited from TimestampedModel).
    """

    name = models.CharField(max_length=255, unique=True)

    def __str__(self) -> str:
        """Return the name of the author as its string representation.

        Returns:
            str: The name of the author.
        """
        return self.name


class Tag(TranslatableModel, TimestampedModel):  # pyright: ignore[reportIncompatibleMethodOverride,reportIncompatibleVariableOverride]
    """Model representing a tag for books.

    Attributes:
        name (str): translated tag name, with a maximum length of 100 characters.
        slug (str): unique non-translated slug, generated automatically.
        created_at (DateTimeField): Timestamp when the tag was created (inherited from TimestampedModel).
        updated_at (DateTimeField): Timestamp when the tag was last updated (inherited from TimestampedModel).
    """

    translations = TranslatedFields(
        name=models.CharField(max_length=100),
    )
    slug = models.SlugField(unique=True, blank=True)

    def __str__(self) -> str:
        """Return the name of the tag as its string representation.

        Returns:
            str: The name of the tag.
        """
        translated_name = self.safe_translation_getter('name', language_code='en', any_language=True)
        return str(translated_name) if translated_name else self.slug

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Create slug on first save from the translated name."""
        if not self.slug:
            source_name = getattr(self, 'name', '')
            if source_name:
                self.slug = slugify(str(source_name))
        super().save(*args, **kwargs)


class BookType(models.TextChoices):
    """Available types for a book.

    Attributes:
        BOOK: A regular book.
        COMIC: A comic book.
    """

    BOOK = 'book', 'Book'
    COMIC = 'comic', 'Comic'


class Book(TimestampedModel):
    """Model representing a book.

    Attributes:
        title (str): The title of the book, with a maximum length of 500 characters.
        title_en (str): The English title of the book, with a maximum length of 500 characters.
        cover (ImageField): An optional image field for the book's cover, validated for size and content type.
        authors (ManyToManyField): A many-to-many relationship to Author, with a maximum of 10 authors per book.
        description (str): A text field for the book's description, with a maximum length of 5000 characters.
        tags (ManyToManyField): A many-to-many relationship to Tag, with a maximum of 20 tags per book.
        book_type (str): A choice field indicating the type of the book (e.g., 'book' or 'comic').
        country (str): The country of origin for the book, with a default value of 'Unknown'.
        pages_total (int): An optional positive integer field for the total number of pages (required if book_type is 'book').
        chapters_total (int): An optional positive integer field for the total number of chapters (required if book_type is 'comic').
        edition (str): An optional character field for the edition information, with a maximum length of 255 characters.
        parent_book (ForeignKey): An optional self-referential foreign key to represent different editions of the same book.
        user (ForeignKey): An optional foreign key to the user who added the book, allowing null values and cascading on delete.
        created_at (DateTimeField): Timestamp when the book was created (inherited from TimestampedModel).
        updated_at (DateTimeField): Timestamp when the book was last updated (inherited from TimestampedModel).
    """

    title = models.CharField(max_length=500)
    title_en = models.CharField(max_length=500)
    cover = models.ImageField(upload_to='covers/', null=True, blank=True, validators=[validate_model_cover_image])
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
        """Meta class for Book model with indexes and validation constraints."""

        indexes = [
            GinIndex(fields=['title'], name='book_title_trgm', opclasses=['gin_trgm_ops']),
            GinIndex(fields=['title_en'], name='book_title_en_trgm', opclasses=['gin_trgm_ops']),
            models.Index(fields=['book_type']),
            models.Index(fields=['country']),
        ]

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Save book and convert cover image to WebP when needed."""
        self._ensure_cover_is_webp()
        super().save(*args, **kwargs)

    def _ensure_cover_is_webp(self) -> None:
        """Convert cover to WebP before saving if source file is not WebP."""
        if not self.cover or self.cover.name.lower().endswith('.webp'):
            return

        self.cover.open('rb')
        with Image.open(self.cover) as source_image:
            normalized_image = ImageOps.exif_transpose(source_image)

            has_alpha = normalized_image.mode in {'RGBA', 'LA'} or (
                normalized_image.mode == 'P' and 'transparency' in normalized_image.info
            )
            converted = normalized_image.convert('RGBA' if has_alpha else 'RGB')

            output = BytesIO()
            converted.save(output, format='WEBP', quality=85, method=6)

        output.seek(0)
        original_name = self.cover.name.rsplit('/', maxsplit=1)[-1]
        base_name = original_name.rsplit('.', maxsplit=1)[0]
        self.cover.save(f'{base_name}.webp', ContentFile(output.read()), save=False)
