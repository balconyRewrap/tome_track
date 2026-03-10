"""Filters for Books application."""
from django_filters import rest_framework as filters

from apps.books.models import Author, Book, BookType, Tag


class BookFilter(filters.FilterSet):
    """FilterSet for Book model supporting author, tag, book_type, and country filters."""

    author = filters.ModelMultipleChoiceFilter(
        field_name='authors', queryset=Author.objects.all(), distinct=True
    )
    tag = filters.ModelMultipleChoiceFilter(
        field_name='tags', queryset=Tag.objects.all(), distinct=True
    )
    book_type = filters.ChoiceFilter(choices=BookType.choices)
    country = filters.CharFilter(lookup_expr='icontains')

    class Meta:  # noqa: D106
        model = Book
        fields = ['author', 'tag', 'book_type', 'country']
