from django.urls import reverse
from django.core.cache import cache
from rest_framework import status
from apps.users.models import User
import pytest
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model

User = get_user_model()

@pytest.fixture(scope="function")
def user(db):
    return User.objects.create_user(email="user@example.com", username="user1", password="StrongPass123", role="user")  # pyright: ignore

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

REGISTER_URL = reverse("register")
LOGIN_URL = reverse("token_obtain_pair")
REFRESH_URL = reverse("token_refresh")
LOGOUT_URL = reverse("logout")
AUTH_CHECK_URL = reverse("auth_check")

test_user = {
    "email": "user@example.com",
    "username": "user1",
    "password": "StrongPass123",
    "role": "user",
}
login_data = {
    "email": "user@example.com",
    "password": "StrongPass123"
}

def test_login_success(api_client, user, db):
    """Successful login returns 200, access in body, refresh in cookie."""
    cache.clear()
    response = api_client.post(LOGIN_URL, login_data)
    assert response.status_code == status.HTTP_200_OK
    assert "access" in response.data
    assert "refresh" not in response.data
    assert "refresh_token" in response.cookies
    assert response.data["email"] == test_user["email"]
    assert response.data["role"] == test_user["role"]

def test_login_invalid(api_client, user, db):
    """Invalid credentials return 401"""
    response = api_client.post(LOGIN_URL, {"email": "user@example.com", "password": "wrong"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "No active account found with the given credentials" in response.data['error']['message']

def test_auth_check_success(api_client, user, db):
    """Authentication check with access token"""
    cache.clear()
    login = api_client.post(LOGIN_URL, login_data)
    access = login.data["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    response = api_client.get(AUTH_CHECK_URL)
    assert response.status_code == status.HTTP_200_OK
    assert response.data["email"] == test_user["email"]

def test_auth_check_unauthenticated(api_client, user, db):
    """Authentication check without token"""
    response = api_client.get(AUTH_CHECK_URL)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

def test_logout_success(api_client, user, db):
    """Successful logout blacklists refresh token cookie"""
    login = api_client.post(LOGIN_URL, login_data)
    api_client.cookies = login.cookies
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    response = api_client.post(LOGOUT_URL)
    assert response.status_code == status.HTTP_205_RESET_CONTENT
    # after logout cookie is cleared, refresh attempt should fail
    response = api_client.post(REFRESH_URL)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

def test_refresh_rotation(api_client, user, db):
    """Rotation: old refresh cookie becomes invalid, new one works"""
    login = api_client.post(LOGIN_URL, login_data)
    # Save the raw token value as a string BEFORE any request updates the cookie jar in-place
    old_refresh_value = login.cookies['refresh_token'].value
    api_client.cookies = login.cookies

    response = api_client.post(REFRESH_URL)
    assert response.status_code == status.HTTP_200_OK
    assert "access" in response.data
    assert "refresh" not in response.data
    assert "refresh_token" in response.cookies

    # old refresh token should be blacklisted
    old_client = APIClient()
    old_client.cookies['refresh_token'] = old_refresh_value
    response_old = old_client.post(REFRESH_URL)
    assert response_old.status_code == status.HTTP_401_UNAUTHORIZED

    # new refresh cookie (updated in-place by the test client) should work
    response_new = api_client.post(REFRESH_URL)
    assert response_new.status_code == status.HTTP_200_OK
    access_token = response_new.data['access']
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
    response = api_client.get(AUTH_CHECK_URL)
    assert response.status_code == status.HTTP_200_OK


def test_login_inactive_user(api_client, user, db):
    user.is_active = False
    user.save()
    response = api_client.post(LOGIN_URL, login_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED