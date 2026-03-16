"""Standardized pagination for API results with configurable page size."""
from rest_framework.pagination import PageNumberPagination


class StandardResultsSetPagination(PageNumberPagination):
    """Standardized pagination for API results with configurable page size."""

    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 1500
