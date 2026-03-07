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
    return Tag.objects.create(name='Existing Tag', slug='existing-tag')


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
    """Each item in the list has 'id', 'name', and 'slug' fields."""
    response = api_client.get(TAGS_URL)
    results = response.data.get('results', response.data)
    assert len(results) > 0
    first = results[0]
    for field in ('id', 'name', 'slug'):
        assert field in first, f"Field '{field}' missing from list response"


# RETRIEVE  GET /api/v1/tags/<pk>/

def test_retrieve_tag_anonymous_returns_200(api_client, tag):
    """Anonymous user can retrieve a tag by ID."""
    response = api_client.get(tag_detail_url(tag.pk))
    assert response.status_code == status.HTTP_200_OK
    assert response.data['id'] == tag.pk
    assert response.data['name'] == tag.name
    assert response.data['slug'] == tag.slug


def test_retrieve_tag_not_found_returns_404(api_client):
    """Retrieve a non-existent tag returns 404."""
    response = api_client.get(tag_detail_url(9999))
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_retrieve_tag_response_fields(api_client, tag):
    """Retrieve response contains 'id', 'name', and 'slug'."""
    response = api_client.get(tag_detail_url(tag.pk))
    for field in ('id', 'name', 'slug'):
        assert field in response.data, f"Field '{field}' missing from retrieve response"


# CREATE  POST /api/v1/tags/

def test_create_tag_by_admin_returns_201(api_client, admin_user):
    """Admin can create a tag."""
    api_client.force_authenticate(user=admin_user)
    response = api_client.post(TAGS_URL, {'name': 'New Tag', 'slug': 'new-tag'}, format='json')
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data['name'] == 'New Tag'
    assert response.data['slug'] == 'new-tag'
    assert Tag.objects.filter(slug='new-tag').exists()


def test_create_tag_by_non_admin_returns_403(api_client, user):
    """Regular authenticated user cannot create a tag (admin-only)."""
    api_client.force_authenticate(user=user)
    response = api_client.post(TAGS_URL, {'name': 'Forbidden Tag', 'slug': 'forbidden-tag'}, format='json')
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert not Tag.objects.filter(slug='forbidden-tag').exists()


def test_create_tag_unauthenticated_returns_401(api_client):
    """Unauthenticated request to create a tag returns 401."""
    response = api_client.post(TAGS_URL, {'name': 'Ghost Tag', 'slug': 'ghost-tag'}, format='json')
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert not Tag.objects.filter(slug='ghost-tag').exists()


def test_create_tag_missing_name_returns_400(api_client, admin_user):
    """Create tag without 'name' returns 400."""
    api_client.force_authenticate(user=admin_user)
    response = api_client.post(TAGS_URL, {'slug': 'no-name'}, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_create_tag_missing_slug_returns_400(api_client, admin_user):
    """Create tag without 'slug' returns 400."""
    api_client.force_authenticate(user=admin_user)
    response = api_client.post(TAGS_URL, {'name': 'No Slug'}, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_create_tag_duplicate_name_returns_400(api_client, admin_user, tag):
    """Create tag with an existing name returns 400 (unique constraint)."""
    api_client.force_authenticate(user=admin_user)
    response = api_client.post(TAGS_URL, {'name': tag.name, 'slug': 'different-slug'}, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_create_tag_duplicate_slug_returns_400(api_client, admin_user, tag):
    """Create tag with an existing slug returns 400 (unique constraint)."""
    api_client.force_authenticate(user=admin_user)
    response = api_client.post(TAGS_URL, {'name': 'Different Name', 'slug': tag.slug}, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_create_tag_name_too_long_returns_400(api_client, admin_user):
    """Create tag with name exceeding max_length returns 400."""
    api_client.force_authenticate(user=admin_user)
    long_name = 'T' * 101  # max_length=100
    response = api_client.post(TAGS_URL, {'name': long_name, 'slug': 'long-name'}, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_create_tag_response_fields(api_client, admin_user):
    """Created tag response contains 'id', 'name', and 'slug'."""
    api_client.force_authenticate(user=admin_user)
    response = api_client.post(TAGS_URL, {'name': 'Field Tag', 'slug': 'field-tag'}, format='json')
    assert response.status_code == status.HTTP_201_CREATED
    for field in ('id', 'name', 'slug'):
        assert field in response.data, f"Field '{field}' missing from create response"


# Cache invalidation

def test_create_tag_invalidates_cache(api_client, admin_user, tag):
    """After creating a tag, the list reflects the new entry."""
    first = api_client.get(TAGS_URL)
    count_before = len(first.data.get('results', first.data))

    api_client.force_authenticate(user=admin_user)
    api_client.post(TAGS_URL, {'name': 'Cache Bust Tag', 'slug': 'cache-bust-tag'}, format='json')
    api_client.force_authenticate(user=None)

    second = api_client.get(TAGS_URL)
    count_after = len(second.data.get('results', second.data))
    assert count_after > count_before
