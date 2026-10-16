from .history_test_settings import *
INSTALLED_APPS = INSTALLED_APPS + ['django.contrib.sessions', 'django.contrib.staticfiles']
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'
MIDDLEWARE = ['acm.session_middleware.ACMSessionMiddleware', 'django.middleware.csrf.CsrfViewMiddleware']
ROOT_URLCONF = 'acm.access_test_urls'
PROPIFY_AUTH_TOKEN_URL = 'https://api.propify.pe/api/auth/token/'
PROPIFY_AUTH_ME_URL = 'https://api.propify.pe/api/auth/me/'
TEMPLATES[0]['OPTIONS']['context_processors'] = ['django.template.context_processors.request']
TEMPLATES[0]['OPTIONS']['loaders'] = ['django.template.loaders.filesystem.Loader', 'django.template.loaders.app_directories.Loader']
