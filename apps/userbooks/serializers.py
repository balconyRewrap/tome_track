"""Models for UserBook app."""
from rest_framework import serializers

from apps.books.models import Book, BookType
from apps.userbooks.models import ReadingStatus, UserBook

MIN_RATING = 0
MAX_RATING = 10


class UserBookSerializer(serializers.ModelSerializer):
    """Serializer for UserBook model."""

    class Meta:  # noqa: D106
        model = UserBook
        fields = [
            'id',
            'user',
            'book',
            'status',
            'current_chapter',
            'current_page',
            'is_masterpiece',
            'rating',
            'created_at',
            'updated_at',
        ]
        extra_kwargs = {
            'id': {'read_only': True},
            'user': {'read_only': True},
            # 'book': {'required': True},
            # 'status': {'required': True},

            'created_at': {'read_only': True},
            'updated_at': {'read_only': True},
        }


class UserBookWriteSerializer(UserBookSerializer):
    """Serializer for write, update, partial_update of UserBook."""

    book = serializers.PrimaryKeyRelatedField(queryset=Book.objects.all())

    def validate(self, attrs: dict) -> dict:
        """Custom validation for UserBook fields based on business rules.

        Validate by:
        - If the book is marked as a masterpiece, its status must be "completed".
        - Current page can only be set for books of type "book".
        - Current chapter can only be set for books of type "comic".
        - Current page cannot exceed the total pages of the book.
        - Rating must be between 0 and 10.
        - Rating cannot be set for books with status "plan_to_read".

        Returns:
            dict: the validated attributes.

        Raises:
            serializers.ValidationError: If any of the validation rules are violated.
        """
        is_masterpiece = attrs.get('is_masterpiece', False)
        status = attrs.get('status')
        current_chapter = attrs.get('current_chapter')
        current_page = attrs.get('current_page')
        book = attrs.get('book')
        rating = attrs.get('rating')
        if not self.partial and not book:
            raise serializers.ValidationError(
                'Book is required.',
            )
        if is_masterpiece and status != ReadingStatus.COMPLETED:
            raise serializers.ValidationError(
                'A book can be masterpiece only if status is completed.',
            )
        if current_page and book and book.book_type != BookType.BOOK:
            raise serializers.ValidationError(
                'Current page can be set only for books of type "book".',
            )

        if current_chapter and book and book.book_type != BookType.COMIC:
            raise serializers.ValidationError(
                'Current chapter can be set only for books of type "comic".',
            )

        if current_page and book and book.pages_total and current_page > book.pages_total:
            raise serializers.ValidationError(
                'Current page cannot be greater than total pages of the book.',
            )

        if rating and (rating < MIN_RATING or rating > MAX_RATING):
            raise serializers.ValidationError(
                f'Rating must be between {MIN_RATING} and {MAX_RATING}.',
            )
        if rating and status and status == ReadingStatus.PLAN_TO_READ:
            raise serializers.ValidationError(
                'Rating cannot be set for books with status "plan_to_read".',
            )
        return attrs
