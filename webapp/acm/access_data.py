"""Confidential snapshots and field projection for every ACM delivery format."""
import base64
import copy
import hashlib
import hmac
import json
import re
import time
import zlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core import signing

from .listing_operation import POLICY_VERSION
from .access import database
from .access_models import ACMPhotoReview


def cipher():
    key = hmac.new(settings.SECRET_KEY.encode(), b'acm-private-snapshots-v1', hashlib.sha256).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def seal(data):
    return cipher().encrypt(zlib.compress(json.dumps(data, separators=(',', ':')).encode())).decode()


def unseal(token, ttl=1800):
    try:
        if not isinstance(token, str) or len(token) > 8_000_000:
            raise ValueError
        raw = cipher().decrypt(token.encode(), ttl=ttl)
        data = json.loads(zlib.decompress(raw))
        if not isinstance(data, dict):
            raise ValueError
        return data
    except InvalidToken as exc:
        # Fernet reports expiration and tampering through the same exception.
        # Authenticate the timestamp before identifying an expired analysis.
        try:
            timestamp = cipher().extract_timestamp(token.encode())
        except (InvalidToken, ValueError, TypeError, AttributeError):
            raise signing.BadSignature('ACM snapshot expired or invalid') from exc
        if ttl is not None and time.time() - timestamp > ttl:
            raise signing.SignatureExpired('ACM snapshot expired') from exc
        raise signing.BadSignature('ACM snapshot expired or invalid') from exc
    except (ValueError, TypeError, zlib.error) as exc:
        raise signing.BadSignature('ACM snapshot expired or invalid') from exc


def issue_snapshot(request, state):
    return seal({'scope': request.acm_access.fingerprint, 'listing_policy': POLICY_VERSION, 'state': state})


def read_snapshot(request, token):
    data = unseal(token)
    if data.get('scope') != request.acm_access.fingerprint or data.get('listing_policy') != POLICY_VERSION:
        raise signing.BadSignature('role or policy changed')
    return data['state']


def opaque_id(request, value):
    message = ('acm-record:' + str(request.acm_access.user.pk) + ':' + str(value)).encode()
    return 'c-' + hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()[:24]


def photo_digest(url):
    value = str(url)
    parsed = urlsplit(value)
    if (parsed.hostname or '').endswith('.blob.core.windows.net'):
        sas = {'sv', 'ss', 'srt', 'sp', 'se', 'st', 'spr', 'sig', 'sr', 'skoid', 'sktid', 'skt', 'ske', 'sks', 'skv', 'sip'}
        query = sorted((key, item) for key, item in parse_qsl(parsed.query) if key.lower() not in sas)
        value = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), ''))
    return hashlib.sha256(value.encode()).hexdigest()


def photo_ticket(request, url):
    return seal({'kind': 'photo', 'scope': request.acm_access.fingerprint, 'url': url})


