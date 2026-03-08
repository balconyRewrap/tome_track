"""Tests for BookViewSet search action — GET /api/v1/books/search/."""
import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.books.models import Author, Book, Tag
from apps.users.models import User

pytestmark = pytest.mark.django_db

SEARCH_URL = reverse('book_search')


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
def author(db) -> Author:
    return Author.objects.create(name='Frank Herbert')


@pytest.fixture
def other_author(db) -> Author:
    return Author.objects.create(name='Isaac Asimov')


@pytest.fixture
def tag(db) -> Tag:
    return Tag.objects.create(name='Sci-Fi', slug='sci-fi')


@pytest.fixture
def other_tag(db) -> Tag:
    return Tag.objects.create(name='Fantasy', slug='fantasy')


@pytest.fixture
def book(db, user, author, tag) -> Book:
    b = Book.objects.create(
        title='Dune',
        title_en='Dune',
        description='A sci-fi epic set in the desert.',
        book_type='book',
        pages_total=412,
        country='US',
        user=user,
    )
    b.authors.set([author])
    b.tags.set([tag])
    return b


@pytest.fixture
def other_book(db, user, other_author, other_tag) -> Book:
    b = Book.objects.create(
        title='Foundation',
        title_en='Foundation',
        description='A classic science fiction saga.',
        book_type='book',
        pages_total=244,
        country='US',
        user=user,
    )
    b.authors.set([other_author])
    b.tags.set([other_tag])
    return b


@pytest.fixture
def comic_book(db, user, author) -> Book:
    b = Book.objects.create(
        title='Dune Comic',
        title_en='Dune Comic',
        description='Dune in comic form.',
        book_type='comic',
        chapters_total=12,
        country='FR',
        user=user,
    )
    b.authors.set([author])
    return b


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()



# Access

def test_search_anonymous_returns_200(api_client, book):
    """Anonymous user can access the search endpoint."""
    response = api_client.get(SEARCH_URL)
    assert response.status_code == status.HTTP_200_OK


def test_search_authenticated_returns_200(api_client, user, book):
    """Authenticated user can access the search endpoint."""
    api_client.force_authenticate(user=user)
    response = api_client.get(SEARCH_URL)
    assert response.status_code == status.HTTP_200_OK


def test_search_only_allows_get(api_client, user):
    """POST to search endpoint returns 405 Method Not Allowed."""
    # we authentificate, because DRF firstly check POST as create method, which need authentification
    api_client.force_authenticate(user=user)
    response = api_client.post(SEARCH_URL, {}, format='json')
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


# No query — returns all books

def test_search_no_q_returns_all_books(api_client, book, other_book):
    """Search without q returns all books."""
    response = api_client.get(SEARCH_URL)
    assert response.status_code == status.HTTP_200_OK
    results = response.data.get('results', response.data)
    ids = [item['id'] for item in results]
    assert book.pk in ids
    assert other_book.pk in ids


def test_search_no_q_empty_database_returns_empty(api_client):
    """Search without q on an empty dataset returns empty results."""
    response = api_client.get(SEARCH_URL)
    results = response.data.get('results', response.data)
    assert results == []


# Title matching

def test_search_exact_title_returns_book(api_client, book, other_book):
    """Searching for the exact title returns the matching book."""
    response = api_client.get(SEARCH_URL, {'q': 'Dune'})
    assert response.status_code == status.HTTP_200_OK
    results = response.data.get('results', response.data)
    ids = [item['id'] for item in results]
    assert book.pk in ids


def test_search_exact_title_excludes_unrelated_book(api_client, book, other_book):
    """An unrelated book is not returned when searching for a specific title."""
    response = api_client.get(SEARCH_URL, {'q': 'Foundation'})
    results = response.data.get('results', response.data)
    ids = [item['id'] for item in results]
    assert other_book.pk in ids
    assert book.pk not in ids


