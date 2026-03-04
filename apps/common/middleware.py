"""Middleware for restricting admin access by IP address."""

from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden

ALLOWED_ADMIN_IPS = getattr(settings, "ALLOWED_ADMIN_IPS", [])


class AdminIPRestrictionMiddleware:
    """Middleware to restrict access to the Django admin interface based on client IP address."""

    def __init__(self, get_response: Callable) -> None:
        """Initialize the middleware with the next layer in the request/response cycle."""
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponseForbidden | HttpResponse:
        """Process the incoming request and restrict admin access if the client IP is not allowed.

        Args:
            request: The incoming HTTP request object.

        Returns:
            An HTTP response object, either allowing access to the admin interface or returning a 403 Forbidden
        """
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
        real_ip = x_forwarded.split(',')[0].strip() or request.META.get('REMOTE_ADDR')
        if request.path.startswith('/admin/') and real_ip not in ALLOWED_ADMIN_IPS:
            return HttpResponseForbidden("Admin access denied by IP restriction.")
        return self.get_response(request)
