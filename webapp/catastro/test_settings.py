from pathlib import Path
SECRET_KEY = 'catastro-isolated-tests-only'
DEBUG = False
ALLOWED_HOSTS = ['testserver', '127.0.0.1', 'localhost']
INSTALLED_APPS = ['django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','django.contrib.staticfiles']
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3','NAME': ':memory:'}}
MIDDLEWARE = ['django.contrib.sessions.middleware.SessionMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware','django.middleware.csrf.CsrfViewMiddleware']
ROOT_URLCONF = 'catastro.test_urls'
TEMPLATES = [{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[Path(__file__).resolve().parents[1]/'templates'],'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.request','django.contrib.auth.context_processors.auth']}}]
STATIC_URL = '/static/'
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
