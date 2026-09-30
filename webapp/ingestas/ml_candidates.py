"""Durable candidate snapshots, deterministic processing and resumable reconciliation."""
import logging
import time
from datetime import timedelta
from decimal import Decimal
from django.db import connection, transaction
from django.utils import timezone
from .ml_eligibility import FIELDS, RULE_VERSION, digest, evaluate

logger = logging.getLogger(__name__)
_schema_cache = (0, False)


def schema_ready():
    global _schema_cache
    now = time.monotonic()
    if now - _schema_cache[0] < 30:
        return _schema_cache[1]
    from .models import MLObservation, MLCandidate, MLPipelineState
    tables = set(connection.introspection.table_names())
    ok = all(m._meta.db_table in tables for m in (MLObservation, MLCandidate, MLPipelineState))
    _schema_cache = (now, ok)
    return ok


def json_value(value):
    if isinstance(value, Decimal):
        return format(value.normalize(), 'f')
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return value


def input_snapshot(obj, revision=None):
    snap = {k: json_value(getattr(obj, k)) for k in FIELDS}
    raw = obj.datos_crudos if isinstance(obj.datos_crudos, dict) else {}
    age_evidence = raw.get('_age_evidence') or {}
    if obj.antiguedad_anios is None and not age_evidence:
        from scrapi.normalization import construction_age
        inputs = {**raw, 'tipo_inmueble': obj.tipo_inmueble}
        if obj.descripcion:
            inputs['description'] = obj.descripcion
        _, age_evidence = construction_age(inputs, obj.fecha_extraccion)
        age_evidence = age_evidence or {}
    age_confirmed = bool(revision and ('antiguedad_anios' in revision.campos_protegidos or
                                     (revision.correcta and obj.antiguedad_anios is not None)))
    snap.update(record_id=obj.pk, manual_excluded=bool(revision and revision.excluida),
                manual_reason=revision.motivo if revision else '',
                fecha_extraccion=json_value(obj.fecha_extraccion),
                normalizer_issues=raw.get('_quality_issues') or [],
                age_conflict=age_evidence.get('reason') if isinstance(age_evidence, dict) and not age_confirmed else None,
                evidence={'age': age_evidence, 'normalizer': raw.get('_normalizer_version')},
                first_seen=json_value(obj.primera_vez_vista), last_seen=json_value(obj.ultima_vez_vista))
    return snap


@transaction.atomic
def capture(property_id, origin='save'):
    from .models import (PropiedadesCompetencia, RevisionPropiedadScraping,
                         MLObservation, MLCandidate)
    # One stable row lock orders captures even when no candidate exists yet.
    obj = PropiedadesCompetencia.objects.select_for_update().get(pk=property_id)
    revision = RevisionPropiedadScraping.objects.filter(propiedad_id=property_id).first()
    snap = input_snapshot(obj, revision)
    fingerprint = digest(snap)
    state = MLCandidate.objects.select_related('latest').filter(propiedad_id=property_id).first()
    previous = state.latest if state else None
    if previous and previous.content_hash == fingerprint and previous.rule_version == RULE_VERSION:
        return previous, False
    changes = {k: {'before': previous.snapshot.get(k), 'after': snap.get(k)}
               for k in FIELDS + ('manual_excluded', 'manual_reason', 'age_conflict', 'normalizer_issues')
               if previous and previous.snapshot.get(k) != snap.get(k)}
    run = obj.ultima_ejecucion_vista if obj.ultima_ejecucion_vista_id else None
    observation = MLObservation.objects.create(propiedad=obj, sequence=previous.sequence + 1 if previous else 1,
        content_hash=fingerprint, snapshot=snap, changes=changes, origin=origin[:40],
        job_id=run.job_id if run else None, rule_version=RULE_VERSION)
    MLCandidate.objects.update_or_create(propiedad=obj, defaults={'latest': observation,
                                         'status': 'pending', 'evaluated_at': None})
    logger.info('ml.candidate.queued record=%s version=%s job=%s', property_id, observation.sequence, observation.job_id)
    return observation, True


def safe_capture(property_id, origin='save'):
    # A rolling deployment must not prevent scraping if the new schema is late.
    # Failed captures remain visible in logs; the worker's full reconciliation repairs them.
    try:
        with transaction.atomic():
            if schema_ready():
                return capture(property_id, origin)
        logger.warning('ml.schema.pending record=%s; reconcile after migration', property_id)
    except Exception:
        logger.exception('ml.capture.failed record=%s; scheduled reconciliation will retry', property_id)


