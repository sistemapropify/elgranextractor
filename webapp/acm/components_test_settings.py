"""Pruebas ACM aisladas, sin credenciales de producción ni migraciones ajenas."""
from pathlib import Path
SECRET_KEY='acm-components-tests-only'
INSTALLED_APPS=['django.contrib.auth','django.contrib.contenttypes','ingestas','cuadrantizacion']
DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':':memory:'}}
DEFAULT_AUTO_FIELD='django.db.models.BigAutoField'
USE_TZ=True
ROOT_URLCONF='acm.components_test_urls'
MIDDLEWARE=[]
ALLOWED_HOSTS=['testserver','127.0.0.1','localhost']
STATIC_URL='/static/'
TEMPLATES=[{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[Path(__file__).parent/'templates'],
    'OPTIONS':{'loaders':[('django.template.loaders.locmem.Loader',{'propifai_base.html':'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">{% block extra_head %}{% endblock %}</head><body>{% block content %}{% endblock %}{% block extra_scripts %}{% endblock %}</body></html>'}),'django.template.loaders.filesystem.Loader']}}]
