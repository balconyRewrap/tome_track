"""Admin panel of project."""
from django.conf import settings
from django.contrib import admin

admin.site.site_header = getattr(settings, "ADMIN_SITE_HEADER", "Django Admin")
admin.site.site_title = getattr(settings, "ADMIN_SITE_TITLE", "Django Admin")
admin.site.index_title = getattr(settings, "ADMIN_INDEX_TITLE", "Site administration")
