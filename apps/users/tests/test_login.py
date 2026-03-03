from django.urls import reverse
from django.conf import settings
from rest_framework import status
from rest_framework.test import APITestCase, override_settings
from rest_framework_simplejwt.tokens import RefreshToken
from apps.users.models import User

settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
        'anon': '600/min',
        'user': '3000/min',
        'register': '1000/hour',
        'login': '1000/hour',
    }

REGISTER_URL = reverse("register")
LOGIN_URL = reverse("token_obtain_pair")
REFRESH_URL = reverse("token_refresh")
LOGOUT_URL = reverse("logout")
AUTH_CHECK_URL = reverse("auth_check")

class AuthEndpointsTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="user@example.com",
            username="user1",
            password="StrongPass123"
        )
        self.login_data = {
            "email": "user@example.com",
            "password": "StrongPass123"
        }

    def test_login_success(self):
        """Успешный логин возвращает токены и user info"""
        response = self.client.post(LOGIN_URL, self.login_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["email"], self.user.email)
        self.assertEqual(response.data["role"], self.user.role)
        self.assertEqual(response.data["user_id"], self.user.id)

    def test_login_invalid(self):
        """Невалидные данные возвращают 401"""
        response = self.client.post(LOGIN_URL, {"email": "user@example.com", "password": "wrong"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        self.assertIn("No active account found with the given credentials", response.data['error']['message'])

    def test_auth_check_success(self):
        """Проверка аутентификации с access-токеном"""
        login = self.client.post(LOGIN_URL, self.login_data)
        access = login.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response = self.client.get(AUTH_CHECK_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], self.user.email)
        self.assertEqual(response.data["user_id"], self.user.id)

    def test_auth_check_unauthenticated(self):
        """Проверка аутентификации без токена"""
        response = self.client.get(AUTH_CHECK_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_success(self):
        """Успешный logout blacklists refresh token"""
        login = self.client.post(LOGIN_URL, self.login_data)
        refresh = login.data["refresh"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        response = self.client.post(LOGOUT_URL, {"refresh": refresh})
        self.assertEqual(response.status_code, status.HTTP_205_RESET_CONTENT)
        # Попытка refresh с этим токеном теперь должна вернуть 401
        response = self.client.post(REFRESH_URL, {"refresh": refresh})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_rotation(self):
        """Rotation: старый refresh становится невалидным, новый работает"""
        login = self.client.post(LOGIN_URL, self.login_data)
        old_refresh = login.data["refresh"]
        response = self.client.post(REFRESH_URL, {"refresh": old_refresh})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        new_refresh = response.data["refresh"]
        # Старый refresh теперь невалиден
        response = self.client.post(REFRESH_URL, {"refresh": old_refresh})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        # Новый refresh работает
        response = self.client.post(REFRESH_URL, {"refresh": new_refresh})
        self.assertEqual(response.status_code, status.HTTP_200_OK)