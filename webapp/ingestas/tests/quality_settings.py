"""Entorno aislado de calidad: sin credenciales, Azure ni apps ajenas."""
from pathlib import Path
SECRET_KEY = 'local-quality-test-only'
INSTALLED_APPS = ['django.contrib.auth', 'django.contrib.contenttypes', 'ingestas', 'cuadrantizacion']
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
USE_TZ = True
ROOT_URLCONF = 'ingestas.tests.quality_urls'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates',
              'DIRS': [Path(__file__).resolve().parents[2] / 'templates'], 'APP_DIRS': True}]
MIDDLEWARE = []
