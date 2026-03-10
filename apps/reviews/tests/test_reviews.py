"""Tests for ReviewViewSet and UserMeReviewsView endpoints.

Covers all HTTP methods on:
  - GET  /api/v1/books/{book_pk}/reviews/
  - POST /api/v1/books/{book_pk}/reviews/
  - GET  /api/v1/books/{book_pk}/reviews/search/
  - GET  /api/v1/books/{book_pk}/reviews/{pk}/
  - PATCH /api/v1/books/{book_pk}/reviews/{pk}/
  - DELETE /api/v1/books/{book_pk}/reviews/{pk}/
  - GET  /api/v1/users/me/reviews/
"""

import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.books.models import Author, Book
from apps.reviews.models import Review
from apps.users.models import User

pytestmark = pytest.mark.django_db


# URL helpers

def reviews_url(book_pk: int) -> str:
    return reverse('reviews', kwargs={'book_pk': book_pk})


def review_detail_url(book_pk: int, pk: int) -> str:
    return reverse('review-detail', kwargs={'book_pk': book_pk, 'pk': pk})


def review_search_url(book_pk: int) -> str:
    return reverse('review_search', kwargs={'book_pk': book_pk})


USER_ME_REVIEWS_URL = reverse('user_me_reviews')


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
def book(db, user, author) -> Book:
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
    return b


@pytest.fixture
def other_book(db, user, author) -> Book:
    b = Book.objects.create(
        title='Other Book',
        title_en='Other Book EN',
        description='Another test book.',
        book_type='book',
        pages_total=200,
        country='US',
        user=user,
    )
    b.authors.set([author])
    return b


@pytest.fixture
def review(db, user, book) -> Review:
    return Review.objects.create(
        user=user,
        book=book,
        name='Great read',
        body='This book was truly wonderful and inspiring.',
        is_public=True,
    )


@pytest.fixture
def private_review(db, user, other_book) -> Review:
    return Review.objects.create(
        user=user,
        book=other_book,
        name='My private thoughts',
        body='Some personal notes about this book.',
        is_public=False,
    )


@pytest.fixture
def other_user_review(db, other_user, book) -> Review:
    return Review.objects.create(
        user=other_user,
        book=book,
        name='Another review',
        body='Different perspective on this book.',
        is_public=True,
    )


@pytest.fixture
def other_user_private_review(db, other_user, other_book) -> Review:
    return Review.objects.create(
        user=other_user,
        book=other_book,
        name='Other private',
        body='Other user private notes.',
        is_public=False,
    )


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


def _review_payload(**overrides) -> dict:
    payload = {
        'name': 'My Review',
        'body': 'A detailed and thoughtful review of the book.',
        'is_public': True,
    }
    payload.update(overrides)
    return payload


# LIST  GET /api/v1/books/{book_pk}/reviews/

class TestReviewList:
    def test_anonymous_can_list_public_reviews(self, api_client, book, review):
        response = api_client.get(reviews_url(book.pk))
        print(response.data)
        assert response.status_code == status.HTTP_200_OK

    def test_list_returns_only_public_reviews_for_anonymous(self, api_client, book, review, other_user_private_review):
        response = api_client.get(reviews_url(book.pk))
        results = response.data.get('results', response.data)
        ids = [r['id'] for r in results]
        assert review.pk in ids
        assert other_user_private_review.pk not in ids

    def test_staff_sees_all_reviews(self, api_client, admin_user, book, review, other_user):
        private_on_book = Review.objects.create(
            user=other_user,
            book=book,
            name='Private review',
            body='Private thoughts staff should see.',
            is_public=False,
        )
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reviews_url(book.pk))
        assert response.status_code == status.HTTP_200_OK
        results = response.data.get('results', response.data)
        ids = [r['id'] for r in results]
        assert review.pk in ids
        assert private_on_book.pk in ids

    def test_list_scoped_to_book(self, api_client, book, other_book, user, author):
        review_for_book = Review.objects.create(
            user=user, book=book,
            name='About this book', body='Good book indeed.', is_public=True,
        )
        review_for_other = Review.objects.create(
            user=user, book=other_book,
            name='About other book', body='Different book review.', is_public=True,
        )
        response = api_client.get(reviews_url(book.pk))
        results = response.data.get('results', response.data)
        ids = [r['id'] for r in results]
        assert review_for_book.pk in ids
        assert review_for_other.pk not in ids

    def test_list_response_has_expected_fields(self, api_client, book, review):
        response = api_client.get(reviews_url(book.pk))
        results = response.data.get('results', response.data)
        assert len(results) > 0
        first = results[0]
        for field in ('id', 'user', 'book', 'name', 'body', 'is_public', 'created_at', 'updated_at'):
            assert field in first

    def test_list_returns_paginated_response(self, api_client, book, review):
        response = api_client.get(reviews_url(book.pk))
        assert 'results' in response.data or isinstance(response.data, list)


