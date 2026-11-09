"""Resolve public Google Maps share links without allowing arbitrary fetches."""
from __future__ import annotations

import re
from urllib.parse import unquote, urljoin, urlsplit

import requests


ALLOWED_HOSTS = {
    'maps.app.goo.gl',
    'goo.gl',
    'google.com',
    'www.google.com',
    'maps.google.com',
    'google.com.pe',
    'www.google.com.pe',
    'maps.google.com.pe',
}
MAX_REDIRECTS = 6


class LocationLinkError(ValueError):
    pass


def _coordinate_pair(lat, lng):
    try:
        latitude, longitude = float(lat), float(lng)
    except (TypeError, ValueError):
        raise LocationLinkError('El enlace no contiene coordenadas válidas.') from None
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise LocationLinkError('El enlace no contiene coordenadas válidas.')
    return latitude, longitude


def extract_coordinates(value):
    """Read coordinates from the common Google Maps URL variants."""
    text = unquote(str(value or ''))
    patterns = (
        r'@\s*(-?\d{1,3}(?:\.\d+)?),\s*(-?\d{1,3}(?:\.\d+)?)',
        r'!3d\s*(-?\d{1,3}(?:\.\d+)?)!4d\s*(-?\d{1,3}(?:\.\d+)?)',
        r'/maps/search/\s*(-?\d{1,3}(?:\.\d+)?),\+?\s*(-?\d{1,3}(?:\.\d+)?)',
        r'(?:[?&](?:q|query)=)(-?\d{1,3}(?:\.\d+)?),\+?\s*(-?\d{1,3}(?:\.\d+)?)',
        r'(-?\d{1,3}\.\d{4,})\s*,\s*\+?(-?\d{1,3}\.\d{4,})',
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return _coordinate_pair(match.group(1), match.group(2))
    return None


def _validated_url(value):
    text = str(value or '').strip()
    if not text or len(text) > 2048 or not text.startswith('https://'):
        raise LocationLinkError('Ingresa un enlace HTTPS válido de Google Maps.')
    parsed = urlsplit(text)
    host = (parsed.hostname or '').lower()
    if parsed.scheme != 'https' or parsed.username or parsed.password:
        raise LocationLinkError('El enlace de Google Maps no es válido.')
    if parsed.port not in (None, 443) or host not in ALLOWED_HOSTS:
        raise LocationLinkError('Solo se permiten enlaces públicos de Google Maps.')
    return text


def resolve_google_maps_link(value, session=None):
    """Follow only Google-hosted redirects and return the shared location."""
    current = _validated_url(value)
    client = session or requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 Prometeo-ACM/1.0',
        'Accept': 'text/html,application/xhtml+xml',
    }
    for _ in range(MAX_REDIRECTS + 1):
        coordinates = extract_coordinates(current)
        if coordinates:
            return {'lat': coordinates[0], 'lng': coordinates[1]}
        response = client.get(
            current, headers=headers, allow_redirects=False,
            timeout=(4, 10), stream=True)
        try:
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get('Location', '')
                if not location:
                    break
                current = _validated_url(urljoin(current, location))
                continue
            if response.status_code not in (200, 204):
                break
            coordinates = extract_coordinates(current)
            if coordinates:
                return {'lat': coordinates[0], 'lng': coordinates[1]}
            break
        finally:
            response.close()
    raise LocationLinkError(
        'No se pudieron obtener las coordenadas del enlace de Google Maps.')
