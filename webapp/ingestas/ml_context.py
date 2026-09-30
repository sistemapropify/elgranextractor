"""Versioned geographic context and conservative, audited identity suggestions.

No training, changes to offer prices, source merges or automatic exclusions.
"""
import hashlib
import json
import logging
import time
import uuid
from datetime import timedelta

from django.apps import apps
from django.db import connection, transaction
from django.db.models import Q, F
from django.utils import timezone

from .identity_rules import propose_pairs, _unit, RULE_VERSION as IDENTITY_RULE_VERSION
from .spatial_rules import assess_location, SPATIAL_RULE_VERSION as LOCATION_RULE_VERSION

logger = logging.getLogger(__name__)
_schema_cache = (0, False)
ZONE_FIELDS = ('id', 'nivel', 'parent_id', 'coordenadas', 'activo', 'nombre_zona', 'codigo')
GEO_LABELS = {'exact_zone': 'Exacta declarada · microzona asignada',
              'exact_unzoned': 'Exacta declarada · sin microzona',
              'approximate_reference': 'Aproximada o precisión desconocida · referencia',
              'missing': 'Sin coordenada válida', 'ambiguous': 'Límite o solapamiento por revisar',
              'invalid_zone': 'Geometría o jerarquía de zona por revisar', 'pending': 'Contexto pendiente'}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), default=str).encode()).hexdigest()


def schema_ready():
    global _schema_cache
    now = time.monotonic()
    if now - _schema_cache[0] < 30:
        return _schema_cache[1]
    from .models import MLZoneVersion, MLSpatialAssessment, MLIdentityPair, MLIdentityDecision, MLCandidate, MLPipelineState
    tables = set(connection.introspection.table_names())
    ok = all(m._meta.db_table in tables for m in (MLZoneVersion, MLSpatialAssessment, MLIdentityPair, MLIdentityDecision, MLCandidate, MLPipelineState))
    if ok:
        with connection.cursor() as cursor:
            ok = ('context_id' in {c.name for c in connection.introspection.get_table_description(cursor, MLCandidate._meta.db_table)}
                  and 'payload' in {c.name for c in connection.introspection.get_table_description(cursor, MLPipelineState._meta.db_table)})
    _schema_cache = now, ok
    return ok


def load_zones():
    try:
        model = apps.get_model('cuadrantizacion', 'ZonaValor')
    except LookupError:
        # Isolated tests may omit this app; production must install it.
        return []
    return list(model.objects.order_by('pk').values(*ZONE_FIELDS))


def current_catalog_hash():
    return fingerprint(load_zones())


def is_current_context(candidate, catalog_hash):
    ctx = candidate.context if candidate.context_id else None
    return bool(ctx and ctx.observation_id == candidate.latest_id and
                ctx.catalog_hash == catalog_hash and ctx.rule_version == LOCATION_RULE_VERSION)


@transaction.atomic
def snapshot_catalog(zones):
    from .models import MLZoneVersion, MLPipelineState
    MLPipelineState.objects.get_or_create(key='zone-catalog')
    state = MLPipelineState.objects.select_for_update().get(pk='zone-catalog')
    if fingerprint(load_zones()) != fingerprint(zones):
        raise RuntimeError('El catálogo cambió; se conserva el contexto y se reintentará.')
    last = {}
    for version in MLZoneVersion.objects.order_by('zone_key', '-sequence'):
        last.setdefault(version.zone_key, version)
    result = {}
    # A removed live polygon gets a tombstone, preserving all previous geometry.
    current_ids = {z['id'] for z in zones}
    entries = list(zones) + [{**v.snapshot, 'activo': False, 'deleted': True}
                            for key, v in last.items() if key not in current_ids]
    for zone in entries:
        key, digest = zone['id'], fingerprint(zone)
        old = last.get(key)
        if not old or old.content_hash != digest:
            old = MLZoneVersion.objects.create(zone_key=key, sequence=old.sequence + 1 if old else 1,
                                               content_hash=digest, snapshot=zone)
            logger.info('ml.zone.version zone=%s version=%s', key, old.sequence)
        result[key] = old
    state.payload = {'catalog_hash': fingerprint(zones), 'zones': len(zones)}
    state.heartbeat_at = timezone.now()
    state.save(update_fields=['payload', 'heartbeat_at'])
    return result


