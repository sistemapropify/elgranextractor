"""Shared Maps browser configuration; reuse the application's existing key."""
from django.conf import settings


def google_maps_api_key():
    return getattr(settings,'GOOGLE_MAPS_API_KEY',None) or 'AIzaSyBrL1QF7vTl9zF8FmCUumfRpFJcaYokO7Q'
