"""Train and monitor offer-price models from immutable dataset versions."""
import hashlib
import json
import logging
import time
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .ml_pricing import TYPES, VERSION, evaluate, features, fit_knn, fit_ridge, metrics, predict, split

logger = logging.getLogger(__name__)


def _rows(dataset, kind):
    from .models import MLDatasetEntry
    entries = MLDatasetEntry.objects.filter(dataset=dataset, included=True).select_related(
        'observation').order_by('candidate_id')
    rows = []
    for entry in entries.iterator(chunk_size=200):
        item = entry.features
        if item.get('tipo_inmueble') != kind or item.get('tipo_operacion') != 'Venta':
            continue
        price = float(entry.target_price_usd or 0)
        if price <= 0:
            continue
        rows.append({'id': entry.candidate_id, 'entry_id': entry.pk,
                     'observation_id': entry.observation_id,
                     'group': entry.identity_group_hash or 'record:' + str(entry.candidate_id),
                     'features': item, 'price': price,
                     'seen': entry.observation.snapshot.get('first_seen') or
                             entry.observation.created_at.isoformat()})
    return rows


def _artifact_hash(artifact):
    return hashlib.sha256(json.dumps(artifact, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False).encode('utf-8')).hexdigest()


def _candidate(model, parts):
    temporal_cases, temporal = evaluate(model, parts['temporal'], 'temporal')
    spatial_cases, spatial = evaluate(model, parts['spatial'], 'spatial')
    available = [result['mape_pct'] for result in (temporal, spatial) if result['available']]
    return {'temporal': temporal, 'spatial': spatial,
            'score': round(sum(available) / len(available), 2) if available else None,
            'cases': (temporal_cases + spatial_cases)[:250]}


def train(run_id):
    from .models import MLTrainingRun
    started = time.monotonic()
    run = MLTrainingRun.objects.select_related('dataset').get(pk=run_id)
    if run.status != 'running':
        return {'skipped': 'not_running'}
    try:
        rows = _rows(run.dataset, run.property_type)
        if len(rows) < 20:
            raise ValueError('Se requieren 20 ofertas válidas del mismo tipo para el primer experimento.')
        parts = split(rows)
        if len(parts['train']) < 12:
            raise ValueError('Después de reservar inmuebles para evaluación quedan menos de 12 para entrenar.')
        alternatives = {}
        for name, fit in (('local_knn', fit_knn), ('hedonic_ridge', fit_ridge)):
            try:
                alternatives[name] = _candidate(fit(parts['train'], run.property_type), parts)
            except (ValueError, OverflowError, ZeroDivisionError) as error:
                alternatives[name] = {'error': str(error), 'score': None}
        ranked = [(value['score'], name) for name, value in alternatives.items()
                  if value.get('score') is not None]
        chosen = min(ranked)[1] if ranked else 'local_knn'
        final = (fit_knn if chosen == 'local_knn' else fit_ridge)(rows, run.property_type)
        fingerprint = _artifact_hash(final)
        selected = alternatives[chosen]
        run.algorithm = chosen
        run.code_version = VERSION
        run.configuration = {'artifact': final, 'split': {key: len(value) for key, value in parts.items()},
                             'trained_groups': sorted({row['group'] for row in rows}),
                             'recipe': 'precios de oferta de venta; identidad, tiempo y zona separados'}
        run.metrics = {'alternatives': alternatives, 'selected': chosen,
                       'temporal': selected.get('temporal', {'available': False}),
                       'spatial': selected.get('spatial', {'available': False}),
                       'duration_seconds': round(time.monotonic() - started, 2),
                       'target': 'precio de oferta USD', 'sample': len(rows),
                       'reliability': 'evaluado' if ranked and
                           selected.get('temporal', {}).get('count', 0) >= 5 and
                           selected.get('spatial', {}).get('count', 0) >= 5 else 'exploratorio'}
        run.artifact_sha256 = fingerprint
        run.artifact_uri = 'database:ml_training_run:%d:configuration.artifact' % run.pk
        run.eligible_count = len(rows)
        run.status = 'completed'
        run.completed_at = timezone.now()
        run.save(update_fields=['algorithm', 'code_version', 'configuration', 'metrics', 'artifact_sha256',
                                'artifact_uri', 'eligible_count', 'status', 'completed_at'])
        logger.info('ml.training.completed run=%s dataset=%s type=%s n=%s selected=%s reliability=%s',
                    run.pk, run.dataset_id, run.property_type, len(rows), chosen, run.metrics['reliability'])
        return {'run_id': run.pk, 'status': run.status, 'selected': chosen, 'sample': len(rows)}
    except Exception as error:
        logger.exception('ml.training.failed run=%s dataset=%s', run.pk, run.dataset_id)
        run.status = 'failed'
        run.error = str(error)[:2000]
        run.completed_at = timezone.now()
        run.save(update_fields=['status', 'error', 'completed_at'])
        return {'run_id': run.pk, 'status': 'failed', 'error': run.error}


