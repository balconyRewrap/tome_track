"""Admin configuration for UserBook model."""
from django.contrib import admin

from apps.userbooks.models import UserBook

# Register your models here.

admin.site.register(UserBook)
