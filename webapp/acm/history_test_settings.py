"""ACM history tests without production databases or AI startup hooks."""
from django.apps import AppConfig
from .components_test_settings import *


class IdentityTestConfig(AppConfig):
    name = 'intelligence'


INSTALLED_APPS = INSTALLED_APPS + ['acm.history_test_settings.IdentityTestConfig', 'acm', 'django.contrib.humanize']
MIGRATION_MODULES = {'intelligence': None, 'acm': None}
TEMPLATES[0]['OPTIONS']['loaders'][0][1]['propifai_base.html'] = (
    '<!doctype html><html><head>{% block extra_head %}{% endblock %}</head>'
    '<body>{% block content %}{% endblock %}{% block extra_scripts %}{% endblock %}</body></html>'
)
