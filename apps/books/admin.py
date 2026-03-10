"""Admin configuration for the books app."""
from django.contrib import admin

from .models import Author, Book, Tag

# Register your models here.

admin.site.register(Author)
admin.site.register(Tag)


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    """Admin configuration for the Book model."""

    list_display = ['title', 'book_type', 'country', 'created_at']
    list_filter = ['book_type', 'country', 'tags']
    search_fields = ['title', 'title_en']
    filter_horizontal = ['authors', 'tags']
    readonly_fields = ['created_at', 'updated_at']
