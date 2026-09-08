"""Validated, versioned search URLs shared by the dashboard and every adapter."""
import hashlib
import json
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ADAPTER_VERSION = '2'
DEFAULT_URLS = {
    'urbania': 'https://urbania.pe/buscar/venta-de-departamentos-en-arequipa--arequipa?page=1',
    'remax': 'https://www.remax.pe/web/search/all/propertys/list/?departament__in=4&page=1',
    'properati': 'https://www.properati.com.pe/s/arequipa',
    'adondevivir': 'https://www.adondevivir.com/inmuebles-en-venta-en-arequipa.html',
    'facebook_marketplace': 'https://www.facebook.com/marketplace/110200712339125/search/?query=Viviendas%20en%20venta&category_id=1270772586445798&exact=false&radius=65&referral_ui_component=category_menu_item&locale=es_LA',
}
DOMAINS = {
    'urbania': {'urbania.pe', 'www.urbania.pe'},
    'remax': {'remax.pe', 'www.remax.pe'},
    'properati': {'properati.com.pe', 'www.properati.com.pe'},
    'adondevivir': {'adondevivir.com', 'www.adondevivir.com'},
    'facebook_marketplace': {'facebook.com', 'www.facebook.com'},
}


def validate_url(portal, value):
    if portal not in DOMAINS:
        raise ValueError(f'Portal no admitido: {portal}')
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{portal}: la URL es obligatoria.')
    value = value.strip()
    if len(value) > 2000 or any(ord(c) < 32 for c in value) or '\\' in value:
        raise ValueError(f'{portal}: URL inválida.')
    parts = urlsplit(value)
    if (parts.scheme != 'https' or parts.hostname not in DOMAINS[portal]
            or parts.username or parts.password or parts.port not in (None, 443)):
        raise ValueError(f'{portal}: use HTTPS y el dominio del portal, sin credenciales.')
    if portal == 'facebook_marketplace' and not parts.path.startswith('/marketplace/'):
        raise ValueError('Facebook: use una URL de búsqueda de Marketplace.')
    remainder = value
    for marker in ('{n}', '{page}', '{}'):
        remainder = remainder.replace(marker, '1')
    if '{' in remainder or '}' in remainder:
        raise ValueError('Solo se admiten los marcadores {n}, {page} y {}.')
    return urlunsplit(parts._replace(fragment=''))


def page_url(portal, source_url, page):
    value = validate_url(portal, source_url)
    number = max(1, int(page))
    has_marker = any(marker in value for marker in ('{n}', '{page}', '{}'))
    if has_marker:
        for marker in ('{n}', '{page}', '{}'):
            value = value.replace(marker, str(number))
        return validate_url(portal, value)
    parts = urlsplit(value)
    if portal in ('urbania', 'remax'):
        query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != 'page']
        return urlunsplit(parts._replace(query=urlencode(query + [('page', str(number))])))
    if portal == 'properati':
        path = re.sub(r'/\d+/?$', '', parts.path.rstrip('/'))
        return urlunsplit(parts._replace(path=path if number == 1 else f'{path}/{number}'))
    if portal == 'adondevivir':
        path = re.sub(r'-pagina-\d+(?=\.html$)', '', parts.path)
        if number > 1:
            if not path.endswith('.html'):
                raise ValueError('Adondevivir: la búsqueda debe terminar en .html.')
            path = path[:-5] + f'-pagina-{number}.html'
        return urlunsplit(parts._replace(path=path))
    return value


def source_snapshot(portal, value=None):
    template = validate_url(portal, value or DEFAULT_URLS[portal])
    url = page_url(portal, template, 1)
    parts = urlsplit(url)
    query = sorted((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                   if k not in {'page', 'ref', 'referral_ui_component', 'locale'}
                   and not k.startswith('utm_'))
    canonical = urlunsplit(parts._replace(netloc=parts.hostname.removeprefix('www.'), query=urlencode(query)))
    source_key = hashlib.sha256(f'{portal}:{canonical}'.encode()).hexdigest()
    snapshot = {'portal': portal, 'source_url': template if '{' in template else url, 'source_key': source_key,
                'initial_url': url,
                'adapter_version': ADAPTER_VERSION}
    snapshot['config_version'] = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    return snapshot


def validate_urls(urls):
    if not isinstance(urls, dict):
        raise ValueError('Las URLs deben ser un objeto por portal.')
    return {portal: validate_url(portal, url) for portal, url in urls.items() if url != ''}


def requested_url(portal, params):
    return validate_url(portal, params.get('source_url') or params.get('url')
                        or params.get('search_url') or DEFAULT_URLS[portal])
