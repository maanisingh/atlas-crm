"""
Test settings that use SQLite database for testing
"""
from .settings import *

# Override database settings for testing
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',  # Use in-memory database for faster tests
    }
}

# Disable some middleware that might slow down tests
MIDDLEWARE = [item for item in MIDDLEWARE if 'axes' not in item.lower()]

# Remove Axes authentication backend for testing
AUTHENTICATION_BACKENDS = [
    backend for backend in AUTHENTICATION_BACKENDS
    if 'axes' not in backend.lower()
]

# Completely disable Axes for testing
AXES_ENABLED = False

# Remove axes from installed apps
INSTALLED_APPS = [app for app in INSTALLED_APPS if 'axes' not in app.lower()]

# Speed up password hashing in tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Disable migrations for faster test database setup
class DisableMigrations:
    def __contains__(self, item):
        return True
    def __getitem__(self, item):
        return None

# Comment this out if you need to test migrations
# MIGRATION_MODULES = DisableMigrations()
