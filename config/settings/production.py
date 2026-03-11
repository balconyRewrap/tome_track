"""Settings for production."""
from .base import *  # noqa: F403

SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = True


SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True  # JavaScript couldn't read cookie
CSRF_COOKIE_SECURE = True

DEBUG = False
