"""Freeze an auditable current-offer snapshot; never modifies ACM or sources."""
import hashlib
import json
import logging
import time
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from datetime import timedelta

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from .identity_rules import RULE_VERSION as IDENTITY_RULE_VERSION
from .ml_context import LOCATION_RULE_VERSION, current_catalog_hash, fingerprint, load_zones

logger = logging.getLogger(__name__)
CRITERIA_VERSION = 'offer-exact-location-v2'
_schema_cache = (0, False)


def schema_ready():
    global _schema_cache
    now = time.monotonic()
    if now - _schema_cache[0] < 30:
        return _schema_cache[1]
    from django.db import connection
    from .models import MLDatasetSnapshot, MLDatasetEntry
    tables = set(connection.introspection.table_names())
    ready = all(model._meta.db_table in tables for model in (MLDatasetSnapshot, MLDatasetEntry))
    _schema_cache = (now, ready)
    return ready


def dashboard_state():
    if not schema_ready():
        return {'ready': False, 'id': None, 'message': 'La migración de conjuntos aún no está aplicada.'}
    from .models import MLDatasetSnapshot
    latest = MLDatasetSnapshot.objects.order_by('-pk').first()
    if not latest:
        return {'ready': False, 'id': None, 'history': [], 'message': 'El primer corte aparecerá cuando termine el análisis inicial.'}
    history = list(MLDatasetSnapshot.objects.order_by('-pk').values(
        'id', 'created_at', 'included', 'total', 'newly_included', 'removed_from_previous', 'status')[:10])
    return {'ready': True, 'id': latest.pk, 'created_at': latest.created_at,
            'included': latest.included, 'total': latest.total, 'status': latest.status,
            'newly_included': latest.newly_included,
            'removed_from_previous': latest.removed_from_previous,
            'excluded_reasons': latest.excluded_reasons, 'coverage': latest.coverage,
            'history': history}


def _num(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError, OverflowError):
        return None
    return float(result) if result.is_finite() else None


def _quality(entry):
    snapshot = entry['observation'].snapshot
    fields = ('area_terreno', 'area_construida', 'antiguedad_anios', 'dormitorios',
              'banos', 'estacionamientos', 'direccion_texto', 'descripcion')
    return sum(bool(snapshot.get(k) is not None and snapshot.get(k) != '') for k in fields)


class _Components:
    def __init__(self, ids):
        self.parent = {key: key for key in ids}

    def find(self, key):
        root = key
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[key] != key:
            parent = self.parent[key]
            self.parent[key] = root
            key = parent
        return root

    def union(self, left, right):
        a, b = self.find(left), self.find(right)
        if a != b:
            self.parent[max(a, b)] = min(a, b)


