"""Utility functions for caching in Django applications."""
import hashlib
from collections.abc import Callable
from functools import wraps
from typing import Any

from django.core.cache import cache

# Sentinel object to distinguish a cached None from a cache miss
_MISSING = object()


# args can be anything hashable, so type is not easily expressed without a lot of imports, so we use Any
def cache_key(prefix: str, *args: Any) -> str:  # noqa: ANN401
    """Generate a cache key by hashing arguments with a given prefix.

    Args:
        prefix: The prefix to prepend to the cache key.
        *args: Variable length arguments to be hashed together.

    Returns:
        A cache key string in the format "prefix:hash_digest".
    """
    raw = ':'.join(map(str, args))
    # used for cache, not cryptographic purposes, so md5 is fine
    digest = hashlib.md5(raw.encode()).hexdigest()  # noqa: S324
    return f"{prefix}:{digest}"


def invalidate_pattern(pattern: str) -> None:
    """Invalidate all cache entries matching the given pattern.

    Args:
        pattern: A string pattern to match cache keys for deletion.

    Raises:
        NotImplementedError: If the cache backend does not support pattern deletion.
    """
    if hasattr(cache, 'delete_pattern'):
        cache.delete_pattern(pattern)  # pyright: ignore[reportAttributeAccessIssue]
    else:
        raise NotImplementedError("Cache backend does not support delete_pattern")


def cached_view(timeout: int, key_func: Callable) -> Callable:
    """Decorator cache view function responses based on a custom key function.

    Args:
        timeout: Cache timeout in seconds.
        key_func: Callable that generates cache key from request and additional arguments.

    Returns:
        Decorator function that wraps view functions with caching behavior.

    Example:
        @cached_view(timeout=3600, key_func=lambda r, *a, **k: f"view_{r.user.id}")
        def my_view(request):
            return render(request, 'template.html')
    """
    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            key = key_func(request, *args, **kwargs)
            result = cache.get(key, _MISSING)
            if result is not _MISSING:
                return result
            response = view_func(request, *args, **kwargs)
            cache.set(key, response, timeout)
            return response
        return _wrapped_view
    return decorator