def project(request, state, result=None, excluded=(), report=False):
    """Keep calculation inputs on the server; emit only permitted property fields."""
    from .property_gallery import gallery_ticket
    access = request.acm_access
    p = access.permissions
    state = copy.deepcopy(state)
    if not p['report_notes']:
        state.get('params', {}).pop('report_notes', None)
    records = state.get('records', [])
    identities = {r['id']: opaque_id(request, r['id']) for r in records}
    urls = [r.get('image') for r in records if r.get('image')]
    approved = set()
    if urls and p['photos'] and not p['unreviewed_photos']:
        approved = set(ACMPhotoReview.objects.using(database()).filter(
            digest__in=[photo_digest(url) for url in urls], approved=True).values_list('digest', flat=True))
    for index, record in enumerate(records, 1):
        gallery = gallery_ticket(request, record) if p['photos'] and not report else ''
        record.pop('_operation_title', None)
        record.pop('_operation_title_lower', None)
        if not p['metadata']:
            allowed = {'id', 'source', 'code', 'title', 'kind', 'description', 'rooms', 'baths', 'floor', 'floor_label', 'age',
                       'parking_has', 'parking_types', 'parking_status',
                       'price', 'converted', 'land', 'built', 'lat', 'lng', 'precision', 'state',
                       'first_seen', 'last_seen', 'operation', 'operation_status', 'district', 'url', 'image', 'distance',
                       'land_similarity', 'built_similarity', 'distance_similarity', 'overall_similarity', 'issues', 'duplicate_of'}
            for key in set(record) - allowed:
                record.pop(key, None)
        if not (p['metadata'] and p['portal_names']):
            record['code'] = 'Comparable ' + str(index)
        if not p['metadata']:
            record.pop('record_id', None)
        if not p['portal_names']:
            for key in ('district', 'kind'):
                if isinstance(record.get(key), str):
                    record[key] = re.sub(r'(?i)\b(?:re/?max|properati|adondevivir|urbania|propify|propifai)\b', '', record[key]).strip()
            record['source'] = 'comparable'
            record['title'] = ' · '.join(str(v) for v in (record.get('kind'), record.get('district')) if v)
            record['description'] = ''
        publication_url = record.get('url') or ''
        if p['portal_link'] and publication_url:
            parsed = urlsplit(publication_url)
            record['portal_url'] = urlunsplit((parsed.scheme, parsed.netloc, '/', '', ''))
        else:
            record.pop('portal_url', None)
        if not p['publication']:
            record['url'] = ''
        if not p['publication_dates']:
            record.pop('first_seen', None)
        if not p['last_seen']:
            record.pop('last_seen', None)
        if not p['metadata']:
            for key in ('first_missing', 'retired_at', 'consecutive_absences', 'review_excluded', 'state'):
                record.pop(key, None)
        url = record.get('image')
        if not p['photos'] or (report and not p['report_photos']):
            record['image'] = ''
        elif url and (p['unreviewed_photos'] or photo_digest(url) in approved):
            # Image delivery never exposes the provider URL to a restricted browser.
            record['image'] = '/acm/fotos/' + photo_ticket(request, url) + '/'
            if report:
                record['image'] = url  # Builders fetch server-side; source URLs are not exported.
        else:
            record['image'] = ''
        if gallery:
            record['gallery_url'] = '/acm/galeria/' + gallery + '/'
        if access.can_configure and not access.previewing and url:
            record['photo_review'] = photo_ticket(request, url)
        if not p['property_data']:
            for key in list(record):
                if key not in ('id', 'kind', 'source', 'code', 'title', 'issues', 'distance'):
                    record.pop(key, None)
    if not p['portal_names']:
        state.get('params', {})['sources'] = ['comparables']
        for key in ('proposal_explanation', 'ai_review_recommendations'):
            state.get('params', {}).pop(key, None)
        state['warnings'] = ['Una fuente de comparables no respondió. El resultado es parcial.'] if state.get('warnings') else []
    state.pop('user', None)
    state.setdefault('params', {})['_acm_permissions'] = p
    # The same opaque identifiers must be used in records, results and selections.
    identifier_fields = {'id', 'duplicate_of', 'built_reference_id', 'land_ids', 'house_ids',
                         'reference_ids', 'reference_display_ids', 'report_ids', 'excluded_ids', 'recommended_ids', 'ids'}
    def replace(value, field=None):
        if isinstance(value, dict):
            return {k: replace(v, k) for k, v in value.items()}
        if isinstance(value, list):
            return [replace(v, field) for v in value]
        if isinstance(value, tuple):
            return [replace(v, field) for v in value]
        if isinstance(value, str) and field in identifier_fields:
            return identities.get(value, value)
        return value
    return replace(state), replace(result), [identities.get(value, value) for value in excluded]


def restore_selection(request, state, data):
    identities = {opaque_id(request, row['id']): row['id'] for row in state['records']}
    output = dict(data)
    for key in ('excluded', 'report_ids'):
        if key in output:
            values = output[key]
            if not isinstance(values, list) or len(values) > 4000 or any(not isinstance(v, str) or v not in identities for v in values):
                raise ValueError('selection')
            output[key] = [identities[v] for v in values]
    return output


def persist_history(user, params, records, result, excluded=()):
    from .access_models import ACMPortalAnalysis
    if not result.get('new'):
        raise ValueError('Primero completa el cálculo.')
    snapshot = {'params': params, 'records': records, 'result': result, 'excluded': list(excluded)}
    fingerprint = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    return ACMPortalAnalysis.objects.using(database()).get_or_create(
        owner_id=str(user.pk), fingerprint=fingerprint, defaults={'snapshot': snapshot})
