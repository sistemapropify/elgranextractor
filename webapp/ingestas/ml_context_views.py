"""Authenticated spatial context and human identity review; no training actions."""
import json
from collections import Counter
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator
from django.db.models import Count, F, Max, Q, Subquery
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from . import ml_context
from .ml_candidate_views import authorized
from .ml_eligibility import LABELS
from .models import MLCandidate, MLIdentityDecision, MLIdentityPair, MLZoneVersion
from .property_access import allowed, user_for


# Tope de pines por area visible; el mapa usa el mismo valor en MAX_MARKERS.
MAP_LIMIT = 2000
GEO_LABELS = {**ml_context.GEO_LABELS, 'stale': 'Ubicación pendiente de reevaluar'}
PAIR_LABELS = {'possible': 'Posible coincidencia', 'same': 'Misma propiedad, según revisión',
               'different': 'Propiedades diferentes, según revisión'}
_LAYER_STATES = {'eligible': ('eligible',), 'reference': ('reference',),
                 'review': ('review', 'pending', 'error', 'excluded')}


def safe_publication(value):
    if not isinstance(value, str) or len(value) > 2048:
        return ''
    value = value.strip()
    if not value or '\\' in value or any(ord(c) < 33 for c in value):
        return ''
    try:
        parts = urlsplit(value)
        if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password:
            return ''
        parts.port  # Validate malformed port strings, without imposing a portal list.
    except (ValueError, UnicodeError):
        return ''
    return value


def _positive_id(value, label='Registro'):
    text = str(value)
    if not text.isascii() or not text.isdigit() or len(text) > 19:
        raise ValueError(label + ' inválido.')
    number = int(text)
    if not 0 < number <= 9223372036854775807:
        raise ValueError(label + ' inválido.')
    return number


def _record(request):
    value = request.GET.get('record')
    return _positive_id(value) if value not in (None, '') else None


def _bbox(params):
    values = {}
    for name in ('south', 'west', 'north', 'east'):
        raw = params.get(name)
        if raw is None or len(str(raw)) > 40:
            raise ValueError('Se requiere el área visible: south, west, north y east.')
        try:
            value = Decimal(str(raw))
        except (InvalidOperation, ValueError):
            raise ValueError('Los límites del mapa deben ser números finitos.') from None
        if not value.is_finite():
            raise ValueError('Los límites del mapa deben ser números finitos.')
        values[name] = value
    if not (-90 <= values['south'] < values['north'] <= 90
            and -180 <= values['west'] < values['east'] <= 180):
        raise ValueError('El área visible está fuera de rango o sus límites están invertidos.')
    return values


def _layers(params):
    values = {part.strip() for part in str(params.get('layers') or '').split(',') if part.strip()}
    if not values <= set(_LAYER_STATES) | {'duplicates'}:
        raise ValueError('Capa de mapa desconocida.')
    return values


def _json(data, status=200):
    response = JsonResponse(data, status=status)
    response['Cache-Control'] = 'private, no-store'
    return response


def _candidates():
    return MLCandidate.objects.select_related('propiedad', 'latest', 'context', 'context__zone_version').defer(
        'propiedad__datos_crudos', 'propiedad__descripcion')


def _current_pairs():
    """Only active evidence concerning both current observation versions."""
    return MLIdentityPair.objects.filter(active=True,
        left_observation_id=F('left__ml_candidate__latest_id'),
        right_observation_id=F('right__ml_candidate__latest_id')).exclude(
            status='different', decision_stale=False)


# SQL Server admite 2100 parametros por consulta y el mapa puede devolver
# MAP_LIMIT identificadores: se leen las parejas por lotes y se deduplican.
_DUPLICATE_ID_CHUNK = 1000


def _duplicate_counts(ids):
    counts = Counter()
    included = set(ids)
    if not included:
        return counts
    ordered = sorted(included)
    pairs = set()
    for offset in range(0, len(ordered), _DUPLICATE_ID_CHUNK):
        chunk = ordered[offset:offset + _DUPLICATE_ID_CHUNK]
        pairs.update(
            _current_pairs()
            .filter(Q(left_id__in=chunk) | Q(right_id__in=chunk))
            .values_list('left_id', 'right_id')
        )
    for left, right in pairs:
        if left in included:
            counts[left] += 1
        if right in included:
            counts[right] += 1
    return counts


