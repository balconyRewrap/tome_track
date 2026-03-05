"""Serializers for Books application."""
from rest_framework import serializers

from apps.books.models import AUTHOR_MAX_COUNT, TAG_MAX_COUNT, Author, Book, BookType, Tag


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
            'created_at',
            'updated_at',
        ]

    def validate(self, attrs: dict) -> dict:  # noqa: PLR6301
        """Validate cross-field business rules.

        Raises:
            serializers.ValidationError: If any business rule is violated.

        Returns:
            dict: The validated attributes.
        """
        authors = attrs.get('authors', [])
        tags = attrs.get('tags', [])
        book_type = attrs.get('book_type', BookType.BOOK)
        pages_total = attrs.get('pages_total')
        chapters_total = attrs.get('chapters_total')

        if len(authors) > AUTHOR_MAX_COUNT:
            raise serializers.ValidationError(
                {'authors': f'A book can have at most {AUTHOR_MAX_COUNT} authors.'},
            )

        if len(tags) > TAG_MAX_COUNT:
            raise serializers.ValidationError(
                {'tags': f'A book can have at most {TAG_MAX_COUNT} tags.'},
            )

        if book_type == BookType.BOOK and not pages_total:
            raise serializers.ValidationError(
                {'pages_total': 'pages_total is required for book type "book".'},
            )

        if book_type == BookType.COMIC and not chapters_total:
            raise serializers.ValidationError(
                {'chapters_total': 'chapters_total is required for book type "comic".'},
            )

        return attrs
