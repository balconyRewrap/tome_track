"""Settings for testing."""
from .base import *  # noqa: F403

# here DEBUG is true Override .env
DEBUG = True
ALLOWED_HOSTS = ['*']

# Print emails to console instead of sending them
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

LOGGING['loggers']['apps']['level'] = 'DEBUG'  # noqa: F405
