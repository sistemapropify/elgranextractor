"""Dedicated SQL queue worker; no web startup hooks, AI models or embedded credentials."""
import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parents[1]

def required(name):
    value = os.environ.get(name)
    if not value:
        raise ImproperlyConfigured(f'Worker configuration missing: {name}')
    return value

SECRET_KEY = required('DJANGO_SECRET_KEY')
INSTALLED_APPS = ['django.contrib.auth', 'django.contrib.contenttypes', 'ingestas']
DATABASES = {'default': {
    'ENGINE': 'mssql', 'NAME': required('SCRAPING_DB_NAME'),
    'HOST': required('SCRAPING_DB_HOST'), 'USER': required('SCRAPING_DB_USER'),
    'PASSWORD': required('SCRAPING_DB_PASSWORD'), 'PORT': '1433',
    'OPTIONS': {'driver': 'ODBC Driver 18 for SQL Server',
                'extra_params': 'Encrypt=yes;TrustServerCertificate=no',
                'connection_timeout': 15, 'query_timeout': 60},
    'CONN_MAX_AGE': 60,
}}
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
USE_TZ = True
TIME_ZONE = 'America/Lima'
DATABASE_ROUTERS = []
SCRAPING_EXECUTION_MODE = 'external'
CELERY_BROKER_URL = 'memory://'
for key in ('AZURE_STORAGE_CONNECTION_STRING', 'AZURE_STORAGE_ACCOUNT_NAME',
            'AZURE_STORAGE_ACCOUNT_KEY', 'AZURE_STORAGE_CONTAINER_NAME'):
    globals()[key] = os.environ.get(key, '')
LOGGING = {'version': 1, 'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'root': {'handlers': ['console'], 'level': 'INFO'}}
