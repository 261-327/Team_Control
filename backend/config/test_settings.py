"""Isolated tests; never use these settings to serve the application."""
import os
from .settings import *

SECRET_KEY = 'test-only-not-for-serving-requests'
DEBUG = False
ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
EMAIL_HOST = 'test'
DEFAULT_FROM_EMAIL = 'test@example.com'
if os.environ.get('TEST_POSTGRES') != '1':
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