def test_search_no_match_returns_empty(api_client, book, other_book):
    """Query that doesn't match any book returns an empty result."""
    response = api_client.get(SEARCH_URL, {'q': 'xyzxyzxyzqqqq'})
    results = response.data.get('results', response.data)
    assert results == []


def test_search_trigram_typo_returns_book(api_client, book):
    """Slight typo in query still matches the book via trigram similarity."""
    # 'Dunee' vs 'Dune' — trigram similarity is above 0.2
    response = api_client.get(SEARCH_URL, {'q': 'Dunee'})
    assert response.status_code == status.HTTP_200_OK
    results = response.data.get('results', response.data)
    ids = [item['id'] for item in results]
    assert book.pk in ids


def test_search_title_en_is_matched(api_client, db, user, author):
    """Search matches title_en when the English title differs from title."""
    b = Book.objects.create(
        title='Дюна',
        title_en='Dune',
        description='Russian edition.',
        book_type='book',
        pages_total=400,
        user=user,
    )
    b.authors.set([author])

    response = api_client.get(SEARCH_URL, {'q': 'Dune'})
    results = response.data.get('results', response.data)
    ids = [item['id'] for item in results]
    assert b.pk in ids


# Filters

def test_search_filter_by_author(api_client, book, other_book, author, other_author):
    """Filter by author ID returns only books by that author."""
    response = api_client.get(SEARCH_URL, {'author': author.pk})
    results = response.data.get('results', response.data)
    ids = [item['id'] for item in results]
    assert book.pk in ids
    assert other_book.pk not in ids


def test_search_filter_by_tag(api_client, book, other_book, tag, other_tag):
    """Filter by tag ID returns only books with that tag."""
    response = api_client.get(SEARCH_URL, {'tag': tag.pk})
    results = response.data.get('results', response.data)
    ids = [item['id'] for item in results]
    assert book.pk in ids
    assert other_book.pk not in ids


def test_search_filter_by_book_type_book(api_client, book, comic_book):
    """Filter book_type=book returns only regular books, not comics."""
    response = api_client.get(SEARCH_URL, {'book_type': 'book'})
    results = response.data.get('results', response.data)
    ids = [item['id'] for item in results]
    assert book.pk in ids
    assert comic_book.pk not in ids


def test_search_filter_by_book_type_comic(api_client, book, comic_book):
    """Filter book_type=comic returns only comics."""
    response = api_client.get(SEARCH_URL, {'book_type': 'comic'})
    results = response.data.get('results', response.data)
    ids = [item['id'] for item in results]
    assert comic_book.pk in ids
    assert book.pk not in ids


def test_search_filter_by_country(api_client, book, comic_book):
    """Filter by country (icontains) returns only books from that country."""
    response = api_client.get(SEARCH_URL, {'country': 'FR'})
    results = response.data.get('results', response.data)
    ids = [item['id'] for item in results]
    assert comic_book.pk in ids
    assert book.pk not in ids


def test_search_filter_by_country_is_case_insensitive(api_client, book):
    """Country filter is case-insensitive."""
    response_lower = api_client.get(SEARCH_URL, {'country': 'us'})
    results = response_lower.data.get('results', response_lower.data)
    ids = [item['id'] for item in results]
    assert book.pk in ids


def test_search_q_combined_with_author_filter(api_client, book, other_book, author):
    """Combining q with author filter narrows results."""
    response = api_client.get(SEARCH_URL, {'q': 'Foundation', 'author': author.pk})
    results = response.data.get('results', response.data)
    ids = [item['id'] for item in results]
    # other_book matches 'Foundation' but belongs to other_author
    assert other_book.pk not in ids


def test_search_q_combined_with_book_type_filter(api_client, book, comic_book):
    """Combining q with book_type filter narrows results."""
    response = api_client.get(SEARCH_URL, {'q': 'Dune', 'book_type': 'book'})
    results = response.data.get('results', response.data)
    ids = [item['id'] for item in results]
    assert book.pk in ids
    assert comic_book.pk not in ids


