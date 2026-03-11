from django.urls import reverse
from rest_framework import status
import pytest
from django.contrib.auth import get_user_model

# settings.REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = []
REGISTER_URL = reverse("register")
User = get_user_model()


@pytest.mark.django_db
class TestRegister:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.valid_data = {
            "email": "user@example.com",
            "username": "user1",
            "password": "StrongPass123",
        }
        self.duplicate_email_data = {
            "email": "user@example.com",
            "username": "user2",
            "password": "StrongPass123",
        }
        self.duplicate_username_data = {
            "email": "user23@example.com",
            "username": "user1",
            "password": "StrongPass123",
        }
        self.weak_password_data = {
            "email": "user2@example.com",
            "username": "user2",
            "password": "12345678",
        }

    def test_register_success(self, client):
        """POST with valid data returns 201 and expected fields"""
        response = client.post(REGISTER_URL, self.valid_data)
        assert response.status_code == status.HTTP_201_CREATED
        assert "id" in response.data
        assert response.data["email"] == self.valid_data["email"]
        assert response.data["username"] == self.valid_data["username"]

    def test_register_duplicate_email(self, client):
        """POST with duplicate email returns 400 and error message"""
        client.post(REGISTER_URL, self.duplicate_email_data)
        response = client.post(REGISTER_URL, self.duplicate_email_data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "User with this email already exists" in response.data['error']['details']['email'][0]

    def test_register_duplicate_username(self, client):
        """POST with duplicate username returns 400 and error message"""
        client.post(REGISTER_URL, self.duplicate_username_data)
        response = client.post(REGISTER_URL, self.duplicate_username_data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "User with this username already exists" in response.data['error']['details']['username'][0]

    def test_register_weak_password(self, client):
        """POST with weak password returns 400 and error message"""
        response = client.post(REGISTER_URL, self.weak_password_data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "password" in response.data['error']['details']
        assert any(keyword in str(response.data['error']['details']["password"]).lower() 
                   for keyword in ["too weak", "only", "too common"])
