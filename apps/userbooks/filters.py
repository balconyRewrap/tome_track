"""Filters for UserBooks application."""
from django_filters import rest_framework as filters

from apps.books.models import BookType
from apps.userbooks.models import ReadingStatus, UserBook


class UserBookFilter(filters.FilterSet):
    """FilterSet for UserBook model supporting status and book_type filters."""

    status = filters.ChoiceFilter(choices=ReadingStatus.choices)
    type = filters.ChoiceFilter(field_name='book__book_type', choices=BookType.choices)

    class Meta:  # noqa: D106
        model = UserBook
        fields = ['status', 'type']
