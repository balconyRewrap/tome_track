from django.apps import AppConfig


class CommonConfig(AppConfig):
    name = 'apps.common'

    def ready(self) -> None:
        """Apply Django admin site customizations from settings."""
        from django.conf import settings
        from django.contrib import admin

        admin.site.site_header = getattr(settings, 'ADMIN_SITE_HEADER', 'Django administration')
        admin.site.site_title = getattr(settings, 'ADMIN_SITE_TITLE', 'Django site admin')
        admin.site.index_title = getattr(settings, 'ADMIN_INDEX_TITLE', 'Site administration')