def _geo(candidate, catalog_hash):
    assessment = candidate.context if candidate.context_id else None
    current = bool(assessment and ml_context.is_current_context(candidate, catalog_hash))
    snapshot = candidate.latest.snapshot
    # Bulk source edits may precede the reconciliation that captures a new version.
    source = candidate.propiedad
    if (_number(snapshot.get('latitud')) != _number(source.latitud)
            or _number(snapshot.get('longitud')) != _number(source.longitud)
            or snapshot.get('precision_ubicacion') != source.precision_ubicacion):
        current = False
    if current and assessment.state == 'exact_zone' and not assessment.zone_version_id:
        current = False
    state = assessment.state if current else 'stale' if assessment else 'pending'
    if state not in GEO_LABELS:
        state = 'stale'
        current = False
    zone = assessment.zone_version if current and state == 'exact_zone' and assessment.zone_version_id else None
    snapshot = zone.snapshot if zone and isinstance(zone.snapshot, dict) else {}
    return dict(state=state, label=GEO_LABELS[state], current=current,
                zone_name=snapshot.get('nombre_zona') or snapshot.get('codigo') or '',
                zone_version=zone.sequence if zone else None,
                evidence=assessment.evidence if current else [],
                rule=assessment.rule_version if current else '')


def _number(value):
    try:
        number = Decimal(str(value))
        return float(number) if number.is_finite() and abs(number) < Decimal('1e100') else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def _feature(candidate, catalog_hash, duplicate_count=0):
    snapshot = candidate.latest.snapshot
    geo = _geo(candidate, catalog_hash)
    return dict(id=candidate.propiedad_id, fuente=snapshot.get('fuente') or '',
        code=snapshot.get('id_origen') or '', title=snapshot.get('titulo') or '',
        # Tipo de propiedad: permite filtrar la capa ML en el mapa.
        property_type=str(snapshot.get('tipo_inmueble') or '').strip() or 'Propiedad',
        lat=_number(snapshot.get('latitud')), lng=_number(snapshot.get('longitud')),
        price_usd=_number(snapshot.get('precio_usd')), land_area=_number(snapshot.get('area_terreno')),
        built_area=_number(snapshot.get('area_construida')), age=_number(snapshot.get('antiguedad_anios')),
        precision=snapshot.get('precision_ubicacion') or 'desconocida',
        status=candidate.status, status_label=LABELS.get(candidate.status, 'Estado pendiente'),
        geo_status=geo['state'], geo_label=geo['label'], zone_name=geo['zone_name'],
        zone_version=geo['zone_version'], duplicate_count=duplicate_count,
        url=safe_publication(snapshot.get('url')))


@require_GET
def map_data(request):
    if not authorized(request):
        return _json({'error': 'Inicia sesión.'}, 401)
    try:
        bounds, layers, record = _bbox(request.GET), _layers(request.GET), _record(request)
    except ValueError as exc:
        return _json({'error': str(exc)}, 400)
    if not ml_context.schema_ready():
        return _json({'ready': False, 'error': 'Migración del contexto ML pendiente.'}, 503)
    if not layers:
        return _json(dict(features=[], total=0, shown=0, truncated=False, limit=MAP_LIMIT, ready=True))
    query = _candidates().filter(propiedad__latitud__gte=bounds['south'],
        propiedad__latitud__lte=bounds['north'], propiedad__longitud__gte=bounds['west'],
        propiedad__longitud__lte=bounds['east'])
    if record:
        query = query.filter(propiedad_id=record)
    states = [status for layer in sorted(layers) for status in _LAYER_STATES.get(layer, ())]
    selected = Q(status__in=states)
    if 'duplicates' in layers:
        pairs = _current_pairs()
        selected |= Q(propiedad_id__in=Subquery(pairs.values('left_id')))
        selected |= Q(propiedad_id__in=Subquery(pairs.values('right_id')))
    query = query.filter(selected).order_by('propiedad_id')
    total = query.count()
    candidates = list(query[:MAP_LIMIT])
    counts = _duplicate_counts([c.propiedad_id for c in candidates])
    catalog_hash = ml_context.current_catalog_hash()
    prepared = [_feature(c, catalog_hash, counts[c.propiedad_id]) for c in candidates]
    # SQL bounds select live source rows; an uncaptured bulk edit can leave a
    # snapshot outside this viewport. Never move that historical snapshot's pin.
    features = [item for item in prepared if item['lat'] is not None and item['lng'] is not None
                and bounds['south'] <= item['lat'] <= bounds['north']
                and bounds['west'] <= item['lng'] <= bounds['east']]
    return _json(dict(features=features, total=total, shown=len(features), truncated=total > len(features),
                      limit=MAP_LIMIT, ready=True, omitted_stale_coordinates=len(prepared) - len(features)))


