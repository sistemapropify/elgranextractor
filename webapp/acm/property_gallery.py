"""On-demand property galleries with the same scoped delivery as ACM covers."""
from urllib.parse import quote

from django.core import signing
from django.db import connections
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from .access import database, required
from .access_data import photo_digest, photo_ticket, seal, unseal
from .access_models import ACMPhotoReview


def gallery_ticket(request, record):
    source = record.get('source')
    identity = str(record.get('id', '')).removeprefix(str(source) + '-')
    if source not in ('remax', 'properati', 'urbania', 'adondevivir', 'propify') or not identity.isdigit():
        return ''
    return seal({'kind': 'gallery', 'scope': request.acm_access.fingerprint,
                 'source': source, 'id': int(identity), 'cover': record.get('image') or ''})


def property_photos(item):
    """Read already captured images; opening a gallery never starts scraping."""
    from scrapi.photo_gallery import gallery_photos
    if item['source'] == 'propify':
        from cuadrantizacion.views import PROPIFY_MEDIA_BASE_URL
        with connections['propifai'].cursor() as cursor:
            cursor.execute("SELECT [file] FROM property_media WHERE property_id=%s "
                           "AND media_type='image' ORDER BY [file]", [item['id']])
            paths = [row[0] for row in cursor.fetchall() if row[0]]
        urls = [str(path) if str(path).startswith(('http://', 'https://')) else
                PROPIFY_MEDIA_BASE_URL + '/' + '/'.join(quote(part, safe='') for part in str(path).lstrip('/').split('/'))
                for path in paths]
        raw = {'photos': urls}
        cover = item.get('cover')
    else:
        from ingestas.models import PropiedadesCompetencia
        obj = get_object_or_404(PropiedadesCompetencia.objects.only('datos_crudos', 'imagen_url'),
                               pk=item['id'], fuente=item['source'])
        raw, cover = obj.datos_crudos, obj.imagen_url
    return gallery_photos(raw, cover)


@require_GET
@required('photos')
def gallery(request, ticket):
    try:
        item = unseal(ticket)
        if (item.get('kind') != 'gallery' or item.get('scope') != request.acm_access.fingerprint
                or item.get('source') not in ('remax', 'properati', 'urbania', 'adondevivir', 'propify')
                or type(item.get('id')) is not int):
            raise ValueError
    except (signing.BadSignature, ValueError, TypeError):
        raise Http404
    photos = property_photos(item)
    approved = None
    if not request.acm_access.permissions['unreviewed_photos']:
        approved = set(ACMPhotoReview.objects.using(database()).filter(
            digest__in=[photo_digest(row['url']) for row in photos], approved=True).values_list('digest', flat=True))
    urls = []
    seen = set()
    for row in photos:
        url = row['url']
        digest = photo_digest(url)
        if digest in seen or (approved is not None and digest not in approved):
            continue
        seen.add(digest)
        urls.append('/acm/fotos/' + photo_ticket(request, url) + '/')
    return JsonResponse({'photos': urls, 'count': len(urls)})
