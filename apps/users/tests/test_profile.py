import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model

User = get_user_model()

@pytest.fixture
def user(db):
    return User.objects.create_user(email="user@example.com", username="user1", password="StrongPass123")

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def auth_client(user, api_client):
    api_client.force_authenticate(user=user)
    return api_client

def test_get_profile(auth_client, user):
    url = reverse("user_me")
    response = auth_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert response.data["email"] == user.email
    assert response.data["username"] == user.username
    assert response.data["role"] == user.role

def test_patch_profile_username_success(auth_client, user):
    url = reverse("user_me")
    response = auth_client.patch(url, {"username": "newname"}, format="json")
    assert response.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    assert user.username == "newname"

def test_patch_profile_username_same(auth_client, user):
    url = reverse("user_me")
    response = auth_client.patch(url, {"username": user.username}, format="json")
    assert response.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    assert user.username == "user1"

def test_patch_profile_username_taken(auth_client, user, db):
    other = User.objects.create_user(email="other@example.com", username="taken", password="StrongPass123")
    url = reverse("user_me")
    response = auth_client.patch(url, {"username": "taken"}, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "username" in response.data['error']['details']

def test_patch_profile_unauthenticated(api_client):
    url = reverse("user_me")
    response = api_client.patch(url, {"username": "any"}, format="json")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

def test_get_profile_unauthenticated(api_client):
    url = reverse("user_me")
    response = api_client.get(url)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
