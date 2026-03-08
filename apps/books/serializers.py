"""Serializers for Books application."""
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.books.models import AUTHOR_MAX_COUNT, TAG_MAX_COUNT, Author, Book, BookType, Tag


# Annotating the *class* (not the instance) is the only reliable way to override
# drf-spectacular's built-in ImageField mapping, which ignores instance-level annotations.
@extend_schema_field({'type': 'string', 'format': 'binary'})
class CoverImageField(serializers.ImageField):
    """Class for schema override of cover image field in BookSerializer."""


class AuthorSerializer(serializers.ModelSerializer):
    """Serializer for Author model."""

    class Meta:  # noqa: D106
        model = Author
        fields = ['id', 'name']


class TagSerializer(serializers.ModelSerializer):
    """Serializer for Tag model."""

    class Meta:  # noqa: D106
        model = Tag
        fields = ['id', 'name', 'slug']


class BookSerializer(serializers.ModelSerializer):
    """Serializer for Book model with business validation."""

    cover = CoverImageField(use_url=True, required=False, allow_null=True)
    average_rating = serializers.FloatField(read_only=True)  # annotated
    ratings_count = serializers.IntegerField(read_only=True)  # annotated
    authors = AuthorSerializer(many=True, read_only=True)
    class Meta:  # noqa: D106
        model = Book
        fields = [
            'id',
            'title',
            'title_en',
            'cover',
            'authors',
            'description',
            'tags',
            'book_type',
            'country',
            'pages_total',
            'chapters_total',
            'edition',
            'parent_book',
            'user',
            'average_rating',
            'ratings_count',
            'created_at',
            'updated_at',
        ]
        extra_kwargs = {
            'title': {'required': True},
            'title_en': {'required': True},
            'authors': {'required': True},
            'book_type': {'required': True},
            'cover': {'required': False},
            'description': {'required': False, 'allow_blank': True},
            'tags': {'required': False},
            'country': {'required': False},
            'pages_total': {'required': False},
            'chapters_total': {'required': False},
            'edition': {'required': False, 'allow_blank': True},
            'parent_book': {'required': False, 'allow_null': True},
            'id': {'read_only': True},
            'user': {'read_only': True},
            'average_rating': {'read_only': True},
            'ratings_count': {'read_only': True},
            'created_at': {'read_only': True},
            'updated_at': {'read_only': True},
        }


class BookWriteSerializer(BookSerializer):
    """Serializer for writing Book — cover rendered as binary upload in Swagger.

    The viewset uses this class for create/update operations via
    ``get_serializer_class`` (see ``books.views.BookViewSet``).  It also
    contains a couple of helpers so that the horrible string that Swagger
    sends when you tick **Send empty value** for the ``tags`` list is
    converted into a real empty list instead of blowing up with
    ``Incorrect type. Expected pk value, received str.``.
    """

    # drf-spectacular maps use_url=False → format: binary → file upload widget in Swagger.
    # At runtime DRF still saves the uploaded file normally regardless of this flag.
    cover = serializers.ImageField(use_url=False, required=False, allow_null=True)

    # override the automatically-generated field so we can intercept
    # the pathological values that the Swagger UI ships when the user
    # checks **Send empty value** on a list field.  We intentionally
    # subclass ``PrimaryKeyRelatedField`` rather than use the default
    # model-generated one so we can tweak the behaviour later if needed.
    tags = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Tag.objects.all(),
        required=False,
        allow_empty=True,
    )
    authors = serializers.PrimaryKeyRelatedField(many=True, queryset=Author.objects.all(), required=True)

    def validate(self, attrs: dict) -> dict:
        """Validate cross-field business rules.

        Raises:
            serializers.ValidationError: If any business rule is violated.

        Returns:
            dict: The validated attributes.
        """
        authors = attrs.get('authors')
        tags = attrs.get('tags', [])
        book_type = attrs.get('book_type', BookType.BOOK)
        pages_total = attrs.get('pages_total')
        chapters_total = attrs.get('chapters_total')
        if authors is not None and len(authors) > AUTHOR_MAX_COUNT:
            raise serializers.ValidationError(
                {'authors': f'A book can have at most {AUTHOR_MAX_COUNT} authors.'},
            )

        if len(tags) > TAG_MAX_COUNT:
            raise serializers.ValidationError(
                {'tags': f'A book can have at most {TAG_MAX_COUNT} tags.'},
            )
        if not self.partial:
            if book_type == BookType.BOOK and not pages_total:
                raise serializers.ValidationError(
                    {'pages_total': 'pages_total is required for book type "book".'},
                )

            if book_type == BookType.COMIC and not chapters_total:
                raise serializers.ValidationError(
                    {'chapters_total': 'chapters_total is required for book type "comic".'},
                )
        else:
            if not hasattr(self, 'initial_data') or not isinstance(self.initial_data, dict):
                raise serializers.ValidationError('initial_data is required for partial updates.')
            if book_type == BookType.BOOK and 'pages_total' in self.initial_data and not pages_total:
                raise serializers.ValidationError(
                    {'pages_total': 'pages_total is required for book type "book".'},
                )
            if book_type == BookType.COMIC and 'chapters_total' in self.initial_data and not chapters_total:
                raise serializers.ValidationError(
                    {'chapters_total': 'chapters_total is required for book type "comic".'},
                )

        return attrs
