import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.books.models import Author, Book, Tag
from apps.userbooks.models import ReadingStatus, UserBook
from apps.users.models import User

pytestmark = pytest.mark.django_db

admin_panel = '/admin/'


def test_admin_access_allowed_ip(settings):
    """A request coming from an IP address that is in the
    ``ALLOWED_ADMIN_IPS`` list should *not* be rejected by the
    :class:`AdminIPRestrictionMiddleware`.

    The Django admin normally redirects anonymous users to the login
    page, which results in a 302 status code, but the important bit for
    this test is that we *do not* see a 403 response.
    """
    # configure a known allowed address and then query the admin panel
    from apps.common import middleware
    middleware.ALLOWED_ADMIN_IPS = ['123.123.123.123']
    cache.clear()
    client = APIClient()
    response = client.get(admin_panel, REMOTE_ADDR='123.123.123.123')
    print(str(response))
    assert response.status_code != status.HTTP_403_FORBIDDEN


def test_admin_access_blocked_ip(settings):
    """A request from an IP address that is *not* in
    ``ALLOWED_ADMIN_IPS`` should receive a 403 Forbidden response.

    We also exercise the ``HTTP_X_FORWARDED_FOR`` header path to ensure
    the middleware picks up the real IP correctly.
    """
    settings.ALLOWED_ADMIN_IPS = ['123.123.123.123']
    from apps.common import middleware
    middleware.ALLOWED_ADMIN_IPS = settings.ALLOWED_ADMIN_IPS

    client = APIClient()

    # REMOTE_ADDR differs from the allowed list
    response = client.get(admin_panel, REMOTE_ADDR='111.111.111.111')
    assert response.status_code == status.HTTP_403_FORBIDDEN

    # even if the forwarded header is set, the first value is used
    response = client.get(
        admin_panel,
        HTTP_X_FORWARDED_FOR='111.111.111.111, 123.123.123.123',
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN

