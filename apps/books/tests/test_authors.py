"""Tests for AuthorViewSet — all endpoints and all possible situations."""
import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.books.models import Author
from apps.users.models import User

pytestmark = pytest.mark.django_db

AUTHORS_URL = reverse('authors')


def author_detail_url(pk: int) -> str:
    return reverse('author-detail', kwargs={'pk': pk})



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
def author(db) -> Author:
    return Author.objects.create(name='Existing Author')


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()



# LIST  GET /api/v1/authors/


def test_list_authors_anonymous_returns_200(api_client, author):
    """Anonymous user can list authors."""
    response = api_client.get(AUTHORS_URL)
    assert response.status_code == status.HTTP_200_OK


def test_list_authors_authenticated_returns_200(api_client, user, author):
    """Authenticated user can list authors."""
    api_client.force_authenticate(user=user)
    response = api_client.get(AUTHORS_URL)
    assert response.status_code == status.HTTP_200_OK


def test_list_authors_contains_existing_author(api_client, author):
    """List response includes the author that exists in the DB."""
    response = api_client.get(AUTHORS_URL)
    results = response.data.get('results', response.data)
    ids = [item['id'] for item in results]
    assert author.pk in ids


def test_list_authors_response_fields(api_client, author):
    """Each item in the list has 'id' and 'name' fields."""
    response = api_client.get(AUTHORS_URL)
    results = response.data.get('results', response.data)
    assert len(results) > 0
    first = results[0]
    assert 'id' in first
    assert 'name' in first



# RETRIEVE  GET /api/v1/authors/<pk>/


def test_retrieve_author_anonymous_returns_200(api_client, author):
    """Anonymous user can retrieve an author by ID."""
    response = api_client.get(author_detail_url(author.pk))
    assert response.status_code == status.HTTP_200_OK
    assert response.data['id'] == author.pk
    assert response.data['name'] == author.name


def test_retrieve_author_not_found_returns_404(api_client):
    """Retrieve a non-existent author returns 404."""
    response = api_client.get(author_detail_url(9999))
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_retrieve_author_response_fields(api_client, author):
    """Retrieve response contains 'id' and 'name' fields."""
    response = api_client.get(author_detail_url(author.pk))
    assert 'id' in response.data
    assert 'name' in response.data



# CREATE  POST /api/v1/authors/


def test_create_author_authenticated_returns_201(api_client, user):
    """Any authenticated user can create an author."""
    api_client.force_authenticate(user=user)
    response = api_client.post(AUTHORS_URL, {'name': 'New Author'}, format='json')
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data['name'] == 'New Author'
    assert Author.objects.filter(name='New Author').exists()


def test_create_author_by_admin_returns_201(api_client, admin_user):
    """Admin can also create an author."""
    api_client.force_authenticate(user=admin_user)
    response = api_client.post(AUTHORS_URL, {'name': 'Admin Author'}, format='json')
    assert response.status_code == status.HTTP_201_CREATED


def test_create_author_unauthenticated_returns_401(api_client):
    """Unauthenticated request to create an author returns 401."""
    response = api_client.post(AUTHORS_URL, {'name': 'Ghost Author'}, format='json')
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert not Author.objects.filter(name='Ghost Author').exists()


def test_create_author_missing_name_returns_400(api_client, user):
    """Create author without 'name' returns 400."""
    api_client.force_authenticate(user=user)
    response = api_client.post(AUTHORS_URL, {}, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_create_author_duplicate_name_returns_400(api_client, user, author):
    """Create author with a name that already exists returns 400 (unique constraint)."""
    api_client.force_authenticate(user=user)
    response = api_client.post(AUTHORS_URL, {'name': author.name}, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_create_author_name_too_long_returns_400(api_client, user):
    """Create author with name exceeding max_length returns 400."""
    api_client.force_authenticate(user=user)
    long_name = 'A' * 256  # max_length=255
    response = api_client.post(AUTHORS_URL, {'name': long_name}, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_create_author_response_fields(api_client, user):
    """Created author response contains 'id' and 'name'."""
    api_client.force_authenticate(user=user)
    response = api_client.post(AUTHORS_URL, {'name': 'Field Check Author'}, format='json')
    assert response.status_code == status.HTTP_201_CREATED
    assert 'id' in response.data
    assert 'name' in response.data



# Cache invalidation


def test_create_author_invalidates_cache(api_client, user, author):
    """After creating an author, the list reflects the new entry."""
    first = api_client.get(AUTHORS_URL)
    count_before = len(first.data.get('results', first.data))

    api_client.force_authenticate(user=user)
    api_client.post(AUTHORS_URL, {'name': 'Cache Bust Author'}, format='json')
    api_client.force_authenticate(user=None)

    second = api_client.get(AUTHORS_URL)
    count_after = len(second.data.get('results', second.data))
    assert count_after > count_before
