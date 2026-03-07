"""Tests for BookViewSet — all endpoints and all possible situations."""
import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.books.models import AUTHOR_MAX_COUNT, TAG_MAX_COUNT, Author, Book, Tag
from apps.users.models import User

pytestmark = pytest.mark.django_db

BOOKS_URL = reverse('books')


def books_detail_url(pk: int) -> str:
    return reverse('book_detail', kwargs={'pk': pk})


# ---------------------------------------------------------------------------
# Shared fixtures
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


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


# Helper: minimal valid payload for a 'book' type

def _book_payload(author: Author, tag: Tag | None = None, **overrides) -> dict:
    payload = {
        'title': 'New Book',
        'title_en': 'New Book EN',
        'authors': [author.pk],
        'book_type': 'book',
        'description': 'Some description.',
        'pages_total': 200,
        'country': 'US',
        'tags': [tag.pk] if tag else [],
    }
    payload.update(overrides)
    return payload



# LIST  GET /api/v1/books/


def test_list_books_anonymous_returns_200(api_client, book):
    """Anonymous user can list books."""
    response = api_client.get(BOOKS_URL)
    assert response.status_code == status.HTTP_200_OK


def test_list_books_authenticated_returns_200(api_client, user, book):
    """Authenticated user can list books."""
    api_client.force_authenticate(user=user)
    response = api_client.get(BOOKS_URL)
    assert response.status_code == status.HTTP_200_OK


def test_list_books_contains_annotated_fields(api_client, book):
    """Each book in the list response contains average_rating and ratings_count."""
    response = api_client.get(BOOKS_URL)
    assert response.status_code == status.HTTP_200_OK
    results = response.data.get('results', response.data)
    assert len(results) > 0
    first = results[0]
    assert 'average_rating' in first
    assert 'ratings_count' in first


def test_list_books_only_returns_existing_books(api_client, book):
    """The list contains exactly the books that exist in the DB."""
    response = api_client.get(BOOKS_URL)
    results = response.data.get('results', response.data)
    ids = [item['id'] for item in results]
    assert book.pk in ids



# RETRIEVE  GET /api/v1/books/<pk>/


def test_retrieve_book_anonymous_returns_200(api_client, book):
    """Anonymous user can retrieve a book by ID."""
    response = api_client.get(books_detail_url(book.pk))
    assert response.status_code == status.HTTP_200_OK
    assert response.data['id'] == book.pk
    assert response.data['title'] == book.title


def test_retrieve_book_contains_all_expected_fields(api_client, book):
    """Retrieve response contains all expected fields including annotations."""
    response = api_client.get(books_detail_url(book.pk))
    expected_fields = (
        'id', 'title', 'title_en', 'cover', 'authors', 'description',
        'tags', 'book_type', 'country', 'pages_total', 'chapters_total',
        'edition', 'parent_book', 'user', 'average_rating', 'ratings_count',
        'created_at', 'updated_at',
    )
    for field in expected_fields:
        assert field in response.data, f"Field '{field}' missing from retrieve response"


def test_retrieve_book_not_found_returns_404(api_client):
    """Retrieve a non-existent book returns 404."""
    response = api_client.get(books_detail_url(9999))
    assert response.status_code == status.HTTP_404_NOT_FOUND



# CREATE  POST /api/v1/books/


def test_create_book_authenticated_returns_201(api_client, user, author, tag):
    """Authenticated user can create a book."""
    api_client.force_authenticate(user=user)
    response = api_client.post(BOOKS_URL, _book_payload(author, tag), format='json')
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data['title'] == 'New Book'


def test_create_book_sets_user_to_requester(api_client, user, author, tag):
    """New book's 'user' field is automatically set to the requesting user."""
    api_client.force_authenticate(user=user)
    response = api_client.post(BOOKS_URL, _book_payload(author, tag), format='json')
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data['user'] == user.pk


