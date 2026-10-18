"""Isolated tests; never use these settings to serve the application."""

import os
from .settings import *
from .settings import MIDDLEWARE as BASE_MIDDLEWARE

SECRET_KEY = "test-only-not-for-serving-requests"
DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
EMAIL_HOST = "test"
DEFAULT_FROM_EMAIL = "test@example.com"
if os.environ.get("TEST_POSTGRES") != "1":
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}

# Legacy tests use original hard-coded paths. API tests override this with config.urls.
ROOT_URLCONF = "config.legacy_test_urls"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# Static files are verified separately against the collected production build.
MIDDLEWARE = [
    item for item in BASE_MIDDLEWARE if item != "whitenoise.middleware.WhiteNoiseMiddleware"
]
