"""Isolated settings for the external real estate agents module tests."""

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

SECRET_KEY = 'external-agents-tests-only'
DEBUG = False
ALLOWED_HOSTS = ['testserver', '127.0.0.1', 'localhost']

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'prospects',
    'external_agents',
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    },
}

MIDDLEWARE = [
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]

ROOT_URLCONF = 'external_agents.test_urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'external_agents' / 'test_templates',
            BASE_DIR / 'templates',
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

STATIC_URL = '/static/'
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

# The application imports this storage backend while defining models. These
# dummy settings avoid production credentials; uploads are mocked by the tests.
AZURE_CONTAINER = 'external-agents-tests'
AZURE_EXTERNAL_AGENTS_CONTAINER = 'external-agents-tests'
AZURE_ACCOUNT_NAME = 'externalagentstests'
AZURE_ACCOUNT_KEY = ''
AZURE_CONNECTION_STRING = ''
AZURE_STORAGE_CONNECTION_STRING = ''


class DisableMigrations(dict):
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


MIGRATION_MODULES = DisableMigrations()
TEST_RUNNER = 'external_agents.test_runner.ExternalAgentsTestRunner'
