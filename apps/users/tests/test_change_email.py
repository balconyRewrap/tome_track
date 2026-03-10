import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from django.core.cache import cache

User = get_user_model()

@pytest.fixture
def user(db):
    return User.objects.create_user(email="user@example.com", username="user1", password="StrongPass123")

@pytest.fixture
def other_user(db):
    return User.objects.create_user(email="user2@example.com", username="user2", password="StrongPass123")

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def get_token(api_client, user):
    def _get_token(email, password):
        url = reverse("token_obtain_pair")
        response = api_client.post(url, {"email": email, "password": password}, format="json")
        return response.data["access"]
    return _get_token

def test_change_email_same_email(api_client, user, get_token):
    cache.clear()
    token = get_token(user.email, "StrongPass123")
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    url = reverse("change_email")
    response = api_client.post(url, {"new_email": user.email, "password": "StrongPass123"}, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "new_email" in response.data['error']['details']

def test_change_email_to_foreign_email(api_client, user, other_user, get_token):
    cache.clear()
    token = get_token(user.email, "StrongPass123")
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    url = reverse("change_email")
    response = api_client.post(url, {"new_email": other_user.email, "password": "StrongPass123"}, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "new_email" in response.data['error']['details']

def test_change_email_invalid_password(api_client, user, get_token):
    token = get_token(user.email, "StrongPass123")
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    url = reverse("change_email")
    response = api_client.post(url, {"new_email": "newemail@example.com", "password": "WrongPass123"}, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "password" in response.data['error']['details']



def test_change_email_token_version(api_client, user, get_token):
    # get access token
    token = get_token(user.email, "StrongPass123")
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    # change email
    url = reverse("change_email")
    response = api_client.post(url, {"new_email": "newemail@example.com", "password": "StrongPass123"}, format="json")
    assert response.status_code == status.HTTP_200_OK

    # if same token, then 401
    response = api_client.post(url, {"new_email": "another@example.com", "password": "StrongPass123"}, format="json")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # get new token with new email
    new_token = get_token("newemail@example.com", "StrongPass123")
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {new_token}")

    # Now the request works again
    response = api_client.post(url, {"new_email": "another@example.com", "password": "StrongPass123"}, format="json")
    assert response.status_code == status.HTTP_200_OK