def process_queue():
    from .models import MLTrainingRun
    now = timezone.now()
    MLTrainingRun.objects.filter(status='running', started_at__lt=now-timedelta(hours=1)).update(
        status='failed', error='Entrenamiento interrumpido; vuelve a solicitarlo.', completed_at=now)
    with transaction.atomic():
        queued = MLTrainingRun.objects.select_for_update().filter(status='queued').order_by('pk').first()
        if not queued:
            return {'training_queue': 'empty'}
        queued.status = 'running'
        queued.started_at = now
        queued.save(update_fields=['status', 'started_at'])
        run_id = queued.pk
    return train(run_id)


def active_run(kind):
    from .models import MLPipelineState, MLTrainingRun
    state = MLPipelineState.objects.filter(pk='model-active:' + kind).first()
    run_id = (state.payload or {}).get('run_id') if state else None
    run = MLTrainingRun.objects.filter(pk=run_id, status='completed').first() if run_id else None
    if not run:
        return None
    artifact = run.configuration.get('artifact')
    if not isinstance(artifact, dict) or _artifact_hash(artifact) != run.artifact_sha256:
        logger.error('ml.artifact.invalid run=%s', run.pk)
        return None
    return run


def publish(run, actor, reason):
    from .models import MLPipelineState
    if run.status != 'completed' or not run.artifact_sha256:
        raise ValueError('Solo puede publicarse un entrenamiento completado.')
    if _artifact_hash(run.configuration.get('artifact')) != run.artifact_sha256:
        raise ValueError('El artefacto no coincide con su huella guardada.')
    key = 'model-active:' + run.property_type
    with transaction.atomic():
        MLPipelineState.objects.get_or_create(key=key)
        state = MLPipelineState.objects.select_for_update().get(pk=key)
        previous = (state.payload or {}).get('run_id')
        history = list((state.payload or {}).get('history') or [])[-49:]
        history.append({'from': previous, 'to': run.pk, 'actor': actor,
                        'reason': reason[:500], 'at': timezone.now().isoformat()})
        state.payload = {'run_id': run.pk, 'history': history}
        state.heartbeat_at = timezone.now()
        state.save(update_fields=['payload', 'heartbeat_at'])
    logger.warning('ml.model.published type=%s run=%s previous=%s actor=%s',
                   run.property_type, run.pk, previous, actor)
    return previous


def monitor_dataset(dataset):
    from .models import MLDatasetSnapshot, MLPipelineState
    previous = MLDatasetSnapshot.objects.filter(pk__lt=dataset.pk).order_by('-pk').first()
    previous_versions = {}
    if previous:
        previous_versions = dict(previous.entries.filter(included=True).values_list('candidate_id', 'observation_id'))
    output = []
    for kind in TYPES:
        run = active_run(kind)
        if not run:
            continue
        key = 'model-monitor:' + kind
        MLPipelineState.objects.get_or_create(key=key)
        with transaction.atomic():
            state = MLPipelineState.objects.select_for_update().get(pk=key)
            if (state.payload or {}).get('latest_dataset_id') == dataset.pk and (state.payload or {}).get('run_id') == run.pk:
                continue
            trained = set(run.configuration.get('trained_groups') or [])
            rows = [row for row in _rows(dataset, kind)
                    if previous_versions.get(row['id']) != row['observation_id'] and row['group'] not in trained]
            cases, result = evaluate(run.configuration['artifact'], rows, 'incoming')
            reference = run.metrics.get('temporal') or {}
            baseline = reference.get('mape_pct') if reference.get('available') else None
            if result['count'] < 10:
                light, why = 'gris', 'Muestra nueva insuficiente para concluir mejora o deterioro.'
            elif baseline is None:
                light, why = 'amarillo', 'Sin prueba temporal previa comparable.'
            elif result['mape_pct'] > max(baseline * 1.3, baseline + 5):
                light, why = 'rojo', 'Error frente a ofertas nuevas superior al nivel de referencia.'
            else:
                light, why = 'verde', 'Error frente a ofertas nuevas dentro del margen de referencia.'
            history = list((state.payload or {}).get('history') or [])[-29:]
            history.append({'dataset_id': dataset.pk, 'run_id': run.pk, 'at': timezone.now().isoformat(),
                            'new_count': len(rows), 'metrics': result, 'light': light, 'reason': why,
                            'cases': cases[:100]})
            state.payload = {'run_id': run.pk, 'latest_dataset_id': dataset.pk, 'history': history}
            state.heartbeat_at = timezone.now()
            state.save(update_fields=['payload', 'heartbeat_at'])
            output.append({'type': kind, 'run_id': run.pk, 'dataset_id': dataset.pk,
                           'new': len(rows), 'light': light})
            logger.info('ml.monitor.updated type=%s run=%s dataset=%s new=%s light=%s',
                        kind, run.pk, dataset.pk, len(rows), light)
    return output
