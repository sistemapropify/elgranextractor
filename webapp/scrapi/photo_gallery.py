"""Ordered property photos and durable, content-addressed copies in Blob Storage."""
import asyncio
import hashlib
import io
import ipaddress
import json
import re
import socket
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

PHOTO_MODES = ('none', 'cover', 'all')
GALLERY_KEY = '_photo_gallery'
MAX_IMAGE_BYTES = 20 * 1024 * 1024


def photo_mode(value='cover'):
    if value not in PHOTO_MODES:
        raise ValueError('Modo de fotos inválido: ninguna, portada o todas.')
    return value


def image_url(value, base=''):
    if not isinstance(value, str) or not value.strip():
        return None
    url = urljoin(base, value.strip())
    parsed = urlsplit(url)
    if parsed.scheme not in ('https', 'http') or not parsed.hostname or parsed.username or parsed.password:
        return None
    return url


def extract_photos(html, base, cover=None):
    """Read the listing's gallery and embedded photo arrays, excluding related cards."""
    photos = []
    def add(value):
        url = image_url(value, base)
        if url and url not in photos:
            photos.append(url)
    add(cover)
    soup = BeautifulSoup(html or '', 'html.parser')
    def related(node):
        return any(re.search(r'related|similar|recommend|sugerid|snippet|posting-card|agent',
                             ' '.join(parent.get('class', [])), re.I)
                   for parent in [node, *node.parents] if getattr(parent, 'attrs', None))
    for node in soup.select('[class*="gallery"], [class*="galeria"], [class*="carousel"], '
                            '[class*="carrousel"], [class*="swiper"], [class*="photo"], '
                            '[class*="foto"], .flexslider, '
                            '[data-testid*="gallery"], [data-qa*="photo"]'):
        if related(node):
            continue
        for img in node.select('img'):
            if not related(img):
                add(img.get('data-original') or img.get('data-full') or img.get('data-src') or img.get('src'))
        for anchor in node.select('a[href]'):
            if re.search(r'\.(?:jpe?g|png|webp|gif)(?:\?|$)', anchor['href'], re.I):
                add(anchor['href'])
    for meta in soup.select('meta[property="og:image"]'):
        add(meta.get('content'))

    photo_keys = {'photos', 'images', 'pictures', 'gallery', 'imageurls', 'imagenes', 'image'}
    def walk(value, in_photos=False):
        if isinstance(value, str):
            if in_photos:
                add(value)
        elif isinstance(value, list):
            for item in value:
                walk(item, in_photos)
        elif isinstance(value, dict):
            if value.get('@type') in ('Person', 'Organization', 'RealEstateAgent'):
                return
            if in_photos:
                best = next((value[key] for key in ('original', 'originalUrl', 'url', 'src', 'contentUrl')
                             if isinstance(value.get(key), str)), None)
                if best:
                    add(best)
                    return
            for key, item in value.items():
                lower = key.lower()
                if re.search(r'related|similar|recommend|suggest|logo|avatar|agent', lower):
                    continue
                walk(item, in_photos or lower in photo_keys)
    for script in soup.select('script'):
        body = script.string or script.get_text()
        assignment = re.match(r'\s*(?:window\.)?(?:__\w+__|initialState)\s*=\s*', body)
        if script.get('type') not in ('application/json', 'application/ld+json') and not assignment:
            continue
        try:
            walk(json.JSONDecoder().raw_decode(body[assignment.end():] if assignment else body.lstrip())[0])
        except (ValueError, TypeError):
            pass
    return photos


def _public_url(url):
    parsed = urlsplit(image_url(url) or '')
    if not parsed.hostname or parsed.port not in (None, 80, 443):
        raise ValueError('URL de imagen no admitida')
    addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ValueError('La imagen debe estar en un servidor público')
    return url


