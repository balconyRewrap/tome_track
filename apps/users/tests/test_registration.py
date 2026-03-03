from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, override_settings
from django.conf import settings

# settings.REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = []
settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
        'anon': '600/min',
        'user': '3000/min',
        'register': '1000/hour',
    }
REGISTER_URL = reverse("register")  # Убедитесь, что в urls.py name="register"

class RegisterTests(APITestCase):
    def setUp(self):
        self.valid_data = {
            "email": "user@example.com",
            "username": "user1",
            "password": "StrongPass123",
            "password_confirm": "StrongPass123",
        }
        self.duplicate_email_data = {
            "email": "user@example.com",
            "username": "user2",
            "password": "StrongPass123",
            "password_confirm": "StrongPass123",
        }
        self.duplicate_username_data = {
            "email": "user23@example.com",
            "username": "user1",
            "password": "StrongPass123",
            "password_confirm": "StrongPass123",
        }
        self.weak_password_data = {
            "email": "user2@example.com",
            "username": "user2",
            "password": "12345678",
            "password_confirm": "12345678",
        }

    def test_register_success(self):
        """POST with valid data returns 201 and expected fields"""
        response = self.client.post(REGISTER_URL, self.valid_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)  # pyright: ignore[reportAttributeAccessIssue]
        self.assertEqual(response.data["email"], self.valid_data["email"])  # pyright: ignore[reportAttributeAccessIssue]
        self.assertEqual(response.data["username"], self.valid_data["username"])  # pyright: ignore[reportAttributeAccessIssue]

    def test_register_duplicate_email(self):
        """POST with duplicate email returns 400 and error message"""
        self.client.post(REGISTER_URL, self.duplicate_email_data)
        response = self.client.post(REGISTER_URL, self.duplicate_email_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("User with this email already exists", response.data['error']['details']['email'][0])  # pyright: ignore[reportAttributeAccessIssue]

    def test_register_duplicate_username(self):
        """POST with duplicate username returns 400 and error message"""
        self.client.post(REGISTER_URL, self.duplicate_username_data)
        response = self.client.post(REGISTER_URL, self.duplicate_username_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("User with this username already exists", response.data['error']['details']['username'][0])  # pyright: ignore[reportAttributeAccessIssue]

    def test_register_weak_password(self):
        """POST with weak password returns 400 and error message"""
        response = self.client.post(REGISTER_URL, self.weak_password_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data['error']['details'])  # pyright: ignore[reportAttributeAccessIssue]
        self.assertTrue(
            "too weak" in str(response.data['error']['details']["password"]).lower() or   # pyright: ignore[reportAttributeAccessIssue]
            "only" in str(response.data['error']['details']["password"]).lower() or   # pyright: ignore[reportAttributeAccessIssue]
            "too common" in str(response.data['error']['details']["password"]).lower()  # pyright: ignore[reportAttributeAccessIssue]
        )

