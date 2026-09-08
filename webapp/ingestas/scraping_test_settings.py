"""Isolated tests: never import production settings or initialize workers."""
SECRET_KEY = 'scraping-tests-only'
CELERY_BROKER_URL = 'memory://'
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parents[1]
INSTALLED_APPS = ['django.contrib.auth', 'django.contrib.contenttypes', 'ingestas']
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
import os
if os.environ.get('SCRAPING_TEST_SQL') == '1':
    DATABASES = {'default': {'ENGINE': 'mssql', 'NAME': 'master', 'HOST': 'scraping-sql',
        'USER': 'sa', 'PASSWORD': os.environ['SCRAPING_DB_PASSWORD'], 'PORT': '1433',
        'OPTIONS': {'driver': 'ODBC Driver 18 for SQL Server',
            'extra_params': 'Encrypt=yes;TrustServerCertificate=yes'},
        'TEST': {'NAME': 'test_scraping_integrity'}}}
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
USE_TZ = True
TIME_ZONE = 'America/Lima'
DATABASE_ROUTERS = []
ROOT_URLCONF = 'ingestas.scraping_test_urls'
MIDDLEWARE = ['django.middleware.csrf.CsrfViewMiddleware']
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates',
              'APP_DIRS': True, 'DIRS': [BASE_DIR / 'templates']}]
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
