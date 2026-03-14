"""Tests for TagViewSet — all endpoints and all possible situations."""
import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.books.models import Tag
from apps.users.models import User

pytestmark = pytest.mark.django_db

TAGS_URL = reverse('tags')


def tag_detail_url(pk: int) -> str:
    return reverse('tag-detail', kwargs={'pk': pk})


# Fixtures

@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user(  # pyright: ignore[reportAttributeAccessIssue]
        email='user@example.com',
        username='testuser',
        password='StrongPass123',
        role='user',
    )


@pytest.fixture
def admin_user(db) -> User:
    return User.objects.create_user(  # pyright: ignore[reportAttributeAccessIssue]
        email='admin@example.com',
        username='adminuser',
        password='StrongPass123',
        role='admin',
    )


@pytest.fixture
def tag(db) -> Tag:
    tag = Tag.objects.create(slug='existing-tag')
    tag.create_translation('ru', name='Sushchestvuyushchii teg')
    tag.create_translation('en', name='Existing Tag')
    tag.create_translation('de', name='Vorhandenes Tag')
    return tag


def _translations_payload(ru: str, en: str, de: str) -> dict:
    return {
        'translations': {
            'ru': {'name': ru},
            'en': {'name': en},
            'de': {'name': de},
        },
    }


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


# LIST  GET /api/v1/tags/

def test_list_tags_anonymous_returns_200(api_client, tag):
    """Anonymous user can list tags."""
    response = api_client.get(TAGS_URL)
    assert response.status_code == status.HTTP_200_OK


def test_list_tags_authenticated_returns_200(api_client, user, tag):
    """Authenticated user can list tags."""
    api_client.force_authenticate(user=user)
    response = api_client.get(TAGS_URL)
    assert response.status_code == status.HTTP_200_OK


def test_list_tags_contains_existing_tag(api_client, tag):
    """List response includes the tag that exists in the DB."""
    response = api_client.get(TAGS_URL)
    results = response.data.get('results', response.data)
    ids = [item['id'] for item in results]
    assert tag.pk in ids


def test_list_tags_response_fields(api_client, tag):
    """Each item in the list has 'id', 'slug', and full 'translations' fields."""
    response = api_client.get(TAGS_URL)
    results = response.data.get('results', response.data)
    assert len(results) > 0
    first = results[0]
    for field in ('id', 'slug', 'translations'):
        assert field in first, f"Field '{field}' missing from list response"
    assert set(first['translations']) == {'ru', 'en', 'de'}


# RETRIEVE  GET /api/v1/tags/<pk>/

def test_retrieve_tag_anonymous_returns_200(api_client, tag):
    """Anonymous user can retrieve a tag by ID."""
    response = api_client.get(tag_detail_url(tag.pk))
    assert response.status_code == status.HTTP_200_OK
    assert response.data['id'] == tag.pk
    assert response.data['slug'] == tag.slug
    assert response.data['translations']['ru']['name'] == 'Sushchestvuyushchii teg'
    assert response.data['translations']['en']['name'] == 'Existing Tag'
    assert response.data['translations']['de']['name'] == 'Vorhandenes Tag'


def test_retrieve_tag_not_found_returns_404(api_client):
    """Retrieve a non-existent tag returns 404."""
    response = api_client.get(tag_detail_url(9999))
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_retrieve_tag_response_fields(api_client, tag):
    """Retrieve response contains 'id', 'slug', and 'translations'."""
    response = api_client.get(tag_detail_url(tag.pk))
    for field in ('id', 'slug', 'translations'):
        assert field in response.data, f"Field '{field}' missing from retrieve response"
    assert set(response.data['translations']) == {'ru', 'en', 'de'}


# CREATE  POST /api/v1/tags/

def test_create_tag_by_admin_returns_201(api_client, admin_user):
    """Admin can create a tag."""
    api_client.force_authenticate(user=admin_user)
    payload = _translations_payload('Novyi teg', 'New Tag', 'Neues Tag')
    response = api_client.post(TAGS_URL, payload, format='json')
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data['translations']['en']['name'] == 'New Tag'
    assert response.data['slug'] == 'new-tag'
    assert Tag.objects.filter(slug='new-tag').exists()


def test_create_tag_by_non_admin_returns_403(api_client, user):
    """Regular authenticated user cannot create a tag (admin-only)."""
    api_client.force_authenticate(user=user)
    payload = _translations_payload('Zapreshchennyi teg', 'Forbidden Tag', 'Verbotenes Tag')
    response = api_client.post(TAGS_URL, payload, format='json')
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert not Tag.objects.filter(slug='forbidden-tag').exists()


def test_create_tag_unauthenticated_returns_401(api_client):
    """Unauthenticated request to create a tag returns 401."""
    payload = _translations_payload('Prizrachnyi teg', 'Ghost Tag', 'Geistertag')
    response = api_client.post(TAGS_URL, payload, format='json')
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert not Tag.objects.filter(slug='ghost-tag').exists()


def test_create_tag_missing_name_returns_400(api_client, admin_user):
    """Create tag without one translated name returns 400."""
    api_client.force_authenticate(user=admin_user)
    payload = {
        'translations': {
            'ru': {'name': 'Bez angliiskogo'},
            'en': {},
            'de': {'name': 'Ohne Englisch'},
        },
    }
    response = api_client.post(TAGS_URL, payload, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_create_tag_duplicate_name_returns_400(api_client, admin_user, tag):
    """Create tag with an existing translated name returns 400."""
    api_client.force_authenticate(user=admin_user)
    payload = _translations_payload('Novyi unikalnyi', 'Existing Tag', 'Neues Einzigartiges')
    response = api_client.post(TAGS_URL, payload, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_create_tag_name_too_long_returns_400(api_client, admin_user):
    """Create tag with name exceeding max_length returns 400."""
    api_client.force_authenticate(user=admin_user)
    long_name = 'T' * 101  # max_length=100
    payload = _translations_payload('Obychnoe imya', long_name, 'Normales Name')
    response = api_client.post(TAGS_URL, payload, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_create_tag_response_fields(api_client, admin_user):
    """Created tag response contains 'id', 'slug', and 'translations'."""
    api_client.force_authenticate(user=admin_user)
    payload = _translations_payload('Teg polei', 'Field Tag', 'Feldtag')
    response = api_client.post(TAGS_URL, payload, format='json')
    assert response.status_code == status.HTTP_201_CREATED
    for field in ('id', 'slug', 'translations'):
        assert field in response.data, f"Field '{field}' missing from create response"
    assert set(response.data['translations']) == {'ru', 'en', 'de'}


# Cache invalidation

def test_create_tag_invalidates_cache(api_client, admin_user, tag):
    """After creating a tag, the list reflects the new entry."""
    first = api_client.get(TAGS_URL)
    count_before = len(first.data.get('results', first.data))

    api_client.force_authenticate(user=admin_user)
    payload = _translations_payload('Kesh-invalidator', 'Cache Bust Tag', 'Cache-Bust-Tag')
    api_client.post(TAGS_URL, payload, format='json')
    api_client.force_authenticate(user=None)

    second = api_client.get(TAGS_URL)
    count_after = len(second.data.get('results', second.data))
    assert count_after > count_before