def process_spatial(limit=50):
    from .models import MLCandidate, MLSpatialAssessment, MLPipelineState
    zones = load_zones()
    catalog_hash = fingerprint(zones)
    versions = snapshot_catalog(zones)
    query = MLCandidate.objects.filter(
        Q(context__isnull=True) | ~Q(context__observation_id=F('latest_id')) |
        ~Q(context__catalog_hash=catalog_hash) | ~Q(context__rule_version=LOCATION_RULE_VERSION))
    batch = list(query.select_related('latest').order_by('latest_id')[:limit])
    done = 0
    for candidate in batch:
        obs = candidate.latest
        result = assess_location(obs.snapshot, zones)
        selected = versions.get(result['selected_zone_id'])
        matches = [{'zone_id': key, 'version_id': versions[key].pk, 'sequence': versions[key].sequence}
                   for key in result['matching_zone_ids'] if key in versions]
        evidence = list(result['evidence'])
        source = (obs.snapshot.get('evidence') or {}).get('location')
        evidence.append({'code': 'source.location', 'message': 'Precisión declarada por la fuente; no certificación catastral.',
                         'details': source or {'status': 'not_preserved', 'message': 'Evidencia detallada no conservada.'}})
        with transaction.atomic():
            state = MLPipelineState.objects.select_for_update().get(pk='zone-catalog')
            if state.payload.get('catalog_hash') != catalog_hash:
                continue
            assessment, _ = MLSpatialAssessment.objects.get_or_create(observation=obs,
                catalog_hash=catalog_hash, rule_version=LOCATION_RULE_VERSION,
                defaults={'state': result['status'], 'zone_version': selected,
                          'matching_versions': matches, 'evidence': evidence})
            # Capture can race this calculation; never attach an obsolete result.
            changed = MLCandidate.objects.filter(pk=candidate.pk, latest_id=obs.pk).update(context=assessment)
        done += changed
    return {'spatial_processed': done, 'spatial_pending': query.count(), 'catalog_hash': catalog_hash}


def identity_signature(row):
    # Price, last-seen and wording edits do not change physical identity.
    fields = ('fuente', 'id_origen', 'url', 'tipo_inmueble', 'latitud', 'longitud',
              'precision_ubicacion', 'direccion_texto', 'area_terreno', 'area_construida')
    return fingerprint({**{key: row.get(key) for key in fields}, 'unit': _unit(row)})


@transaction.atomic
def _claim_identity(force):
    from .models import MLPipelineState
    MLPipelineState.objects.get_or_create(key='identity')
    state = MLPipelineState.objects.select_for_update().get(pk='identity')
    payload = dict(state.payload or {})
    now = timezone.now()
    if float(payload.get('lease_until', 0)) > now.timestamp():
        return None
    if not force and state.heartbeat_at and now - state.heartbeat_at < timedelta(seconds=60):
        return None
    token = str(uuid.uuid4())
    payload.update(lease=token, lease_until=now.timestamp() + 600)
    state.payload, state.heartbeat_at = payload, now
    state.save(update_fields=['payload', 'heartbeat_at'])
    return token, payload.get('input_hash')


def _fence_identity(token):
    """Must run inside the same transaction as pair writes."""
    from .models import MLPipelineState
    state = MLPipelineState.objects.select_for_update().get(pk='identity')
    now = timezone.now().timestamp()
    if state.payload.get('lease') != token or state.payload.get('lease_until', 0) <= now:
        raise RuntimeError('La concesión del proceso de identidad venció; se reintentará.')
    state.payload = {**state.payload, 'lease_until': now + 600}
    state.save(update_fields=['payload'])


