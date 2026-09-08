"""Persist search URLs without falling back silently after configuration errors."""
from scrapi.source_config import validate_urls

APP_ID = 'scraping_portal_urls'


def _get_model():
    from intelligence.models import AppConfig
    return AppConfig


def get_urls_portales():
    row = _get_model().objects.using('default').filter(id=APP_ID).first()
    return validate_urls(row.config) if row else {}


def save_urls_portales(urls):
    clean = validate_urls(urls)
    _get_model().objects.using('default').update_or_create(
        id=APP_ID, defaults={'name': 'URLs de extracción por portal (scraping)',
                             'level': 1, 'config': clean})
    return clean
