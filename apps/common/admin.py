"""Admin panel of project."""
import logging

from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

admin.site.site_header = getattr(settings, "ADMIN_SITE_HEADER", "Django Admin")
admin.site.site_title = getattr(settings, "ADMIN_SITE_TITLE", "Django Admin")
admin.site.index_title = getattr(settings, "ADMIN_INDEX_TITLE", "Site administration")


@staff_member_required
@require_POST
def clear_all_cache(request: HttpRequest) -> HttpResponse:
    """Clear all cache entries from the configured cache backend.

    Args:
        request (HttpRequest): Admin request object.

    Returns:
        HttpResponse: Redirect response back to admin index or referer.
    """
    try:
        cache.clear()
    except Exception:  # noqa: BLE001
        logger.exception("Failed to clear cache from admin")
        messages.error(request, "Failed to clear cache. Check server logs for details.")
    else:
        messages.success(request, "Cache was successfully cleared.")

    next_url = request.META.get("HTTP_REFERER") or reverse("admin:index")
    return redirect(next_url)