def process_identity(force=False):
    from .models import MLCandidate, MLIdentityPair, MLPipelineState
    claim = _claim_identity(force)
    if not claim:
        return {'identity_skipped': True}
    token, previous_hash = claim
    completed_hash = None
    changed = 0
    try:
        # Latest ids are a compact signature. Do not refetch thousands of JSONs unchanged.
        ids = list(MLCandidate.objects.order_by('propiedad_id').values_list('propiedad_id', 'latest_id'))
        input_hash = fingerprint([IDENTITY_RULE_VERSION, ids])
        if input_hash == previous_hash and not force:
            completed_hash = input_hash
            return {'identity_unchanged': True}
        observations = {c.propiedad_id: c.latest for c in MLCandidate.objects.select_related('latest').order_by('propiedad_id')}
        # Recompute signature from the actual fetched version set to handle ingestion races.
        input_hash = fingerprint([IDENTITY_RULE_VERSION, [(key, o.pk) for key, o in observations.items()]])
        rows = [{**obs.snapshot, 'id': key} for key, obs in observations.items()]
        proposed = propose_pairs(rows)
        present = set()
        for item in proposed:
            left, right = sorted((item['left_id'], item['right_id']))
            present.add((left, right))
            lo, ro = observations[left], observations[right]
            signatures = identity_signature(lo.snapshot), identity_signature(ro.snapshot)
            with transaction.atomic():
                _fence_identity(token)
                pair, created = MLIdentityPair.objects.select_for_update().get_or_create(left_id=left, right_id=right,
                    defaults={'left_observation': lo, 'right_observation': ro, 'left_signature': signatures[0],
                              'right_signature': signatures[1], 'score': item['score'], 'evidence': item['evidence'],
                              'rule_version': IDENTITY_RULE_VERSION})
                if not created:
                    stale = pair.decision_stale or (pair.status != 'possible' and
                            (pair.left_signature, pair.right_signature) != signatures)
                    values = {'left_observation_id': lo.pk, 'right_observation_id': ro.pk,
                              'left_signature': signatures[0], 'right_signature': signatures[1],
                              'score': item['score'], 'evidence': item['evidence'],
                              'rule_version': IDENTITY_RULE_VERSION, 'active': True, 'decision_stale': stale}
                    if any(getattr(pair, k) != v for k, v in values.items()):
                        for k, v in values.items():
                            setattr(pair, k, v)
                        pair.revision += 1
                        pair.save()
                        changed += 1
                else:
                    changed += 1
        # Preserve decisions even when suggestion rules no longer match. Mark material
        # identity changes stale, retain audit, and do not turn a same decision into a merge.
        for pk in list(MLIdentityPair.objects.values_list('pk', flat=True)):
            with transaction.atomic():
                _fence_identity(token)
                pair = MLIdentityPair.objects.select_for_update().get(pk=pk)
                if (pair.left_id, pair.right_id) in present:
                    continue
                lo, ro = observations.get(pair.left_id), observations.get(pair.right_id)
                if not lo or not ro:
                    continue
                signatures = identity_signature(lo.snapshot), identity_signature(ro.snapshot)
                stale = pair.decision_stale or (pair.status != 'possible' and
                         (pair.left_signature, pair.right_signature) != signatures)
                active = pair.status == 'same' or stale
                values = {'active': active, 'decision_stale': stale, 'left_observation_id': lo.pk,
                          'right_observation_id': ro.pk, 'left_signature': signatures[0], 'right_signature': signatures[1]}
                if any(getattr(pair, k) != v for k, v in values.items()):
                    for k, v in values.items():
                        setattr(pair, k, v)
                    pair.revision += 1
                    pair.save()
                    changed += 1
        completed_hash = input_hash
        logger.info('ml.identity.evaluated records=%s suggestions=%s changed=%s', len(rows), len(proposed), changed)
        return {'identity_records': len(rows), 'identity_suggestions': len(proposed), 'identity_changed': changed}
    finally:
        with transaction.atomic():
            state = MLPipelineState.objects.select_for_update().get(pk='identity')
            if state.payload.get('lease') == token:
                payload = dict(state.payload)
                payload.update(lease='', lease_until=0)
                if completed_hash:
                    payload['input_hash'] = completed_hash
                    state.sweep_finished_at = timezone.now()
                state.payload = payload
                state.save(update_fields=['payload', 'sweep_finished_at'])


@transaction.atomic
def decide_pair(pair_id, expected_revision, decision, reason, actor):
    from .models import MLIdentityPair, MLIdentityDecision, MLCandidate, PropiedadesCompetencia
    if decision not in ('same', 'different', 'possible') or not str(reason or '').strip():
        raise ValueError('Elige una decisión e indica su motivo.')
    if len(str(reason)) > 2000:
        raise ValueError('El motivo no puede superar 2000 caracteres.')
    # Same order as capture: source locks first, then derived state. No deadlocks
    # against ingestion, and a reviewed observation cannot change mid-decision.
    initial = MLIdentityPair.objects.get(pk=pair_id)
    list(PropiedadesCompetencia.objects.select_for_update().filter(pk__in=[initial.left_id, initial.right_id]).order_by('pk'))
    pair = MLIdentityPair.objects.select_for_update().get(pk=pair_id)
    latest = dict(MLCandidate.objects.filter(propiedad_id__in=[pair.left_id, pair.right_id]).values_list('propiedad_id', 'latest_id'))
    if pair.revision != expected_revision or latest != {pair.left_id: pair.left_observation_id, pair.right_id: pair.right_observation_id}:
        raise RuntimeError('Los registros cambiaron. Actualiza antes de decidir.')
    pair.status, pair.decision_stale, pair.revision = decision, False, pair.revision + 1
    pair.save(update_fields=['status', 'decision_stale', 'revision', 'updated_at'])
    MLIdentityDecision.objects.create(pair=pair, decision=decision, reason=str(reason).strip(), actor=str(actor)[:200],
        left_observation_id=pair.left_observation_id, right_observation_id=pair.right_observation_id)
    logger.info('ml.identity.decided pair=%s decision=%s actor=%s', pair.pk, decision, actor)
    return pair
