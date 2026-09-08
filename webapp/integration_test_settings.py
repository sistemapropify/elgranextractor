"""Integration tests with isolated databases and no production startup hooks."""
import os
from pathlib import Path

from django.apps import AppConfig

from ingestas.scraping_test_settings import *

class IdentityTestConfig(AppConfig):
    name = 'intelligence'

class BridgeTestConfig(AppConfig):
    name = 'n8n_bridge'

BASE_DIR = Path(__file__).resolve().parent
SECRET_KEY = 'isolated-project-integration-tests'
INSTALLED_APPS = [
    'django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions',
    'django.contrib.messages', 'django.contrib.staticfiles', 'rest_framework',
    'integration_test_settings.IdentityTestConfig', 'ingestas', 'lead_intelligence',
    'prospects', 'integration_test_settings.BridgeTestConfig', 'response_intelligence', 'analisis_crm',
]
# Existing identity migrations require the production auth schema. Create test
# identity fixtures directly; keep all migrations for the integrated modules.
MIGRATION_MODULES = {'intelligence': None}
DATABASES['propifai'] = {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}
DATABASE_ROUTERS = []
ROOT_URLCONF = 'integration_test_urls'
ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']
MIDDLEWARE = [
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
]
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'], 'APP_DIRS': True,
    'OPTIONS': {'context_processors': ['django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages']}}]
STATIC_URL = '/static/'
MEDIA_URL = '/media/'
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
DEFAULT_FROM_EMAIL = 'tests@example.invalid'
DURABLE_EXECUTION_MODE = 'external'
CELERY_TASK_ALWAYS_EAGER = True
CELERY_BROKER_URL = 'memory://'
CELERY_RESULT_BACKEND = 'cache+memory://'
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
TEST_RUNNER = 'integration_test_runner.OfflineIntegrationRunner'
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
