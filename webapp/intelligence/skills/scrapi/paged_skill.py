"""Shared persistence/result contract for the four paginated adapters."""
import inspect
import logging
import traceback
from intelligence.skills.base import SkillResult
from scrapi.contracts import outcome
from scrapi.source_config import requested_url

logger = logging.getLogger(__name__)


def execute_paged_skill(skill, portal, runner, saver, params, context=None):
    context = context or {}
    counters = {'total': 0, 'nuevas': 0, 'actualizadas': 0, 'errores': 0}
    run_id = context.get('lifecycle_run_id')
    progress = context.get('progress_callback')

    def save(rows):
        result = saver(rows, fuente=portal, lifecycle_run_id=run_id,
                       execution_token=context.get('execution_token'))
        for key in counters:
            counters[key] = int(result.get(key, 0)) if run_id else counters[key] + int(result.get(key, 0))
        return counters.copy()

    try:
        runner_kwargs = dict(
            source_url=requested_url(portal, params),
            start_page=int(params.get('start_page') or 1),
            progress_callback=progress,
            batch_callback=save,
            resume_state=params.get('resume_state'),
        )
        # El modo "solo listado" solo se propaga a runners que lo soporten;
        # el resto de portales conserva su comportamiento actual.
        if 'listing_only' in inspect.signature(runner).parameters:
            runner_kwargs['listing_only'] = bool(
                params.get('solo_listado') or params.get('listing_only')
            )
        rows = runner(int(params.get('max_paginas') or 0), **runner_kwargs)
        discovery = outcome(rows)
        if run_id:
            from ingestas.scraping_store import run_counters
            counters.update(run_counters(run_id))
        data = {'portal': portal, **counters, 'discovery': discovery,
                'resume_complete': discovery['complete'] and not counters.get('pending', 0)}
        if not rows and not data['resume_complete'] and not counters['total']:
            return SkillResult(False, data=data, message=f'{portal}: sin resultados; {discovery["stop_reason"]}', skill_name=skill.name)
        return SkillResult.ok(data=data, message=(f'{portal}: {counters["total"]} guardadas; '
            f'{discovery["stop_reason"]}; cobertura {"completa" if discovery["complete"] else "incompleta"}'), skill_name=skill.name)
    except Exception as exc:
        logger.exception('[%s] scraping.failed', portal)
        if progress:
            try:
                progress({'event': 'scraping.failed', 'level': 'error', 'message': str(exc),
                          'error_type': type(exc).__name__, 'traceback': traceback.format_exc()})
            except Exception:
                logger.exception('[%s] No se pudo persistir el evento de fallo', portal)
        return SkillResult(False, data={'portal': portal, **counters,
            'discovery': {'complete': False, 'stop_reason': 'failed'}},
            message=f'{portal}: {exc}', skill_name=skill.name)
