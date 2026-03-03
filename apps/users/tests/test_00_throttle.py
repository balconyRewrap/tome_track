# it is 00, because somehow it fails if it is after test_registration.py, even though it should not depend on it at all
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.conf import settings
from django.core.cache import cache

REGISTER_URL = reverse("register")
settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
        'anon': '60/min',
        'user': '300/min',
        'register': '10/hour',
    }


class ThrottleTests(APITestCase):
    def setUp(self):
        self.valid_data = {
            "email": "user@example.com",
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
        cache.clear()

    def test_register_throttle(self):
        """More than 10 registration attempts from the same IP within an hour should be throttled."""
        throttle_remote_addr = '127.0.0.11'
        print(settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"])
        for i in range(10):
            data = self.valid_data.copy()
            data["email"] = f"user{i}@example.com"
            data["username"] = f"user{i}"
            response = self.client.post(REGISTER_URL, data, REMOTE_ADDR=throttle_remote_addr)
            self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])
        # 11-й запрос должен быть заблокирован
        data = self.valid_data.copy()
        data["email"] = "user29@example.com"
        data["username"] = "user29"
        response = self.client.post(REGISTER_URL, data, REMOTE_ADDR=throttle_remote_addr)
        print(response)
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
