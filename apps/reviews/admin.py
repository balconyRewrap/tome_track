"""Models of review are registered for admin site here."""
from django.contrib import admin

from apps.reviews.models import Review

admin.site.register(Review)