def _classified_entries(candidates, catalog_hash):
    from .models import MLIdentityPair
    zone_lookup = {str(zone['id']): zone for zone in load_zones()}
    ids = [c.propiedad_id for c in candidates]
    by_id = {c.propiedad_id: c for c in candidates}
    groups = _Components(ids)
    blocked = set()
    different_edges = []
    pair_query = MLIdentityPair.objects.filter(
        Q(left_id__in=ids) | Q(right_id__in=ids)).select_related(
            'left_observation', 'right_observation').order_by('pk')
    for pair in pair_query.iterator(chunk_size=500):
        left, right = by_id.get(pair.left_id), by_id.get(pair.right_id)
        if not left or not right:
            continue
        current = (pair.left_observation_id == left.latest_id and pair.right_observation_id == right.latest_id)
        if pair.status == 'different':
            if not current or pair.decision_stale:
                blocked.update((pair.left_id, pair.right_id))
            else:
                different_edges.append((pair.left_id, pair.right_id))
        elif pair.status == 'possible':
            if pair.active or pair.decision_stale:
                blocked.update((pair.left_id, pair.right_id))
        elif pair.status == 'same':
            if not current or pair.decision_stale:
                blocked.update((pair.left_id, pair.right_id))
                continue
            groups.union(pair.left_id, pair.right_id)

    components = defaultdict(list)
    for candidate in candidates:
        components[groups.find(candidate.propiedad_id)].append(candidate)
    representative = {}
    group_hash = {}
    for members in components.values():
        if len(members) == 1:
            continue
        member_ids = sorted(x.propiedad_id for x in members)
        digest = fingerprint({'rule': IDENTITY_RULE_VERSION, 'members': member_ids})
        if any(item.propiedad_id in blocked for item in members):
            blocked.update(member_ids)
        if any(groups.find(left) == groups.find(right) for left, right in different_edges):
            blocked.update(member_ids)
        def preference(candidate):
            snap = candidate.latest.snapshot
            context = candidate.context if candidate.context_id else None
            usable = bool(candidate.status == 'eligible' and snap.get('estado_publicacion') == 'activa'
                          and context and context.observation_id == candidate.latest_id
                          and context.state == 'exact_zone' and context.catalog_hash == catalog_hash
                          and not candidate.latest.status == 'excluded')
            return (usable, _quality({'observation': candidate.latest}), -candidate.propiedad_id)
        winner = max(members, key=preference)
        for item in members:
            group_hash[item.propiedad_id] = digest
            representative[item.propiedad_id] = winner.propiedad_id

    rows, reason_counts = [], Counter()
    for candidate in candidates:
        obs = candidate.latest
        context = candidate.context if candidate.context_id else None
        current_geo = bool(context and context.observation_id == obs.pk
                           and context.catalog_hash == catalog_hash
                           and context.rule_version == LOCATION_RULE_VERSION)
        reason_code, reason, include = '', '', False
        snapshot = obs.snapshot
        if candidate.status != 'eligible':
            reason_code = 'candidate.' + str(candidate.status)
            reason = next((item.get('message') for item in obs.reasons if item.get('message')),
                          'No cumple los requisitos de candidata preliminar.')
        elif snapshot.get('estado_publicacion') != 'activa':
            reason_code, reason = 'publication.not_confirmed', 'La publicación no está confirmada como activa.'
        elif candidate.propiedad_id in blocked:
            reason_code, reason = 'identity.review', 'Posible duplicado o decisión pendiente; revisar en Contexto.'
        elif candidate.propiedad_id in representative and representative[candidate.propiedad_id] != candidate.propiedad_id:
            reason_code, reason = 'identity.confirmed_duplicate', 'Publicación secundaria de una identidad revisada; se conserva como evidencia.'
        elif snapshot.get('tipo_operacion') not in ('Venta',):
            reason_code, reason = 'operation.not_sale', 'El corte de valoración usa ofertas de venta; alquiler y operación mixta se conservan como referencia.'
        elif not current_geo:
            reason_code, reason = 'location.context_pending', 'Precisa reevaluación espacial con el catálogo y registro actuales.'
        elif context.state not in ('exact_zone', 'exact_unzoned'):
            reason_code, reason = 'location.not_usable', 'Solo se incluye ubicación exacta declarada con contexto espacial válido.'
        else:
            required = ('area_terreno', 'area_construida') if snapshot.get('tipo_inmueble') == 'Casa' else (
                ('area_terreno',) if snapshot.get('tipo_inmueble') == 'Terreno' else ('area_construida',))
            values = {field: _num(snapshot.get(field)) for field in required}
            price = _num(snapshot.get('precio_usd'))
            if price is None or price <= 0 or any(value is None or value <= 0 for value in values.values()):
                reason_code, reason = 'features.incomplete', 'El precio en USD y las superficies requeridas deben ser positivos.'
            else:
                include, reason_code = True, 'included.offer'
                reason = ('Oferta activa, superficies válidas, identidad vigente y ubicación exacta declarada.'
                          if context.state == 'exact_unzoned' else
                          'Oferta activa, superficies válidas, identidad y microzona vigentes.')
        reason_counts[reason_code] += 1
        features = {key: snapshot.get(key) for key in (
            'fuente', 'id_origen', 'url', 'tipo_inmueble', 'tipo_operacion', 'precio_usd',
            'area_terreno', 'area_construida', 'antiguedad_anios', 'dormitorios', 'banos',
            'estacionamientos', 'latitud', 'longitud', 'precision_ubicacion', 'distrito')}
        if context and current_geo:
            version = context.zone_version
            features.update(zone_id=version.zone_key if version else None,
                            zone_version=version.sequence if version else None,
                            zone_name=(version.snapshot.get('nombre_zona') or version.snapshot.get('codigo')) if version else '')
            if version:
                ancestor_id = version.snapshot.get('parent_id')
                visited = {str(version.zone_key)}
                while ancestor_id is not None and str(ancestor_id) not in visited:
                    visited.add(str(ancestor_id))
                    ancestor = zone_lookup.get(str(ancestor_id))
                    if not ancestor:
                        break
                    if ancestor.get('nivel') in ('zona', 'distrito'):
                        features['parent_' + ancestor['nivel'] + '_id'] = ancestor['id']
                        features['parent_' + ancestor['nivel'] + '_name'] = ancestor.get('nombre_zona') or ancestor.get('codigo') or str(ancestor['id'])
                    ancestor_id = ancestor.get('parent_id')
        rows.append({'candidate': candidate, 'observation': obs,
            'spatial_assessment': context if current_geo else None,
            'included': include, 'reason_code': reason_code, 'reason': reason,
            'identity_group_hash': group_hash.get(candidate.propiedad_id, ''),
            'features': features, 'target_price_usd': Decimal(str(_num(snapshot.get('precio_usd'))))
                 if include else None})
    return rows, reason_counts


