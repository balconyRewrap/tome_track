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
def admin_user(db):
    return User.objects.create_user(email="admin@example.com", username="admin", password="StrongPass123", is_staff=True, role="admin")  # pyright: ignore

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

def test_admin_functions_not_admin(api_client, user, get_token):
    cache.clear()
    token = get_token(user.email, "StrongPass123")
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    url = reverse("admin_users")
    response = api_client.get(url)
    assert response.status_code == status.HTTP_403_FORBIDDEN

    url = reverse("admin_user_detail", kwargs={"pk": user.id})
    response = api_client.get(url)
    assert response.status_code == status.HTTP_403_FORBIDDEN

def test_admin_list_users(api_client, admin_user, get_token):
    cache.clear()
    token = get_token(admin_user.email, "StrongPass123")
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    url = reverse("admin_users")
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.data['results'], list)
    assert any(u["email"] == admin_user.email for u in response.data['results'])

def test_admin_retrieve_user(api_client, admin_user, user, get_token):
    cache.clear()
    token = get_token(admin_user.email, "StrongPass123")
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    url = reverse("admin_user_detail", kwargs={"pk": user.id})
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert response.data["email"] == user.email
    assert response.data["username"] == user.username
    assert response.data["role"] == user.role
    assert response.data["page_coefficient"] == 0.0


def test_admin_patch_user_page_coefficient(api_client, admin_user, user, get_token):
    cache.clear()
    token = get_token(admin_user.email, "StrongPass123")
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    url = reverse("admin_user_detail", kwargs={"pk": user.id})
    response = api_client.patch(url, {"page_coefficient": 3.14}, format="json")
    assert response.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    assert user.page_coefficient == 3.14

def test_admin_invalid_user(api_client, admin_user, user, get_token):
    cache.clear()
    admin_token = get_token(admin_user.email, "StrongPass123")
    user_token = get_token(user.email, "StrongPass123")

    # check if user is valid and active
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {user_token}")
    auth_url = reverse('auth_check')
    response = api_client.get(auth_url)
    assert response.status_code == status.HTTP_200_OK

    # deactivate user
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {admin_token}")
    url = reverse("admin_user_detail", kwargs={"pk": user.id})
    response = api_client.patch(url, {"is_active": False}, format="json")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["is_active"] is False

    # check if user not working
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {user_token}")
    response = api_client.get(auth_url)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED