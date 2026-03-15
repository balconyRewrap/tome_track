"""Settings for production."""
from .base import *  # noqa: F403

SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', default=(not DEBUG))
SECURE_HSTS_SECONDS = env.int('SECURE_HSTS_SECONDS', default=(31536000 if not DEBUG else 0))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=True)
SECURE_HSTS_PRELOAD = env.bool('SECURE_HSTS_PRELOAD', default=True)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True  # JavaScript couldn't read cookie
CSRF_COOKIE_SECURE = True

#DEBUG = False
