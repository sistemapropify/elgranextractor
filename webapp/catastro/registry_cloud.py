"""Private relational index in R2; SQLite and all working data stay in RAM."""
from concurrent.futures import ThreadPoolExecutor
import datetime
import gzip
import hashlib
import hmac
import io
import json
import re
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request
import xml.etree.ElementTree as ET

from . import registry
from .storage import R2, StorageError, PreconditionFailed

_cache = {}
_lock = threading.RLock()
MAX_DATABASE = 128 * 1024 * 1024
PREFIX = 'geollaqta/indices/registro-tabular-v1/'


def validate_district(value):
    from scrapi.geollaqta_scraper import DISTRICTS
    if value not in DISTRICTS:
        raise ValueError('Selecciona un distrito del catálogo catastral.')
    return value


def list_lots(ubigeo, after='', limit=20):
    validate_district(ubigeo)
    if after and not re.fullmatch(ubigeo+r'\d{8,12}', after):
        raise ValueError('Posición de importación no válida.')
    cloud = R2(timeout=12)
    prefix = 'geollaqta/'+ubigeo+'/'
    params = {'list-type': '2', 'prefix': prefix, 'delimiter': '/', 'max-keys': str(limit)}
    if after:
        params['start-after'] = prefix+after+'/'
    query = '&'.join(quote(k, safe='')+'='+quote(v, safe='') for k,v in sorted(params.items()))
    now = datetime.datetime.now(datetime.timezone.utc)
    stamp, day = now.strftime('%Y%m%dT%H%M%SZ'), now.strftime('%Y%m%d')
    uri = '/'+quote(cloud.bucket, safe='')
    digest = hashlib.sha256(b'').hexdigest()
    headers = {'host': cloud.host, 'x-amz-date': stamp, 'x-amz-content-sha256': digest}
    signed = ';'.join(sorted(headers))
    canonical = '\n'.join(['GET', uri, query, ''.join(k+':'+headers[k]+'\n' for k in sorted(headers)), signed, digest])
    scope = day+'/auto/s3/aws4_request'
    to_sign = '\n'.join(['AWS4-HMAC-SHA256',stamp,scope,hashlib.sha256(canonical.encode()).hexdigest()])
    secret = ('AWS4'+cloud.values['R2_SECRET_ACCESS_KEY']).encode()
    for part in (day,'auto','s3','aws4_request'):
        secret = hmac.new(secret,part.encode(),hashlib.sha256).digest()
    signature = hmac.new(secret,to_sign.encode(),hashlib.sha256).hexdigest()
    headers['Authorization'] = 'AWS4-HMAC-SHA256 Credential='+cloud.values['R2_ACCESS_KEY_ID']+'/'+scope+', SignedHeaders='+signed+', Signature='+signature
    try:
        with cloud.opener.open(Request('https://'+cloud.host+uri+'?'+query, headers=headers), timeout=12) as response:
            body = response.read(2_000_000)
        root = ET.fromstring(body)
    except HTTPError as error:
        raise StorageError('No se pudo listar el archivo R2 (HTTP '+str(error.code)+').') from None
    except (URLError, OSError, ET.ParseError):
        raise StorageError('No se pudo consultar el inventario de R2.') from None
    ns = '{http://s3.amazonaws.com/doc/2006-03-01/}'
    lots = [n.text[len(prefix):].rstrip('/') for n in root.findall(ns+'CommonPrefixes/'+ns+'Prefix') if n.text]
    lots = sorted(lot for lot in lots if re.fullmatch(ubigeo+r'\d{8,12}', lot))
    truncated = root.findtext(ns+'IsTruncated') == 'true'
    if truncated and not lots:
        raise StorageError('El inventario no devolvió una posición válida para continuar.')
    return lots, lots[-1] if truncated else None


def read_manifest(ubigeo, lot_id):
    if not re.fullmatch(ubigeo+r'\d{8,12}', lot_id):
        raise ValueError('Lote no válido.')
    body, _ = R2(timeout=10).get('geollaqta/'+ubigeo+'/'+lot_id+'/datos.json')
    manifest = json.loads(body)
    if manifest.get('lot_id') != lot_id or manifest.get('district_ubigeo') != ubigeo:
        raise ValueError('El documento no coincide con el lote solicitado.')
    return manifest, hashlib.sha256(body).hexdigest()


def load(ubigeo, fresh=False):
    validate_district(ubigeo)
    with _lock:
        saved = _cache.get(ubigeo)
        if not fresh and saved and saved[0] > time.monotonic()-20:
            return registry.connect(saved[1]), saved[2]
    try:
        compressed, headers = R2(timeout=12).get(PREFIX+ubigeo+'.sqlite3.gz')
        with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as source:
            body = source.read(MAX_DATABASE+1)
        if len(body)>MAX_DATABASE:
            raise StorageError('El índice supera el tamaño de lectura permitido.')
        etag = next((v for k,v in headers.items() if k.lower()=='etag'), None)
        if not etag:
            raise StorageError('R2 no devolvió la versión del índice.')
    except StorageError as error:
        if error.http_status != 404:
            raise
        body, etag = None, None
    except (OSError, EOFError):
        raise StorageError('El índice tabular requiere revisión; los originales se conservan.') from None
    with _lock:
        # Bound cache memory independently of the number of districts visited.
        if len(_cache)>=3:
            _cache.pop(min(_cache, key=lambda key: _cache[key][0]))
        _cache[ubigeo] = (time.monotonic(),body,etag)
    return registry.connect(body), etag


def save_batch(ubigeo, manifests):
    for attempt in range(3):
        db, etag = load(ubigeo, fresh=True)
        try:
            changed = 0
            for manifest, digest in manifests:
                if manifest.get('district_ubigeo') != ubigeo:
                    raise ValueError('El lote no pertenece al distrito del índice.')
                changed += int(registry.import_manifest(db,manifest,digest))
            db.commit()
            if not changed:
                return 0
            body = db.serialize()
            if len(body)>MAX_DATABASE:
                raise StorageError('El índice requiere partición antes de incorporar más datos.')
            compressed = gzip.compress(body, compresslevel=3)
            if len(compressed)>19_000_000:
                raise StorageError('El índice comprimido requiere partición.')
            key = PREFIX+ubigeo+'.sqlite3.gz'
            _, headers = R2(timeout=20).request('PUT',key,compressed,'application/gzip',
                            condition=('if-match',etag) if etag else ('if-none-match','*'))
            new_etag = next((v for k,v in headers.items() if k.lower()=='etag'),None)
            with _lock:
                _cache[ubigeo]=(time.monotonic(),body,new_etag)
            return changed
        except PreconditionFailed:
            if attempt == 2:
                raise StorageError('Otro proceso actualizó el índice. Reintenta el mismo bloque.') from None
        finally:
            db.close()


def index_batch(ubigeo, after='', lot_id=None):
    validate_district(ubigeo)
    lots, next_after = ([lot_id], None) if lot_id else list_lots(ubigeo,after)
    manifests, errors = [], []
    def fetch(lot):
        try:
            return lot, read_manifest(ubigeo,lot), None
        except (StorageError, ValueError, TypeError, KeyError):
            return lot, None, 'No se pudo leer o validar el índice del predio.'
    with ThreadPoolExecutor(max_workers=4) as pool:
        for lot, result, error in pool.map(fetch,lots):
            if error:
                errors.append({'lot_id':lot,'error':error})
            else:
                manifests.append(result)
    changed = save_batch(ubigeo,manifests) if manifests else 0
    return {'processed':len(lots),'updated':changed,'errors':errors,'next_after':next_after,
            'last_lot':lots[-1] if lots else after}