def _pair_is_current(pair):
    try:
        return (pair.left_observation_id == pair.left.ml_candidate.latest_id
                and pair.right_observation_id == pair.right.ml_candidate.latest_id)
    except ObjectDoesNotExist:
        return False


def _coverage(catalog_hash, page_number=None):
    """Aggregate latest recorded observations, without inferring unique properties."""
    current = Q(context__catalog_hash=catalog_hash, context__observation_id=F('latest_id'),
                context__rule_version=ml_context.LOCATION_RULE_VERSION)
    query = MLCandidate.objects.all()
    evaluated = query.filter(current).values('context__zone_version_id', 'context__state', 'status').annotate(
        n=Count('pk'), updated=Max('context__created_at'))
    awaiting = query.filter(Q(context__isnull=True) | ~current).values('status').annotate(
        n=Count('pk'), updated=Max('context__created_at'))

    def blank():
        return dict(total=0, eligible=0, reference=0, review=0, excluded=0, pending=0, error=0, updated=None)

    def add(target, item):
        target['total'] += item['n']
        state = item['status'] if item['status'] in LABELS else 'pending'
        target[state] += item['n']
        if item['updated'] and (not target['updated'] or item['updated'] > target['updated']):
            target['updated'] = item['updated']

    grouped, unassigned, pending = {}, blank(), blank()
    for item in evaluated:
        version_id = item['context__zone_version_id']
        if item['context__state'] == 'exact_zone' and version_id:
            target = grouped.setdefault(version_id, blank())
        else:
            target = unassigned
        add(target, item)
    for item in awaiting:
        add(pending, item)
    # Only the current page resolves version snapshots, never the full history.
    page = Paginator([dict(version_id=key, **value) for key, value in sorted(grouped.items())], 30).get_page(page_number)
    versions = {item.pk: item for item in MLZoneVersion.objects.filter(
        pk__in=[item['version_id'] for item in page]).only('pk', 'zone_key', 'sequence', 'snapshot')}
    for item in page:
        version = versions.get(item['version_id'])
        snapshot = version.snapshot if version and isinstance(version.snapshot, dict) else {}
        item.update(name=snapshot.get('nombre_zona') or snapshot.get('codigo') or 'Microzona sin nombre',
                    zone_key=version.zone_key if version else None,
                    sequence=version.sequence if version else None)
    return dict(zones=page, unassigned=unassigned, pending=pending,
                total=sum(item['total'] for item in grouped.values()) + unassigned['total'] + pending['total'])


