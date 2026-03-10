"""Serializers for review book."""
import re

from rest_framework import serializers

from apps.books.models import Book
from apps.common.validators import validate_serializer_name
from apps.reviews.models import REVIEW_MAX_LENGTH, Review

MAX_WORD_LENGTH = 200


class ReviewSerializer(serializers.ModelSerializer):
    """Serializer for Review model."""

    class Meta:  # noqa: D106
        model = Review
        fields = [
            'id',
            'user',
            'book',
            'name',
            'body',
            'is_public',
            'created_at',
            'updated_at',
        ]
        extra_kwargs = {
            'id': {'read_only': True},
            'user': {'read_only': True},
            'book': {'read_only': True},

            'created_at': {'read_only': True},
            'updated_at': {'read_only': True},
        }


class ReviewWriteSerializer(ReviewSerializer):
    """Serializer for write, update, partial_update of Review."""

    def validate(self, attrs: dict) -> dict:
        """Validate that the user can only have one review per book.

        Raises:
            serializers.ValidationError: if the user already has a review for the book or it's not his book.

        Returns:
            dict: validated data.
        """
        request = self.context.get('request')
        view = self.context.get('view')
        book_id = view.kwargs.get('book_pk') if view is not None else None
        user = request.user if request and request.user.is_authenticated else None

        if not book_id:
            raise serializers.ValidationError("Book ID is required in the URL.")

        # This is a create operation, check if a review by this user for this book already exists.
        if self.instance is None and user is not None and Review.objects.filter(user=user, book_id=book_id).exists():
            raise serializers.ValidationError("You have already reviewed this book.")

        # this check already had in partial, so useless for it again
        if not self.partial and not Book.objects.filter(id=book_id).exists():
            raise serializers.ValidationError("Book does not exist.")

        return super().validate(attrs)

    def validate_name(self, value: str) -> str:  # noqa: PLR6301
        """Validate name text.

        Raises:
            serializers.ValidationError: if any check fails.

        Returns:
            str: validated name text.
        """
        return validate_serializer_name(value)

    def validate_body(self, value: str) -> str:  # noqa: PLR6301
        """Validate body text.

        Raises:
            serializers.ValidationError: if any check fails.

        Returns:
            str: validated body text.
        """
        if len(value) > REVIEW_MAX_LENGTH:
            raise serializers.ValidationError('Review body cannot exceed 10,000 characters.')
        value = value.strip()

        if not value:
            raise serializers.ValidationError('Review body cannot be empty.')

        # all except \n \t \r
        if re.search(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", value):
            raise serializers.ValidationError('Review body cannot contain control characters.')

        if any(len(word) > MAX_WORD_LENGTH for word in value.split()):
            raise serializers.ValidationError("Too long word in text.")

        # delete extra spaces
        value = re.sub(r'\s+', ' ', value).strip()

        return value  # noqa: RET504
