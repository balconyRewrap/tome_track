"""Base config for apps in project."""
from django.apps import AppConfig


class CommonConfig(AppConfig):  # noqa: D101
    name = 'apps.common'

    def ready(self) -> None:  # noqa: PLR6301
        """Apply Django admin site customizations from settings."""
        from django.conf import settings  # noqa: PLC0415
        from django.contrib import admin  # noqa: PLC0415

        admin.site.site_header = getattr(settings, 'ADMIN_SITE_HEADER', 'Django administration')
        admin.site.site_title = getattr(settings, 'ADMIN_SITE_TITLE', 'Django site admin')
        admin.site.index_title = getattr(settings, 'ADMIN_INDEX_TITLE', 'Site administration')
