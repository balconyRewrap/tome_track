"""Cache Utils for tome track."""
from django.core.cache import cache


def invalidate_cache_prefix(prefix: str) -> None:
    """Invalidate all cache entries that start with the given prefix."""
    client = cache.client.get_client()
    for key in client.keys(f'*cache_page.{prefix}*'):
        client.delete(key)
    for key in client.keys(f'*cache_header.{prefix}*'):
        client.delete(key)


def invalidate_cache_by_key_prefix(prefix: str) -> None:
    """Invalidate manually-set cache entries whose Redis key contains *prefix*."""
    client = cache.client.get_client()
    for key in client.keys(f'*{prefix}*'):
        client.delete(key)
