"""Tests for UserBookViewSet endpoints and caching.

Covers all public CRUD endpoints accessible via the router and exercises the
custom ``cache_response`` key function as well as invalidation logic.  The
style mirrors ``apps/books/tests/test_books.py`` so that behaviour is easier
to compare.
"""

import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.books.models import Author, Book, Tag
from apps.userbooks.models import ReadingStatus, UserBook
from apps.users.models import User

pytestmark = pytest.mark.django_db

USERBOOKS_URL = reverse('userbooks')

def userbook_detail_url(pk: int) -> str:
    return reverse('userbook-detail', kwargs={'pk': pk})


# ---------------------------------------------------------------------------
# fixtures (mostly copied from apps/books/tests/test_books.py)
# ---------------------------------------------------------------------------

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
def other_user(db) -> User:
    return User.objects.create_user(  # pyright: ignore[reportAttributeAccessIssue]
        email='other@example.com',
        username='otheruser',
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
        is_staff=True,
    )


@pytest.fixture
def author(db) -> Author:
    return Author.objects.create(name='Test Author')


@pytest.fixture
def tag(db) -> Tag:
    return Tag.objects.create(name='Test Tag', slug='test-tag')


@pytest.fixture
def book(db, user, author, tag) -> Book:
    b = Book.objects.create(
        title='Test Book',
        title_en='Test Book EN',
        description='A test book.',
        book_type='book',
        pages_total=300,
        country='US',
        user=user,
    )
    b.authors.set([author])
    b.tags.set([tag])
    return b


@pytest.fixture
def userbook(db, user, book) -> UserBook:
    return UserBook.objects.create(user=user, book=book, status=ReadingStatus.READING)


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


# ---------------------------------------------------------------------------
# low-level permission / sanity tests
# ---------------------------------------------------------------------------


def test_list_requires_auth(api_client, book):
    """Unauthenticated requests cannot see userbooks."""
    response = api_client.get(USERBOOKS_URL)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_list_returns_only_own_items(api_client, user, other_user, book, userbook):
    api_client.force_authenticate(user=user)
    response = api_client.get(USERBOOKS_URL)
    assert response.status_code == status.HTTP_200_OK
    results = response.data.get('results', response.data)
    assert len(results) == 1
    assert results[0]['id'] == userbook.pk
    cache.clear()
    # make sure another user's record is not leaked
    UserBook.objects.create(user=other_user, book=book, status=ReadingStatus.READING)
    second = api_client.get(USERBOOKS_URL)
    print(type(second))
    data = second.json()
    print(data)
    results2 = second.data.get('results', second.data)
    assert len(results2) == 1


def test_retrieve_permissions(api_client, user, other_user, admin_user, userbook):
    """Only the owner or an admin may view a specific UserBook."""
    api_client.force_authenticate(user=user)
    ok = api_client.get(userbook_detail_url(userbook.pk))
    assert ok.status_code == status.HTTP_200_OK

    api_client.force_authenticate(user=other_user)
    forbidden = api_client.get(userbook_detail_url(userbook.pk))
    # other user don't need to know about existing of other users userbooks, so 404 is appropriate
    assert forbidden.status_code == status.HTTP_404_NOT_FOUND

    api_client.force_authenticate(user=admin_user)
    admin_ok = api_client.get(userbook_detail_url(userbook.pk))
    assert admin_ok.status_code == status.HTTP_200_OK


def test_create_sets_user(api_client, user, book):
    api_client.force_authenticate(user=user)
    payload = {'book': book.pk, 'status': ReadingStatus.READING}
    response = api_client.post(USERBOOKS_URL, payload, format='json')
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data['user'] == user.pk


def test_create_requires_auth(api_client, book):
    response = api_client.post(USERBOOKS_URL, {'book': book.pk, 'status': ReadingStatus.READING}, format='json')
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# caching behaviour
# ---------------------------------------------------------------------------


def test_update_forbidden_for_non_owner(api_client, other_user, userbook):
    api_client.force_authenticate(user=other_user)
    response = api_client.patch(
        userbook_detail_url(userbook.pk),
        {'status': ReadingStatus.COMPLETED},
        format='json',
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_destroy_forbidden_for_non_owner(api_client, other_user, userbook):
    api_client.force_authenticate(user=other_user)
    response = api_client.delete(userbook_detail_url(userbook.pk))
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_list_endpoint_is_cached(api_client, user, book):
    api_client.force_authenticate(user=user)
    # prime cache with a single record
    UserBook.objects.create(user=user, book=book, status=ReadingStatus.READING)
    first = api_client.get(USERBOOKS_URL)
    first_data = first.json()
    assert first.status_code == status.HTTP_200_OK

    # add a second record directly (bypass invalidation)
    UserBook.objects.get(user=user, book=book).status = ReadingStatus.COMPLETED
    UserBook.objects.get(user=user, book=book).save()
    second = api_client.get(USERBOOKS_URL)
    # it becomes django http.response.JsonResponse after caching, but the content should be the same
    second_data = second.json()
    # results should be identical because the view was served from cache
    assert second_data == first_data


def test_list_invalidation_on_create(api_client, user, book):
    api_client.force_authenticate(user=user)
    first = api_client.get(USERBOOKS_URL)
    count_before = len(first.data.get('results', first.data))

    # create via API – invalidation should occur automatically
    api_client.post(USERBOOKS_URL, {'book': book.pk, 'status': ReadingStatus.READING}, format='json')

    second = api_client.get(USERBOOKS_URL)
    count_after = len(second.data.get('results', second.data))
    assert count_after > count_before


def test_retrieve_endpoint_is_cached(api_client, user, book, userbook):
    api_client.force_authenticate(user=user)
    r1 = api_client.get(userbook_detail_url(userbook.pk))
    r1_data = r1.json()
    # mutate the database directly; cache should shield the second query
    userbook.status = ReadingStatus.COMPLETED
    userbook.save()
    r2 = api_client.get(userbook_detail_url(userbook.pk))
    # same logic as for test_list_endpoint_is_cached()
    r2_data = r2.json()
    assert r2_data == r1_data


def test_update_invalidates_cache(api_client, user, book, userbook):
    api_client.force_authenticate(user=user)
    api_client.get(userbook_detail_url(userbook.pk))  # warm cache

    api_client.patch(
        userbook_detail_url(userbook.pk),
        {'status': ReadingStatus.COMPLETED},
        format='json',
    )

    updated = api_client.get(userbook_detail_url(userbook.pk))
    assert updated.data['status'] == ReadingStatus.COMPLETED


def test_destroy_invalidates_cache(api_client, user, book, userbook):
    api_client.force_authenticate(user=user)
    api_client.get(USERBOOKS_URL)  # warm list cache

    api_client.delete(userbook_detail_url(userbook.pk))

    after = api_client.get(USERBOOKS_URL)
    ids = [i['id'] for i in after.data.get('results', after.data)]
    assert userbook.pk not in ids