@transaction.atomic
def repair_age(property_id):
    from .models import PropiedadesCompetencia, RevisionPropiedadScraping, CambioPropiedadScraping
    from scrapi.normalization import construction_age
    obj = PropiedadesCompetencia.objects.select_for_update().get(pk=property_id)
    if obj.antiguedad_anios is not None:
        return False
    review = RevisionPropiedadScraping.objects.filter(propiedad_id=property_id).first()
    if review and (review.correcta or 'antiguedad_anios' in review.campos_protegidos):
        return False
    raw = dict(obj.datos_crudos or {})
    # Include stored prose when the portal's archived payload omitted it.
    evidence_input = dict(raw)
    evidence_input['tipo_inmueble'] = obj.tipo_inmueble
    if obj.descripcion:
        evidence_input['description'] = obj.descripcion
    age, evidence = construction_age(evidence_input, obj.fecha_extraccion)
    if age is None or (evidence and evidence.get('reason')):
        return False
    obj.antiguedad_anios = age
    raw['_age_evidence'] = evidence
    obj.datos_crudos = raw
    # Do not reset publication lifecycle or extraction dates during a repair.
    obj.save(update_fields=['antiguedad_anios', 'datos_crudos'])
    CambioPropiedadScraping.objects.create(propiedad=obj, usuario='system:ml-age-v1', cambios={
        'antiguedad_anios': {'antes': None, 'despues': age, 'evidencia': evidence}})
    logger.info('ml.repair.age record=%s age=%s source=%s', property_id, age, evidence.get('source'))
    return True


def process_pending(limit=50):
    from .models import MLObservation, MLCandidate
    ids = list(MLObservation.objects.filter(status='pending').order_by('id').values_list('id', flat=True)[:limit])
    counts = {'processed': 0, 'repaired': 0, 'errors': 0}
    for pk in ids:
        try:
            identity = MLObservation.objects.only('propiedad_id').get(pk=pk)
            counts['repaired'] += int(repair_age(identity.propiedad_id))
            with transaction.atomic():
                obs = MLObservation.objects.select_for_update().get(pk=pk)
                if obs.status != 'pending':
                    continue
                result = evaluate(obs.snapshot)
                obs.status, obs.reasons, obs.notes = result['status'], result['reasons'], result['notes']
                obs.evaluated_at = timezone.now()
                obs.attempts += 1
                obs.save(update_fields=['status', 'reasons', 'notes', 'evaluated_at', 'attempts'])
                # An old version must never overwrite the current admission state.
                MLCandidate.objects.filter(propiedad_id=obs.propiedad_id, latest_id=obs.pk).update(
                    status=obs.status, evaluated_at=obs.evaluated_at)
                counts['processed'] += 1
                logger.info('ml.candidate.evaluated record=%s version=%s status=%s job=%s',
                            obs.propiedad_id, obs.sequence, obs.status, obs.job_id)
        except Exception:
            logger.exception('ml.evaluation.failed observation=%s', pk)
            with transaction.atomic():
                obs = MLObservation.objects.select_for_update().get(pk=pk)
                if obs.status == 'pending':
                    obs.attempts += 1
                    if obs.attempts >= 3:
                        obs.status = 'error'
                        obs.reasons = [{'code': 'evaluation.failed', 'message': 'No se pudo evaluar; reintentar desde la tarea de mantenimiento.', 'field': '', 'severity': 'review'}]
                    obs.save(update_fields=['attempts', 'status', 'reasons'])
                    MLCandidate.objects.filter(latest_id=pk).update(status=obs.status)
            counts['errors'] += 1
    return counts


@transaction.atomic
def reconcile_chunk(limit=50, force=False):
    from .models import PropiedadesCompetencia, MLPipelineState
    MLPipelineState.objects.get_or_create(key='candidates')
    state = MLPipelineState.objects.select_for_update().get(key='candidates')
    now = timezone.now()
    state.heartbeat_at = now
    if not force and state.cursor == 0 and state.sweep_finished_at and now - state.sweep_finished_at < timedelta(hours=24):
        state.save(update_fields=['heartbeat_at'])
        return {'scanned': 0, 'queued': 0, 'complete': True}
    ids = list(PropiedadesCompetencia.objects.filter(pk__gt=state.cursor).order_by('pk').values_list('pk', flat=True)[:limit])
    queued = 0
    for pk in ids:
        _, changed = capture(pk, origin='reconciliation')
        queued += int(changed)
    state.cursor = ids[-1] if ids else 0
    if not ids:
        state.sweep_finished_at = now
    state.save()
    return {'scanned': len(ids), 'queued': queued, 'complete': not ids}
