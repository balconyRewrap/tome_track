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
            'reread_times',
            'is_masterpiece',
            'rating',
            'created_at',
            'updated_at',
        ]
        extra_kwargs = {
            'id': {'read_only': True},
            'user': {'read_only': True},

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
        - Current page cannot exceed the total pages of the book.
        - Rating must be between 0 and 10.
        - Rating cannot be set for books with status "plan_to_read".

        Returns:
            dict: the validated attributes.

        Raises:
            serializers.ValidationError: If any of the validation rules are violated.
        """
        status = attrs.get('status')
        if self.partial and self.instance and status is None:
            status = self.instance.status

        is_masterpiece_default = (
            getattr(self.instance, 'is_masterpiece', False)
            if self.partial
            else False
        )
        is_masterpiece = attrs.get('is_masterpiece', is_masterpiece_default)

        current_page = attrs.get('current_page')
        book = attrs.get('book')
        rating = attrs.get('rating')

        if not self.partial and not book:
            raise serializers.ValidationError(
                'Book is required.',
            )
        if not self.partial and book:
            user = self.context['request'].user
            if UserBook.objects.filter(user=user, book=book).exists():
                raise serializers.ValidationError(
                    'You already have this book in your list.',
                )
        if is_masterpiece and status != ReadingStatus.COMPLETED:
            raise serializers.ValidationError(
                'A book can be masterpiece only if status is completed.',
            )
        if current_page and book and book.book_type != BookType.BOOK:
            raise serializers.ValidationError(
                'Current page can be set only for books of type "book".',
            )

        if current_page and book and book.pages_total and current_page > book.pages_total:
            raise serializers.ValidationError(
                'Current page cannot be greater than total pages of the book.',
            )
        # not just check on rating, but check on is not None, because
        # rating can be 0, and we want to allow it.
        if rating is not None and (rating < MIN_RATING or rating > MAX_RATING):
            raise serializers.ValidationError(
                f'Rating must be between {MIN_RATING} and {MAX_RATING}.',
            )
        if rating is not None and status == ReadingStatus.PLAN_TO_READ:
            raise serializers.ValidationError(
                'Rating cannot be set for books with status "plan_to_read".',
            )
        return attrs


class UserBookUpdateSerializer(UserBookWriteSerializer):
    """Serializer for partial_update of UserBook — book field is excluded (cannot be changed)."""

    class Meta(UserBookSerializer.Meta):  # noqa: D106
        fields = [
            'id',
            'user',
            'status',
            'current_chapter',
            'current_page',
            'reread_times',
            'is_masterpiece',
            'rating',
            'created_at',
            'updated_at',
        ]
        extra_kwargs = UserBookSerializer.Meta.extra_kwargs

    def validate(self, attrs: dict) -> dict:
        """In update no book is given in response, so we need additional check.

        Args:
            attrs (dict): attrs of response

        Returns:
            attrs (dict): validated attrs of response

        Raises:
            serializers.ValidationError: if any check fails
        """
        if not self.instance:
            raise serializers.ValidationError(
                "You try to update not existed User Book.",
            )
        book = self.instance.book
        current_page = attrs.get('current_page')
        if current_page and book and book.pages_total and current_page > book.pages_total:
            raise serializers.ValidationError(
                'Current page cannot be greater than total pages of the book.',
            )
        if current_page and book and book.book_type != BookType.BOOK:
            raise serializers.ValidationError(
                'Current page can be set only for books of type "book".',
            )
        return super().validate(attrs)


class TotalPagesReadSerializer(serializers.Serializer):
    """Serializer for total pages read for the current user."""

    total_pages_read = serializers.IntegerField()