@transaction.atomic
def freeze_dataset(force=False):
    """Create one new immutable cut only after admission and spatial queues drain.

    Identity analysis must describe the exact current observation set. The first
    frozen snapshot waits until the full initial reconciliation has completed.
    """
    from .models import MLCandidate, MLPipelineState, MLDatasetSnapshot, MLDatasetEntry, MLObservation
    if not schema_ready():
        return {'dataset_skipped': 'dataset_schema_pending'}
    state, _ = MLPipelineState.objects.select_for_update().get_or_create(key='datasets')
    pipeline = MLPipelineState.objects.filter(pk='candidates').first()
    if not pipeline or not pipeline.sweep_finished_at:
        return {'dataset_skipped': 'initial_reconciliation_incomplete'}
    latest_snapshot = MLDatasetSnapshot.objects.order_by('-pk').only('pk', 'created_at', 'input_hash').first()
    now = timezone.now()
    if latest_snapshot and not force and latest_snapshot.created_at > now - timedelta(minutes=10):
        return {'dataset_skipped': 'coalescing_recent_changes', 'dataset_id': latest_snapshot.pk}
    if MLObservation.objects.filter(status='pending').exists():
        return {'dataset_skipped': 'admission_pending'}
    candidates = list(MLCandidate.objects.select_related('latest', 'context', 'context__zone_version').order_by('propiedad_id'))
    # Make all derived text snapshots consistent before this bounded write.
    catalog_hash = current_catalog_hash()
    if MLCandidate.objects.filter(Q(context__isnull=True) | ~Q(context__observation_id=F('latest_id')) |
        ~Q(context__catalog_hash=catalog_hash) | ~Q(context__rule_version=LOCATION_RULE_VERSION)).exists():
        return {'dataset_skipped': 'spatial_context_pending'}
    observations_hash = [(item.propiedad_id, item.latest_id) for item in candidates]
    identity_state = MLPipelineState.objects.filter(pk='identity').first()
    identity_hash = fingerprint([IDENTITY_RULE_VERSION, observations_hash])
    if not identity_state or identity_state.payload.get('input_hash') != identity_hash:
        return {'dataset_skipped': 'identity_review_pending'}
    rows, reason_counts = _classified_entries(candidates, catalog_hash)
    material = {'criteria': CRITERIA_VERSION, 'geo_rule': LOCATION_RULE_VERSION,
                'identity_rule': IDENTITY_RULE_VERSION, 'catalog': catalog_hash,
                'rows': [(row['candidate'].propiedad_id, row['observation'].content_hash,
                          row['spatial_assessment'].pk if row['spatial_assessment'] else None,
                          row['included'], row['reason_code'], row['identity_group_hash']) for row in rows],
                # Decision effects are already represented by each row's group,
                # exclusion reason and inclusion flag. Worker leases/heartbeats
                # are operational state and must not create fake dataset versions.
                'identity_input_hash': (identity_state.payload or {}).get('input_hash')}
    input_hash = fingerprint(material)
    latest = latest_snapshot
    if latest and latest.input_hash == input_hash:
        return {'dataset_skipped': 'unchanged', 'dataset_id': latest.pk}
    # Once the first catalog sweep is done, reserve a bounded change window to
    # coalesce multiple updates from a single scrape run into one dataset cut.
    included_ids = {row['candidate'].propiedad_id for row in rows if row['included']}
    previous_ids = set(MLDatasetEntry.objects.filter(dataset=latest, included=True).values_list('candidate_id', flat=True)) if latest else set()
    coverage = {'by_type': dict(Counter(row['features'].get('tipo_inmueble') or 'Sin tipo'
                                        for row in rows if row['included'])),
                'by_portal': dict(Counter(row['features'].get('fuente') or 'Sin portal'
                                          for row in rows if row['included'])),
                'by_parent_zone': dict(Counter(row['features'].get('parent_zona_name')
                                               for row in rows if row['included'] and row['features'].get('parent_zona_name'))),
                'by_parent_district': dict(Counter(row['features'].get('parent_distrito_name')
                                                   for row in rows if row['included'] and row['features'].get('parent_distrito_name'))),
                'without_subzone': sum(1 for row in rows if row['included'] and not row['features'].get('zone_id')),
                'microzones': len({row['features'].get('zone_id') for row in rows
                                   if row['included'] and row['features'].get('zone_id') is not None})}
    dataset = MLDatasetSnapshot.objects.create(criteria_version=CRITERIA_VERSION,
        spatial_rule_version=LOCATION_RULE_VERSION, identity_rule_version=IDENTITY_RULE_VERSION,
        catalog_hash=catalog_hash, input_hash=input_hash, total=len(rows), included=len(included_ids),
        excluded_reasons=dict(reason_counts), coverage=coverage,
        newly_included=len(included_ids - previous_ids),
        removed_from_previous=len(previous_ids - included_ids), status='ready' if included_ids else 'empty')
    MLDatasetEntry.objects.bulk_create([
        MLDatasetEntry(dataset=dataset, candidate=row['candidate'], observation=row['observation'],
            spatial_assessment=row['spatial_assessment'], included=row['included'],
            reason_code=row['reason_code'], reason=row['reason'][:300],
            identity_group_hash=row['identity_group_hash'], features=row['features'],
            target_price_usd=row['target_price_usd']) for row in rows], batch_size=100)
    state.payload = {'latest_dataset_id': dataset.pk, 'latest_dataset_hash': input_hash}
    state.heartbeat_at = now
    state.save(update_fields=['payload', 'heartbeat_at'])
    logger.info('ml.dataset.frozen id=%s total=%s included=%s new=%s removed=%s hash=%s',
                dataset.pk, dataset.total, dataset.included, dataset.newly_included,
                dataset.removed_from_previous, dataset.input_hash[:12])
    return {'dataset_created': dataset.pk, 'dataset_total': dataset.total,
            'dataset_included': dataset.included, 'dataset_newly_included': dataset.newly_included,
            'dataset_removed_from_previous': dataset.removed_from_previous}