def test_create_book_unauthenticated_returns_401(api_client, author, tag):
    """Unauthenticated request to create a book returns 401."""
    response = api_client.post(BOOKS_URL, _book_payload(author, tag), format='json')
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_create_book_missing_title_returns_400(api_client, user, author, tag):
    """Create book without 'title' returns 400."""
    api_client.force_authenticate(user=user)
    payload = _book_payload(author, tag)
    del payload['title']
    response = api_client.post(BOOKS_URL, payload, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_create_book_missing_title_en_returns_400(api_client, user, author, tag):
    """Create book without 'title_en' returns 400."""
    api_client.force_authenticate(user=user)
    payload = _book_payload(author, tag)
    del payload['title_en']
    response = api_client.post(BOOKS_URL, payload, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_create_book_missing_authors_returns_400(api_client, user, author, tag):
    """Create book without 'authors' returns 400."""
    api_client.force_authenticate(user=user)
    payload = _book_payload(author, tag)
    del payload['authors']
    response = api_client.post(BOOKS_URL, payload, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_create_book_missing_book_type_returns_400(api_client, user, author, tag):
    """Create book without 'book_type' returns 400."""
    api_client.force_authenticate(user=user)
    payload = _book_payload(author, tag)
    del payload['book_type']
    response = api_client.post(BOOKS_URL, payload, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_create_book_invalid_book_type_returns_400(api_client, user, author, tag):
    """Create book with an unknown 'book_type' returns 400."""
    api_client.force_authenticate(user=user)
    payload = _book_payload(author, tag, book_type='magazine')
    response = api_client.post(BOOKS_URL, payload, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_create_book_type_book_without_pages_total_returns_400(api_client, user, author, tag):
    """Create book with type 'book' and no 'pages_total' returns 400."""
    api_client.force_authenticate(user=user)
    payload = _book_payload(author, tag)
    del payload['pages_total']
    response = api_client.post(BOOKS_URL, payload, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_create_book_type_comic_without_chapters_total_returns_400(api_client, user, author, tag):
    """Create comic without 'chapters_total' returns 400."""
    api_client.force_authenticate(user=user)
    payload = _book_payload(author, tag, book_type='comic', pages_total=None)
    response = api_client.post(BOOKS_URL, payload, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_create_book_type_comic_with_chapters_total_returns_201(api_client, user, author, tag):
    """Create comic with 'chapters_total' succeeds."""
    api_client.force_authenticate(user=user)
    payload = _book_payload(author, tag, book_type='comic', pages_total=None, chapters_total=50)
    response = api_client.post(BOOKS_URL, payload, format='json')
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data['chapters_total'] == 50


def test_create_book_too_many_authors_returns_400(api_client, user, db):
    """Create book exceeding AUTHOR_MAX_COUNT authors returns 400."""
    authors = [Author.objects.create(name=f'Author {i}') for i in range(AUTHOR_MAX_COUNT + 1)]
    api_client.force_authenticate(user=user)
    payload = {
        'title': 'Book',
        'title_en': 'Book EN',
        'authors': [a.pk for a in authors],
        'book_type': 'book',
        'pages_total': 100,
    }
    response = api_client.post(BOOKS_URL, payload, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_create_book_too_many_tags_returns_400(api_client, user, author, db):
    """Create book exceeding TAG_MAX_COUNT tags returns 400."""
    tags = [Tag.objects.create(name=f'Tag {i}', slug=f'tag-{i}') for i in range(TAG_MAX_COUNT + 1)]
    api_client.force_authenticate(user=user)
    payload = {
        'title': 'Book',
        'title_en': 'Book EN',
        'authors': [author.pk],
        'book_type': 'book',
        'pages_total': 100,
        'tags': [t.pk for t in tags],
    }
    response = api_client.post(BOOKS_URL, payload, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_create_book_with_nonexistent_author_returns_400(api_client, user):
    """Reference to a non-existent author PK returns 400."""
    api_client.force_authenticate(user=user)
    payload = {
        'title': 'Book',
        'title_en': 'Book EN',
        'authors': [99999],
        'book_type': 'book',
        'pages_total': 100,
    }
    response = api_client.post(BOOKS_URL, payload, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_create_book_with_nonexistent_tag_returns_400(api_client, user, author):
    """Reference to a non-existent tag PK returns 400."""
    api_client.force_authenticate(user=user)
    payload = _book_payload(author)
    payload['tags'] = [99999]
    response = api_client.post(BOOKS_URL, payload, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_create_book_response_has_zero_ratings(api_client, user, author, tag):
    """Newly created book has ratings_count=0 and average_rating=None on retrieve.

    The create response uses BookWriteSerializer applied to the unsaved instance,
    so the queryset annotations are absent there; they appear on GET retrieve.
    """
    api_client.force_authenticate(user=user)
    create_resp = api_client.post(BOOKS_URL, _book_payload(author, tag), format='json')
    assert create_resp.status_code == status.HTTP_201_CREATED
    book_id = create_resp.data['id']

    retrieve_resp = api_client.get(books_detail_url(book_id))
    assert retrieve_resp.status_code == status.HTTP_200_OK
    assert retrieve_resp.data['ratings_count'] == 0
    assert retrieve_resp.data['average_rating'] is None



# UPDATE  PUT /api/v1/books/<pk>/


def test_update_book_by_owner_returns_200(api_client, user, book, author, tag):
    """Owner can fully replace a book."""
    api_client.force_authenticate(user=user)
    payload = _book_payload(author, tag, title='Updated Title', title_en='Updated EN')
    response = api_client.put(books_detail_url(book.pk), payload, format='json')
    assert response.status_code == status.HTTP_200_OK
    assert response.data['title'] == 'Updated Title'


def test_update_book_by_admin_returns_200(api_client, admin_user, book, author, tag):
    """Admin can fully replace any book."""
    api_client.force_authenticate(user=admin_user)
    payload = _book_payload(author, tag, title='Admin Updated', title_en='Admin EN')
    response = api_client.put(books_detail_url(book.pk), payload, format='json')
    assert response.status_code == status.HTTP_200_OK
    assert response.data['title'] == 'Admin Updated'


def test_update_book_by_non_owner_returns_403(api_client, other_user, book, author, tag):
    """Non-owner receives 403 on PUT."""
    api_client.force_authenticate(user=other_user)
    payload = _book_payload(author, tag, title='Hijacked')
    response = api_client.put(books_detail_url(book.pk), payload, format='json')
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_update_book_unauthenticated_returns_401(api_client, book, author, tag):
    """Unauthenticated PUT returns 401."""
    payload = _book_payload(author, tag, title='Hijacked')
    response = api_client.put(books_detail_url(book.pk), payload, format='json')
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_update_book_not_found_returns_404(api_client, user, author, tag):
    """PUT on non-existent book returns 404."""
    api_client.force_authenticate(user=user)
    response = api_client.put(books_detail_url(9999), _book_payload(author, tag), format='json')
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_update_book_invalid_data_returns_400(api_client, user, book, author):
    """PUT with missing required fields returns 400."""
    api_client.force_authenticate(user=user)
    response = api_client.put(books_detail_url(book.pk), {'title': ''}, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_update_book_type_book_removes_pages_total_returns_400(api_client, user, book, author, tag):
    """PUT on 'book' type without pages_total returns 400."""
    api_client.force_authenticate(user=user)
    payload = _book_payload(author, tag)
    del payload['pages_total']
    response = api_client.put(books_detail_url(book.pk), payload, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST



# PARTIAL UPDATE  PATCH /api/v1/books/<pk>/


def test_partial_update_book_by_owner_returns_200(api_client, user, book):
    """Owner can patch individual fields.

    BookWriteSerializer.validate() checks pages_total when book_type is 'book'
    even on partial updates, so pages_total must be included in the payload.
    """
    api_client.force_authenticate(user=user)
    response = api_client.patch(
        books_detail_url(book.pk),
        {'title': 'Patched', 'pages_total': 300},
        format='json',
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data['title'] == 'Patched'


def test_partial_update_book_by_admin_returns_200(api_client, admin_user, book):
    """Admin can patch any book.

    pages_total is included alongside country to satisfy the cross-field validation
    in BookWriteSerializer.validate() (which does not inspect self.partial).
    """
    api_client.force_authenticate(user=admin_user)
    response = api_client.patch(
        books_detail_url(book.pk),
        {'country': 'DE', 'pages_total': 300},
        format='json',
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data['country'] == 'DE'


def test_partial_update_book_by_non_owner_returns_403(api_client, other_user, book):
    """Non-owner receives 403 on PATCH."""
    api_client.force_authenticate(user=other_user)
    response = api_client.patch(books_detail_url(book.pk), {'title': 'Hijacked'}, format='json')
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_partial_update_book_unauthenticated_returns_401(api_client, book):
    """Unauthenticated PATCH returns 401."""
    response = api_client.patch(books_detail_url(book.pk), {'title': 'Hijacked'}, format='json')
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_partial_update_book_not_found_returns_404(api_client, user):
    """PATCH on non-existent book returns 404."""
    api_client.force_authenticate(user=user)
    response = api_client.patch(books_detail_url(9999), {'title': 'x'}, format='json')
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_partial_update_book_invalid_field_value_returns_400(api_client, user, book):
    """PATCH with an invalid value for a field returns 400."""
    api_client.force_authenticate(user=user)
    response = api_client.patch(books_detail_url(book.pk), {'book_type': 'invalid'}, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST



# DESTROY  DELETE /api/v1/books/<pk>/


def test_destroy_book_by_owner_returns_204(api_client, user, book):
    """Owner can delete their book."""
    api_client.force_authenticate(user=user)
    response = api_client.delete(books_detail_url(book.pk))
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not Book.objects.filter(pk=book.pk).exists()


def test_destroy_book_by_admin_returns_204(api_client, admin_user, book):
    """Admin can delete any book."""
    api_client.force_authenticate(user=admin_user)
    response = api_client.delete(books_detail_url(book.pk))
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not Book.objects.filter(pk=book.pk).exists()


def test_destroy_book_by_non_owner_returns_403(api_client, other_user, book):
    """Non-owner receives 403 on DELETE and book is not deleted."""
    api_client.force_authenticate(user=other_user)
    response = api_client.delete(books_detail_url(book.pk))
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert Book.objects.filter(pk=book.pk).exists()


def test_destroy_book_unauthenticated_returns_401(api_client, book):
    """Unauthenticated DELETE returns 401 and book is not deleted."""
    response = api_client.delete(books_detail_url(book.pk))
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert Book.objects.filter(pk=book.pk).exists()


def test_destroy_book_not_found_returns_404(api_client, user):
    """DELETE on non-existent book returns 404."""
    api_client.force_authenticate(user=user)
    response = api_client.delete(books_detail_url(9999))
    assert response.status_code == status.HTTP_404_NOT_FOUND



# Cache invalidation


def test_create_book_invalidates_cache(api_client, user, author, tag, book):
    """After creating a book, subsequent GET reflects the new entry."""
    # Warm cache
    first = api_client.get(BOOKS_URL)
    count_before = len(first.data.get('results', first.data))

    # Create a new book (should invalidate cache)
    api_client.force_authenticate(user=user)
    api_client.post(
        BOOKS_URL,
        _book_payload(author, tag, title='Cache Test Book', title_en='Cache Test EN'),
        format='json',
    )
    api_client.force_authenticate(user=None)

    second = api_client.get(BOOKS_URL)
    count_after = len(second.data.get('results', second.data))
    assert count_after > count_before


def test_update_book_invalidates_cache(api_client, user, book, author, tag):
    """After updating a book, subsequent GET returns updated data."""
    # Warm cache
    api_client.get(books_detail_url(book.pk))

    api_client.force_authenticate(user=user)
    # Include pages_total so BookWriteSerializer cross-field validation passes.
    api_client.patch(
        books_detail_url(book.pk),
        {'title': 'Post-Cache Title', 'pages_total': 300},
        format='json',
    )
    api_client.force_authenticate(user=None)

    response = api_client.get(books_detail_url(book.pk))
    assert response.data['title'] == 'Post-Cache Title'


def test_destroy_book_invalidates_cache(api_client, user, book):
    """After deleting a book, subsequent GET list no longer includes it."""
    api_client.force_authenticate(user=user)
    api_client.delete(books_detail_url(book.pk))
    api_client.force_authenticate(user=None)

    response = api_client.get(BOOKS_URL)
    ids = [item['id'] for item in response.data.get('results', response.data)]
    assert book.pk not in ids
