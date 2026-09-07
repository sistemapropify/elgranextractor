from .remarketing_test_settings import *
from django.apps import AppConfig


class ControlIdentityTestConfig(AppConfig):
    name = 'intelligence'
    # Load real identity models without starting embedding/LLM services.


INSTALLED_APPS = ['django.contrib.auth', 'django.contrib.contenttypes', 'lead_intelligence.control_test_settings.ControlIdentityTestConfig', 'lead_intelligence', 'prospects', 'rest_framework']
# Identity tables are fixtures; migrations under test remain enabled for control
# and prospects, including the existing mobile device schema.
MIGRATION_MODULES = {'intelligence': None}
ROOT_URLCONF = 'lead_intelligence.control_test_urls'
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
DEFAULT_FROM_EMAIL = 'control@example.invalid'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'OPTIONS': {'loaders': [('django.template.loaders.locmem.Loader', {'base.html': '{% block content %}{% endblock %}'}), 'django.template.loaders.app_directories.Loader']}}]
