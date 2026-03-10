import pytest
from django.conf import settings
from django.test.utils import override_settings
from django.core.cache import cache

@pytest.fixture(autouse=True)
def disable_throttling(request):
    if request.node.get_closest_marker("throttle"):
        yield
        return

    rf = settings.REST_FRAMEWORK.copy()
    rf["DEFAULT_THROTTLE_CLASSES"] = []
    rf['DEFAULT_THROTTLE_RATES'] = {
        'anon': '9999/sec',
        'user': '9999/sec',
        'register': '9999/sec',
        'login': '9999/sec',
        'password_reset': '9999/sec',
    }
    with override_settings(REST_FRAMEWORK=rf):
        yield

@pytest.fixture(autouse=True)
def clear_throttle_cache():
    client = cache.client.get_client()
    keys = client.keys("*throttle*")
    for key in keys:
        client.delete(key)
