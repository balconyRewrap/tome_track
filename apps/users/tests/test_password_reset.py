import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from apps.users.models import PasswordResetToken
from datetime import timedelta
from django.conf import settings
from django.core.cache import cache

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

def test_reset_password_different_email(api_client, user, get_token):
    token = get_token(user.email, "StrongPass123")
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    url = reverse("password_reset")
    response = api_client.post(url, {"email": "different@example.com"}, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "You can't reset" in response.data['error']['details']['email'][0]

def test_reset_password_no_credentials(api_client, user, get_token):
    url = reverse("password_reset")
    response = api_client.post(url, {"email": user.email}, format="json")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

def test_reset_password_success(api_client, user, get_token):
    cache.clear()
    token = get_token(user.email, "StrongPass123")
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    url = reverse("password_reset")
    response = api_client.post(url, {"email": user.email}, format="json")
    assert response.status_code == status.HTTP_200_OK
    assert "reset_token" in response.data
    reset_token = response.data["reset_token"]
    assert len(reset_token) > 0
    assert isinstance(reset_token, str)


    url = reverse("password_reset_confirm")
    # bad password returns 400 with error message
    response = api_client.post(url, {"token": reset_token, "new_password": "123"}, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "new_password" in response.data['error']['details']
    # successful password reset returns 200 with detail message
    response = api_client.post(url, {"token": reset_token, "new_password": "NewStrongPass123"}, format="json")
    assert response.status_code == status.HTTP_200_OK
    assert "detail" in response.data
    assert response.data["detail"] == "Password has been reset successfully."

    # old token no longer works
    response = api_client.post(url, {"token": reset_token, "new_password": "NewStrongPass123"}, format="json")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Token is no longer valid" in response.data['error']['message']
    # old password no longer works
    response = api_client.post(reverse("token_obtain_pair"), {"email": user.email, "password": "StrongPass123"}, format="json")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    # new password works
    response = api_client.post(reverse("token_obtain_pair"), {"email": user.email, "password": "NewStrongPass123"}, format="json")
    assert response.status_code == status.HTTP_200_OK

def test_reset_password_expired_token(api_client, user, get_token):
    token = get_token(user.email, "StrongPass123")
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    url = reverse("password_reset")
    response = api_client.post(url, {"email": user.email}, format="json")
    assert response.status_code == status.HTTP_200_OK
    reset_token = response.data["reset_token"]

    # Simulate token expiration by directly deleting the token from the database
    reset_token_model = PasswordResetToken.objects.filter(token=reset_token).first()
    reset_token_model.created_at = reset_token_model.created_at - timedelta(hours=2)  # Set created_at to 2 hours ago   # pyright: ignore
    reset_token_model.save()  # pyright: ignore

    url = reverse("password_reset_confirm")
    response = api_client.post(url, {"token": reset_token, "new_password": "NewStrongPass123"}, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    print(response.data)
    assert "Invalid or expired token." in response.data['error']['details']['token']
