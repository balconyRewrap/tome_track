from apps.common.cache_utils import cache_key, cached_view, invalidate_pattern, cache
import pytest
from unittest.mock import patch
from django.test import RequestFactory

def test_cache_key_same_args_same_key():
    k1 = cache_key('prefix', 1, 'a')
    k2 = cache_key('prefix', 1, 'a')
    assert k1 == k2

def test_cache_key_diff_args_diff_key():
    k1 = cache_key('prefix', 1, 'a')
    k2 = cache_key('prefix', 2, 'a')
    assert k1 != k2

def test_cache_key_prefix():
    k = cache_key('my', 1)
    assert k.startswith('my:')

def test_invalidate_pattern_calls_delete_pattern():
    with patch.object(cache, 'delete_pattern') as mock_del:
        invalidate_pattern('foo*')
        mock_del.assert_called_once_with('foo*')

def test_invalidate_pattern_not_supported():
    with patch('django.core.cache.cache.delete_pattern', new=None):
        with patch('apps.common.cache_utils.hasattr', return_value=False):
            with pytest.raises(NotImplementedError):
                invalidate_pattern('foo*')

def test_cached_view_hits_cache(mocker):
    rf = RequestFactory()
    request = rf.get('/')
    key = 'testkey'
    mocker.patch('django.core.cache.cache.get', return_value='cached')
    mocker.patch('django.core.cache.cache.set')
    @cached_view(timeout=10, key_func=lambda r: key)
    def view(request): return 'fresh'
    assert view(request) == 'cached'

def test_cached_view_sets_cache(mocker):
    rf = RequestFactory()
    request = rf.get('/')
    key = 'testkey'
    mocker.patch('django.core.cache.cache.get', return_value=None)
    set_mock = mocker.patch('django.core.cache.cache.set')
    @cached_view(timeout=10, key_func=lambda r: key)
    def view(request): return 'fresh'
    assert view(request) == 'fresh'
    set_mock.assert_called_once_with(key, 'fresh', 10)