def upload_photo(url, portal, property_id, referer=''):
    """Bounded downloads; identical image bytes reuse the same blob name."""
    import requests
    from PIL import Image
    from captura.azure_storage import upload_bytes
    headers = {'User-Agent': 'Mozilla/5.0'}
    if image_url(referer):
        headers['Referer'] = referer
    with requests.Session() as session:
        session.trust_env = False
        for _ in range(6):
            _public_url(url)
            with session.get(url, headers=headers, stream=True, timeout=(5, 15), allow_redirects=False) as response:
                if response.is_redirect:
                    url = urljoin(url, response.headers['Location'])
                    continue
                response.raise_for_status()
                content = bytearray()
                for chunk in response.iter_content(65536):
                    content.extend(chunk)
                    if len(content) > MAX_IMAGE_BYTES:
                        raise ValueError('La imagen supera 20 MB')
                with Image.open(io.BytesIO(content)) as image:
                    fmt = image.format
                    image.verify()
                extensions = {'JPEG': ('jpg', 'image/jpeg'), 'PNG': ('png', 'image/png'),
                              'WEBP': ('webp', 'image/webp'), 'GIF': ('gif', 'image/gif')}
                if fmt not in extensions:
                    raise ValueError('Formato de imagen no admitido')
                extension, mime = extensions[fmt]
                # Hash both identities to avoid collisions between portals or truncated IDs.
                identity = hashlib.sha256(f'{portal}:{property_id}'.encode()).hexdigest()[:24]
                digest = hashlib.sha256(content).hexdigest()
                return upload_bytes(bytes(content),
                    blob_name=f'propiedades/{portal}/{identity}/{digest}.{extension}',
                    container_name='propiedadesimagenes', content_type=mime,
                    metadata={'fuente': portal, 'propiedad': identity, 'sha256': digest})
    raise ValueError('Demasiadas redirecciones de imagen')


async def store_photos(row, urls, portal, emit, *, mode='all', uploader=None):
    mode = photo_mode(mode)
    unique = list(dict.fromkeys(url for value in urls if (url := image_url(value))))
    selected = unique[:1] if mode == 'cover' else unique if mode == 'all' else []
    gallery = []
    for position, url in enumerate(selected):
        await emit(event='image.started', property_id=row['id_origen'], image_position=position,
                   message=f'{portal}: guardando foto {position + 1} de {len(selected)}')
        blob = None
        error_type = None
        try:
            blob = await asyncio.wait_for(asyncio.to_thread(uploader or upload_photo,
                url, portal, row['id_origen'], row.get('url') or ''), timeout=60)
        except Exception as exc:
            error_type = type(exc).__name__
        gallery.append({'url': blob or url, 'source_url': url, 'stored': bool(blob)})
        if blob:
            await emit(event='image.saved', property_id=row['id_origen'], image_position=position,
                       message=f'{portal}: foto {position + 1} almacenada en Azure')
        else:
            # Do not log signed source URLs or credentials embedded in an SDK error.
            await emit(event='image.failed', level='warning', property_id=row['id_origen'],
                       image_position=position, error_type=error_type or 'UploadFailed',
                       message=f'{portal}: foto {position + 1} pendiente; se conserva el enlace original')
    row.setdefault('datos_crudos', {})[GALLERY_KEY] = gallery
    row['datos_crudos']['_photo_mode'] = mode
    stored = next((photo['url'] for photo in gallery if photo['stored']), None)
    if stored:
        row['imagen_url'] = stored
    return row


def gallery_photos(raw=None, cover=None):
    raw = raw if isinstance(raw, dict) else {}
    rows = list(raw.get(GALLERY_KEY) or [])
    rows += [{'url': url, 'stored': True} for url in raw.get('blob_photos') or []]
    if not rows:
        rows += [{'url': url, 'stored': False} for url in raw.get('photos') or []]
    if cover:
        rows.append({'url': cover, 'stored': '.blob.core.windows.net/' in cover})
    photos = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        url = image_url(row.get('url'))
        source = image_url(row.get('source_url'))
        if not url or url in seen or (source and source in seen):
            continue
        photos.append({**row, 'url': url})
        seen.add(url)
        if source:
            seen.add(source)
    return photos


def preserve_gallery(new_raw, old_raw, old_cover=None):
    """Keep archived photos even when a later run has only a cover or a failed download."""
    raw = dict(new_raw or {})
    old = [photo for photo in gallery_photos(old_raw, old_cover) if photo.get('stored')]
    current = gallery_photos(raw)
    stored_sources = {photo.get('source_url') for photo in old if photo.get('source_url')}
    current = [photo for photo in current if photo.get('stored') or
               (photo.get('source_url') or photo['url']) not in stored_sources]
    combined = gallery_photos({GALLERY_KEY: current + old})
    if combined:
        raw[GALLERY_KEY] = combined
    return raw