def test_search_invalid_book_type_returns_400(api_client, book):
    """An invalid book_type value causes a 400 response from the filter."""
    response = api_client.get(SEARCH_URL, {'book_type': 'magazine'})
    print(response.data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


# Response shape

def test_search_results_contain_annotated_fields(api_client, book):
    """Each result in the search response contains average_rating and ratings_count."""
    response = api_client.get(SEARCH_URL)
    results = response.data.get('results', response.data)
    assert len(results) > 0
    first = results[0]
    assert 'average_rating' in first
    assert 'ratings_count' in first


def test_search_results_are_paginated(api_client, db, user, author):
    """Search response uses pagination (contains 'results' key)."""
    for i in range(5):
        b = Book.objects.create(
            title=f'Book {i}',
            title_en=f'Book {i} EN',
            description='desc',
            book_type='book',
            pages_total=100,
            user=user,
        )
        b.authors.set([author])

    response = api_client.get(SEARCH_URL)
    assert response.status_code == status.HTTP_200_OK
    assert 'results' in response.data
    assert 'count' in response.data


# Caching

def test_search_response_is_cached(api_client, book):
    """Second identical request returns the same data (served from cache)."""
    response1 = api_client.get(SEARCH_URL, {'q': 'Dune'})
    response2 = api_client.get(SEARCH_URL, {'q': 'Dune'})
    assert response1.status_code == status.HTTP_200_OK
    assert response2.status_code == status.HTTP_200_OK
    assert response1.data == response2.data


def test_search_cache_invalidated_on_create(api_client, user, author, tag, book):
    """Creating a book invalidates the search cache so new results are reflected."""
    # Warm the cache with the initial state (only 'book' exists)
    response_before = api_client.get(SEARCH_URL)
    results_before = response_before.data.get('results', response_before.data)
    count_before = len(results_before)

    # Create a new book
    api_client.force_authenticate(user=user)
    new_book_data = {
        'title': 'Messiah',
        'title_en': 'Dune Messiah',
        'authors': [author.pk],
        'book_type': 'book',
        'description': 'Second Dune novel.',
        'pages_total': 330,
        'tags': [tag.pk],
        'country': 'US',
    }
    create_resp = api_client.post(reverse('books'), new_book_data, format='json')
    assert create_resp.status_code == status.HTTP_201_CREATED

    api_client.logout()
    response_after = api_client.get(SEARCH_URL)
    results_after = response_after.data.get('results', response_after.data)
    assert len(results_after) > count_before


def test_search_cache_invalidated_on_destroy(api_client, user, book):
    """Deleting a book invalidates the search cache."""
    # Warm the cache
    response_before = api_client.get(SEARCH_URL)
    results_before = response_before.data.get('results', response_before.data)
    assert any(item['id'] == book.pk for item in results_before)

    # Delete the book
    api_client.force_authenticate(user=user)
    delete_resp = api_client.delete(reverse('book_detail', kwargs={'pk': book.pk}))
    assert delete_resp.status_code == status.HTTP_204_NO_CONTENT

    api_client.logout()
    response_after = api_client.get(SEARCH_URL)
    results_after = response_after.data.get('results', response_after.data)
    assert not any(item['id'] == book.pk for item in results_after)


def test_search_different_queries_have_independent_caches(api_client, book, other_book):
    """Different query params produce independently cached results."""
    response_dune = api_client.get(SEARCH_URL, {'q': 'Dune'})
    response_foundation = api_client.get(SEARCH_URL, {'q': 'Foundation'})

    ids_dune = [item['id'] for item in response_dune.data.get('results', response_dune.data)]
    ids_foundation = [item['id'] for item in response_foundation.data.get('results', response_foundation.data)]

    assert book.pk in ids_dune
    assert other_book.pk not in ids_dune
    assert other_book.pk in ids_foundation
    assert book.pk not in ids_foundation
