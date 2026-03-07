from django.contrib import admin

from .models import Author, Book, Tag

# Register your models here.
admin.site.register(Book)
admin.site.register(Author)
admin.site.register(Tag)
