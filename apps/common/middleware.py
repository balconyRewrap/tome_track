"""Middleware for restricting admin access by IP address."""

from collections.abc import Callable

from django.http import HttpRequest, HttpResponseForbidden

ALLOWED_ADMIN_IPS = ['127.0.0.1', '172.19.0.1']  # Add my local IP address here


class AdminIPRestrictionMiddleware:
    def __init__(self, get_response: Callable) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        real_ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR'))
        if request.path.startswith('/admin/') and real_ip not in ALLOWED_ADMIN_IPS:
            return HttpResponseForbidden("Admin access denied by IP restriction.")
        return self.get_response(request)
