from django.urls import reverse
from rest_framework import status
from django.core.cache import cache
import pytest
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model

REGISTER_URL = reverse("register")

User = get_user_model()

@pytest.fixture
def user(db):
    return User.objects.create_user(email="user@example.com", username="user1", password="StrongPass123")

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

valid_data = {
    "email": "user@example.com",
    "username": "user1",
    "password": "StrongPass123",
    "password_confirm": "StrongPass123",
}
weak_password_data = {
    "email": "user2@example.com",
    "username": "user2",
    "password": "12345678",
    "password_confirm": "12345678",
}

@pytest.mark.throttle
def test_register_throttle(api_client, db):
    """More than 10 registration attempts from the same IP within an hour should be throttled."""
    cache.clear()
    throttle_remote_addr = '127.0.0.11'

    for i in range(10):
        data = valid_data.copy()
        data["email"] = f"user{i}@example.com"
        data["username"] = f"user{i}"
        response = api_client.post(REGISTER_URL, data, REMOTE_ADDR=throttle_remote_addr)
        print(response.data)
        assert response.status_code in [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST]
        client = cache.client.get_client()  # pyright: ignore[reportAttributeAccessIssue]
        print(list(client.keys('*')))
    # 11th request should be throttled
    data = valid_data.copy()
    data["email"] = "user29@example.com"
    data["username"] = "user29"
    response = api_client.post(REGISTER_URL, data, REMOTE_ADDR=throttle_remote_addr)
    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

@pytest.mark.throttle
def test_login_throttle(api_client, db):
    """More than 5 login attempts with wrong credentials from the same IP within a minute should be throttled."""
    throttle_remote_addr = '127.0.0.4'
    for i in range(5):
        response = api_client.post(reverse("token_obtain_pair"), {"email": "user@example.com", "password": "wrong"}, REMOTE_ADDR=throttle_remote_addr)
    # 6th request should be throttled
    response = api_client.post(reverse("token_obtain_pair"), {"email": "user@example.com", "password": "wrong"}, REMOTE_ADDR=throttle_remote_addr)
    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