# CREATE  POST /api/v1/books/{book_pk}/reviews/

class TestReviewCreate:
    def test_anonymous_cannot_create(self, api_client, book):
        response = api_client.post(reviews_url(book.pk), _review_payload(), format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_authenticated_user_can_create(self, api_client, user, book):
        api_client.force_authenticate(user=user)
        response = api_client.post(reviews_url(book.pk), _review_payload(), format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert Review.objects.filter(user=user, book=book).exists()

    def test_create_sets_user_automatically(self, api_client, user, book):
        api_client.force_authenticate(user=user)
        response = api_client.post(reviews_url(book.pk), _review_payload(), format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['user'] == user.pk

    def test_create_sets_book_from_url(self, api_client, user, book):
        api_client.force_authenticate(user=user)
        response = api_client.post(reviews_url(book.pk), _review_payload(), format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['book'] == book.pk

    def test_create_private_review(self, api_client, user, book):
        api_client.force_authenticate(user=user)
        payload = _review_payload(is_public=False)
        response = api_client.post(reviews_url(book.pk), payload, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['is_public'] is False

    def test_cannot_create_review_for_nonexistent_book(self, api_client, user):
        api_client.force_authenticate(user=user)
        response = api_client.post(reviews_url(99999), _review_payload(), format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_cannot_create_duplicate_review(self, api_client, user, book, review):
        api_client.force_authenticate(user=user)
        response = api_client.post(reviews_url(book.pk), _review_payload(), format='json')
        assert response.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT)

    def test_create_invalid_name_special_chars(self, api_client, user, book):
        api_client.force_authenticate(user=user)
        response = api_client.post(reviews_url(book.pk), _review_payload(name='Bad<>Name'), format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_empty_body_returns_400(self, api_client, user, book):
        api_client.force_authenticate(user=user)
        response = api_client.post(reviews_url(book.pk), _review_payload(body=''), format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_body_with_control_chars_returns_400(self, api_client, user, book):
        api_client.force_authenticate(user=user)
        response = api_client.post(reviews_url(book.pk), _review_payload(body='Bad\x00body'), format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_body_too_long_word_returns_400(self, api_client, user, book):
        api_client.force_authenticate(user=user)
        long_word = 'a' * 201
        response = api_client.post(reviews_url(book.pk), _review_payload(body=long_word), format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_body_exceeds_max_length_returns_400(self, api_client, user, book):
        api_client.force_authenticate(user=user)
        response = api_client.post(reviews_url(book.pk), _review_payload(body='x ' * 5001), format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_name_with_control_chars_returns_400(self, api_client, user, book):
        api_client.force_authenticate(user=user)
        response = api_client.post(reviews_url(book.pk), _review_payload(name='Bad\x01Name'), format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_strips_extra_spaces_from_body(self, api_client, user, book):
        api_client.force_authenticate(user=user)
        payload = _review_payload(body='Too   many    spaces in    body.')
        response = api_client.post(reviews_url(book.pk), payload, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert '  ' not in response.data['body']

    def test_create_increments_review_count(self, api_client, user, book):
        api_client.force_authenticate(user=user)
        before = Review.objects.filter(book=book).count()
        api_client.post(reviews_url(book.pk), _review_payload(), format='json')
        assert Review.objects.filter(book=book).count() == before + 1


# RETRIEVE  GET /api/v1/books/{book_pk}/reviews/{pk}/

class TestReviewRetrieve:
    def test_anonymous_can_retrieve_public_review(self, api_client, book, review):
        response = api_client.get(review_detail_url(book.pk, review.pk))
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == review.pk

    def test_anonymous_cannot_retrieve_private_review(self, api_client, book, private_review):
        response = api_client.get(review_detail_url(book.pk, private_review.pk))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_owner_can_retrieve_own_private_review(self, api_client, user, other_book, private_review):
        api_client.force_authenticate(user=user)
        response = api_client.get(review_detail_url(other_book.pk, private_review.pk))
        print(response.data)
        assert response.status_code == status.HTTP_200_OK

    def test_other_user_cannot_retrieve_private_review(self, api_client, other_user, book, private_review):
        api_client.force_authenticate(user=other_user)
        response = api_client.get(review_detail_url(book.pk, private_review.pk))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_staff_can_retrieve_any_private_review(self, api_client, admin_user, other_book, private_review):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(review_detail_url(other_book.pk, private_review.pk))
        assert response.status_code == status.HTTP_200_OK

    def test_retrieve_nonexistent_review_returns_404(self, api_client, book):
        response = api_client.get(review_detail_url(book.pk, 99999))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_retrieve_review_from_wrong_book_returns_404(self, api_client, book, other_book, other_user):
        review_on_other_book = Review.objects.create(
            user=other_user, book=other_book,
            name='Other book review', body='Review for another book.', is_public=True,
        )
        response = api_client.get(review_detail_url(book.pk, review_on_other_book.pk))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_retrieve_response_has_expected_fields(self, api_client, book, review):
        response = api_client.get(review_detail_url(book.pk, review.pk))
        for field in ('id', 'user', 'book', 'name', 'body', 'is_public', 'created_at', 'updated_at'):
            assert field in response.data


# PARTIAL UPDATE  PATCH /api/v1/books/{book_pk}/reviews/{pk}/

class TestReviewPartialUpdate:
    def test_anonymous_cannot_update(self, api_client, book, review):
        response = api_client.patch(review_detail_url(book.pk, review.pk), {'name': 'New name'}, format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_other_user_cannot_update(self, api_client, other_user, book, review):
        api_client.force_authenticate(user=other_user)
        response = api_client.patch(review_detail_url(book.pk, review.pk), {'name': 'Stolen update'}, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_owner_can_update_name(self, api_client, user, book, review):
        api_client.force_authenticate(user=user)
        response = api_client.patch(review_detail_url(book.pk, review.pk), {'name': 'Updated name'}, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == 'Updated name'

    def test_owner_can_update_body(self, api_client, user, book, review):
        api_client.force_authenticate(user=user)
        response = api_client.patch(review_detail_url(book.pk, review.pk), {'body': 'Updated body text here.'}, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['body'] == 'Updated body text here.'

    def test_owner_can_toggle_visibility(self, api_client, user, book, review):
        api_client.force_authenticate(user=user)
        response = api_client.patch(review_detail_url(book.pk, review.pk), {'is_public': False}, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['is_public'] is False

    def test_admin_can_update_any_review(self, api_client, admin_user, book, review):
        print(admin_user.username)
        print(admin_user.is_staff)
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(review_detail_url(book.pk, review.pk), {'name': 'Admin edit'}, format='json')
        print(response.data)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == 'Admin edit'

    def test_update_invalid_name_returns_400(self, api_client, user, book, review):
        api_client.force_authenticate(user=user)
        response = api_client.patch(review_detail_url(book.pk, review.pk), {'name': '<script>xss</script>'}, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_update_empty_body_returns_400(self, api_client, user, book, review):
        api_client.force_authenticate(user=user)
        response = api_client.patch(review_detail_url(book.pk, review.pk), {'body': ''}, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_update_body_with_control_chars_returns_400(self, api_client, user, book, review):
        api_client.force_authenticate(user=user)
        response = api_client.patch(review_detail_url(book.pk, review.pk), {'body': 'Bad\x02body'}, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_put_method_not_allowed(self, api_client, user, book, review):
        api_client.force_authenticate(user=user)
        response = api_client.put(review_detail_url(book.pk, review.pk), _review_payload(), format='json')
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_update_persists_to_db(self, api_client, user, book, review):
        api_client.force_authenticate(user=user)
        api_client.patch(review_detail_url(book.pk, review.pk), {'name': 'Persisted'}, format='json')
        review.refresh_from_db()
        assert review.name == 'Persisted'


# DESTROY  DELETE /api/v1/books/{book_pk}/reviews/{pk}/

class TestReviewDestroy:
    def test_anonymous_cannot_delete(self, api_client, book, review):
        response = api_client.delete(review_detail_url(book.pk, review.pk))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_other_user_cannot_delete(self, api_client, other_user, book, review):
        api_client.force_authenticate(user=other_user)
        response = api_client.delete(review_detail_url(book.pk, review.pk))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_owner_can_delete_own_review(self, api_client, user, book, review):
        api_client.force_authenticate(user=user)
        response = api_client.delete(review_detail_url(book.pk, review.pk))
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Review.objects.filter(pk=review.pk).exists()

    def test_admin_can_delete_any_review(self, api_client, admin_user, book, review):
        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(review_detail_url(book.pk, review.pk))
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Review.objects.filter(pk=review.pk).exists()

    def test_delete_nonexistent_returns_404(self, api_client, user, book):
        api_client.force_authenticate(user=user)
        response = api_client.delete(review_detail_url(book.pk, 99999))
        assert response.status_code == status.HTTP_404_NOT_FOUND


# SEARCH  GET /api/v1/books/{book_pk}/reviews/search/

class TestReviewSearch:
    def test_search_requires_query_param(self, api_client, book):
        response = api_client.get(review_search_url(book.pk))
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'detail' in response.data

    def test_anonymous_can_search(self, api_client, book, review):
        response = api_client.get(review_search_url(book.pk), {'query': 'wonderful'})
        assert response.status_code == status.HTTP_200_OK

    def test_authenticated_user_can_search(self, api_client, user, book, review):
        api_client.force_authenticate(user=user)
        response = api_client.get(review_search_url(book.pk), {'query': 'wonderful'})
        assert response.status_code == status.HTTP_200_OK

    def test_search_returns_matching_reviews(self, api_client, book, review):
        response = api_client.get(review_search_url(book.pk), {'query': 'wonderful inspiring'})
        assert response.status_code == status.HTTP_200_OK
        results = response.data.get('results', response.data)
        ids = [r['id'] for r in results]
        assert review.pk in ids

    def test_search_scoped_to_book(self, api_client, book, other_book, user):
        review_on_other = Review.objects.create(
            user=user, book=other_book,
            name='Unique term xyzzy', body='Featuring the word xyzzy prominently.',
            is_public=True,
        )
        response = api_client.get(review_search_url(book.pk), {'query': 'xyzzy'})
        results = response.data.get('results', response.data)
        ids = [r['id'] for r in results]
        assert review_on_other.pk not in ids


# USER ME REVIEWS  GET /api/v1/users/me/reviews/

class TestUserMeReviews:
    def test_anonymous_cannot_access(self, api_client):
        response = api_client.get(USER_ME_REVIEWS_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_authenticated_user_can_list_own_reviews(self, api_client, user, book, review):
        api_client.force_authenticate(user=user)
        response = api_client.get(USER_ME_REVIEWS_URL)
        assert response.status_code == status.HTTP_200_OK
        results = response.data.get('results', response.data)
        ids = [r['id'] for r in results]
        assert review.pk in ids

    def test_returns_private_reviews_of_authenticated_user(self, api_client, user, book, private_review):
        api_client.force_authenticate(user=user)
        response = api_client.get(USER_ME_REVIEWS_URL)
        assert response.status_code == status.HTTP_200_OK
        results = response.data.get('results', response.data)
        ids = [r['id'] for r in results]
        assert private_review.pk in ids

    def test_does_not_return_other_users_reviews(self, api_client, user, book, other_user_review, other_user_private_review):
        api_client.force_authenticate(user=user)
        response = api_client.get(USER_ME_REVIEWS_URL)
        results = response.data.get('results', response.data)
        ids = [r['id'] for r in results]
        assert other_user_review.pk not in ids
        assert other_user_private_review.pk not in ids

    def test_returns_all_own_reviews_including_private(self, api_client, user, book, review, private_review, other_user_review):
        api_client.force_authenticate(user=user)
        response = api_client.get(USER_ME_REVIEWS_URL)
        results = response.data.get('results', response.data)
        ids = [r['id'] for r in results]
        assert review.pk in ids
        assert private_review.pk in ids
        assert other_user_review.pk not in ids


# CACHE INVALIDATION

class TestReviewCacheInvalidation:
    def test_create_invalidates_list_cache(self, api_client, user, book):
        api_client.force_authenticate(user=user)
        # Warm the cache
        api_client.get(reviews_url(book.pk))
        # Create a new review
        response = api_client.post(reviews_url(book.pk), _review_payload(), format='json')
        assert response.status_code == status.HTTP_201_CREATED
        # The new review should appear in a fresh list fetch
        list_response = api_client.get(reviews_url(book.pk))
        results = list_response.data.get('results', list_response.data)
        ids = [r['id'] for r in results]
        assert response.data['id'] in ids

    def test_update_invalidates_list_cache(self, api_client, user, book, review):
        api_client.force_authenticate(user=user)
        api_client.get(reviews_url(book.pk))
        api_client.patch(review_detail_url(book.pk, review.pk), {'name': 'Cache busted'}, format='json')
        list_response = api_client.get(reviews_url(book.pk))
        results = list_response.data.get('results', list_response.data)
        names = [r['name'] for r in results]
        assert 'Cache busted' in names

    def test_delete_removes_review_from_list(self, api_client, user, book, review):
        api_client.force_authenticate(user=user)
        api_client.get(reviews_url(book.pk))
        api_client.delete(review_detail_url(book.pk, review.pk))
        list_response = api_client.get(reviews_url(book.pk))
        results = list_response.data.get('results', list_response.data)
        ids = [r['id'] for r in results]
        assert review.pk not in ids