@require_GET
@ensure_csrf_cookie
def dashboard(request):
    if not authorized(request):
        return HttpResponse('Inicia sesión para consultar el contexto.', status=401)
    try:
        record = _record(request)
        pair_filter = request.GET.get('pair_state', 'active')
        if pair_filter not in {'active', 'all', 'different'}:
            raise ValueError('Filtro de coincidencias inválido.')
    except ValueError as exc:
        return HttpResponse(str(exc), status=400)
    if not ml_context.schema_ready():
        return render(request, 'ingestas/property_quality.html',
                      {'ml_context_mode': True, 'context_ready': False}, status=503)
    catalog_hash = ml_context.current_catalog_hash()
    candidates = _candidates().order_by('propiedad_id')
    pairs = MLIdentityPair.objects.select_related('left', 'right',
        'left__ml_candidate', 'right__ml_candidate', 'left_observation', 'right_observation').defer(
            'left__datos_crudos', 'right__datos_crudos', 'left__descripcion', 'right__descripcion').order_by('-score', 'pk')
    if pair_filter == 'active':
        pairs = pairs.filter(active=True)
    elif pair_filter == 'different':
        pairs = pairs.filter(status='different')
    if record:
        candidates = candidates.filter(propiedad_id=record)
        pairs = pairs.filter(Q(left_id=record) | Q(right_id=record))
    page = Paginator(candidates, 30).get_page(request.GET.get('page'))
    duplicates = _duplicate_counts([c.propiedad_id for c in page])
    for candidate in page:
        candidate.geo = _geo(candidate, catalog_hash)
        candidate.status_label = LABELS.get(candidate.status, 'Estado pendiente')
        candidate.publication_url = safe_publication(candidate.latest.snapshot.get('url'))
        candidate.duplicate_count = duplicates[candidate.propiedad_id]
        candidate.geo_evidence_json = json.dumps(candidate.geo['evidence'], ensure_ascii=False, indent=2, default=str)
    pair_page = Paginator(pairs, 20).get_page(request.GET.get('pair_page'))
    pair_ids = [pair.pk for pair in pair_page]
    last_ids = MLIdentityDecision.objects.filter(pair_id__in=pair_ids).values('pair_id').annotate(last=Max('pk')).values_list('last', flat=True)
    last_decisions = {item.pair_id: item for item in MLIdentityDecision.objects.filter(pk__in=list(last_ids))}
    for pair in pair_page:
        pair.evidence_current = pair.active and _pair_is_current(pair)
        pair.needs_review = pair.active and (pair.decision_stale or not pair.evidence_current)
        pair.status_label = PAIR_LABELS.get(pair.status, 'Posible coincidencia')
        pair.last_decision = last_decisions.get(pair.pk)
        pair.evidence_json = json.dumps(pair.evidence, ensure_ascii=False, indent=2, default=str)
        pair.left_url = safe_publication(pair.left_observation.snapshot.get('url'))
        pair.right_url = safe_publication(pair.right_observation.snapshot.get('url'))
    params = request.GET.copy()
    params['tab'] = 'contexto'
    candidate_params, pair_params, coverage_params = params.copy(), params.copy(), params.copy()
    candidate_params.pop('page', None)
    pair_params.pop('pair_page', None)
    coverage_params.pop('coverage_page', None)
    return render(request, 'ingestas/property_quality.html', dict(
        ml_context_mode=True, context_ready=True, context_page=page, pair_page=pair_page,
        context_params=candidate_params.urlencode(), pair_params=pair_params.urlencode(),
        record_filter=record or '', can_edit=allowed(user_for(request)),
        pair_filter=pair_filter, pair_scope_label={'active': 'pares activos',
            'all': 'pares guardados, incluido el historial', 'different': 'pares descartados por revisión'}[pair_filter],
        location_rule=ml_context.LOCATION_RULE_VERSION, pair_labels=PAIR_LABELS,
        coverage=_coverage(catalog_hash, request.GET.get('coverage_page')),
        coverage_params=coverage_params.urlencode()))


@require_POST
@csrf_protect
def decide(request, pk):
    if not authorized(request):
        return _json({'error': 'Inicia sesión.'}, 401)
    user = user_for(request)
    if not allowed(user):
        return _json({'error': 'Se requiere permiso para editar propiedades scrapeadas.'}, 403)
    if not ml_context.schema_ready():
        return _json({'ready': False, 'error': 'Migración del contexto ML pendiente.'}, 503)
    try:
        if request.content_type == 'application/json':
            body = request.body
            if len(body) > 16384:
                raise ValueError('Solicitud demasiado extensa.')
            data = json.loads(body)
        else:
            # CSRF may already have consumed a multipart body; use parsed POST.
            data = request.POST
        if not hasattr(data, 'get'):
            raise ValueError('Solicitud inválida.')
        revision = _positive_id(data.get('revision'), 'Versión de revisión')
        decision = data.get('decision')
        reason = data.get('reason')
        if (not isinstance(decision, str) or decision not in PAIR_LABELS
                or not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 2000):
            raise ValueError('Elige una decisión e indica un motivo de hasta 2000 caracteres.')
        actor = str(getattr(user, 'username', None) or getattr(user, 'pk', 'usuario autenticado'))
        ml_context.decide_pair(pk, revision, decision, reason.strip(), actor)
    except (ValueError, UnicodeError) as exc:
        return _json({'error': str(exc) or 'Solicitud inválida.'}, 400)
    except RuntimeError:
        return _json({'error': 'La evidencia cambió. Actualiza la página y revisa las versiones actuales.'}, 409)
    except ObjectDoesNotExist:
        return _json({'error': 'La coincidencia ya no está disponible.'}, 404)
    return _json({'ok': True, 'message': 'Decisión guardada con motivo y versiones revisadas.'})
