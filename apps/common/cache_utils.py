"""Cache Utils for tome track."""
import functools
from collections.abc import Callable
from typing import Any, TypeVar

from django.core.cache import cache
from rest_framework.request import Request
from rest_framework.response import Response

_F = TypeVar('_F', bound=Callable[..., Response])


def invalidate_cache_prefix(prefix: str) -> None:
    """Invalidate all cache entries that start with the given prefix."""
    # cache func is only for redis, so we can use client.keys to find keys to delete
    client = cache.client.get_client()  # pyright: ignore[reportAttributeAccessIssue]
    for key in client.keys(f'*cache_page.{prefix}*'):
        client.delete(key)
    for key in client.keys(f'*cache_header.{prefix}*'):
        client.delete(key)


def invalidate_cache_by_key_prefix(prefix: str) -> None:
    """Invalidate manually-set cache entries whose Redis key contains *prefix*."""
    client = cache.client.get_client()  # pyright: ignore[reportAttributeAccessIssue]
    for key in client.keys(f'*{prefix}*'):
        client.delete(key)


def cache_response(
    timeout: int,
    key_func: Callable[..., str],
) -> Callable[[_F], _F]:
    """Decorator to cache DRF view responses using a custom key function.

    Returns:
        Callable: A decorator that can be applied to DRF view methods to cache their responses.
    """
    def decorator(method: _F) -> _F:
        @functools.wraps(method)
        def wrapper(view: Any, request: Request, *args: Any, **kwargs: Any) -> Response:
            last_bad_code = 400
            key = key_func(view, method, request, *args, **kwargs)
            cached = cache.get(key)
            if cached is not None:
                return Response(cached)
            response = method(view, request, *args, **kwargs)
            if response.status_code < last_bad_code:
                cache.set(key, response.data, timeout)
            return response
        return wrapper  # type: ignore[return-value]
    return decorator  # type: ignore[return-value]
