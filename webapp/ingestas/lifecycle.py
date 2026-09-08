"""Coverage and absences scoped to an immutable search configuration."""
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from .models import EjecucionPortal, PropiedadesCompetencia, PublicacionFuente, ScrapingJob
from scrapi.source_config import source_snapshot


def _min_coverage():
    return min(max(float(getattr(settings, 'SCRAPING_LIFECYCLE_MIN_COVERAGE', 0.65)), 0), 1)


@transaction.atomic
def start_or_resume_portal_run(job, portal):
    locked = ScrapingJob.objects.select_for_update().get(pk=job.pk)
    from scrapi.contracts import ScrapingInterrupted
    if (locked.estado != 'running' or locked.execution_token != job.execution_token
            or (locked.lease_expires_at and locked.lease_expires_at <= timezone.now())):
        raise ScrapingInterrupted('execution.owner_lost: no se puede iniciar otro portal')
    params = dict(locked.parametros or {})
    configs = dict(params.get('sources') or {})
    # Snapshot once, including jobs created through CLI/watchdog.
    config = configs.get(portal) or source_snapshot(portal, (params.get('urls') or {}).get(portal))
    configs[portal] = config
    params['sources'] = configs
    tokens = dict(params.get('lifecycle_runs') or {})
    run = EjecucionPortal.objects.filter(job=locked, token=tokens.get(portal), portal=portal).first() if tokens.get(portal) else None
    if run and (run.estado == 'completed' or run.source_key != config['source_key']):
        run = None
    if run is None:
        run = EjecucionPortal.objects.create(job=locked, portal=portal,
            source_key=config['source_key'], source_config=config)
        tokens[portal] = str(run.token)
    else:
        run.estado = 'running'
        run.es_confiable = run.es_linea_base = False
        run.completado_en = None
        run.motivo_no_confiable = None
        run.save(update_fields=['estado', 'es_confiable', 'es_linea_base', 'completado_en', 'motivo_no_confiable'])
    params['lifecycle_runs'] = tokens
    locked.parametros = params
    locked.save(update_fields=['parametros'])
    job.parametros = params
    return run


@transaction.atomic
def fail_portal_run(run, reason, status='error', execution_token=None):
    if run:
        if run.job_id:
            from .scraping_store import lock_run
            from scrapi.contracts import ScrapingInterrupted
            try:
                lock_run(run.pk, execution_token)
            except ScrapingInterrupted:
                return
        EjecucionPortal.objects.filter(pk=run.pk).update(
            estado=status if status in {'error', 'incomplete'} else 'error',
            es_confiable=False, es_linea_base=False, completado_en=timezone.now(),
            motivo_no_confiable=str(reason)[:4000])


@transaction.atomic
def finalize_portal_run(run, execution_token=None):
    from .scraping_store import lock_run
    run = lock_run(run.pk, execution_token)
    if run.estado == 'completed' and run.es_confiable:
        return {'reliable': True, 'baseline': run.es_linea_base, 'seen': run.propiedades_vistas,
                'possible': run.posibles_retiradas, 'retired': run.retiros_confirmados, 'reason': ''}
    now = timezone.now()
    seen = PublicacionFuente.objects.filter(source_key=run.source_key, last_run=run).count()
    previous = EjecucionPortal.objects.filter(portal=run.portal, source_key=run.source_key,
        estado='completed', es_confiable=True).exclude(pk=run.pk).order_by('-completado_en', '-pk').first()
    discovery = run.discovery or {}
    reason = ''
    if not run.source_key:
        reason = 'La ejecución anterior no tiene identidad de búsqueda; requiere nueva línea base.'
    elif discovery.get('complete') is not True:
        reason = f'Cobertura no demostrada: {discovery.get("stop_reason", "unknown")}.'
    elif discovery.get('details_failed') or run.candidates.filter(status__in=['pending', 'error']).exists():
        reason = 'Quedan anuncios pendientes o con errores; no se evaluaron ausencias.'
    elif run.portal == 'facebook_marketplace':
        reason = 'La ausencia en el feed de Marketplace no certifica retiro de una publicación.'
    elif not seen:
        reason = 'La ejecución no registró propiedades; no se evaluaron ausencias.'
    elif previous and previous.propiedades_vistas and seen / previous.propiedades_vistas < _min_coverage():
        reason = f'Cobertura insuficiente: {seen}/{previous.propiedades_vistas}; mínimo {_min_coverage():.1%}.'
    possible = retired = 0
    baseline = not reason and previous is None
    if not reason and not baseline:
        threshold = max(2, int(getattr(settings, 'SCRAPING_LIFECYCLE_MISSES_TO_RETIRE', 2)))
        missing = PublicacionFuente.objects.select_for_update().filter(
            source_key=run.source_key, state__in=['activa', 'posible_retirada']).exclude(last_run=run)
        for membership in missing:
            membership.misses += 1
            membership.first_missing_at = membership.first_missing_at or now
            membership.state = 'retirada' if membership.misses >= threshold else 'posible_retirada'
            if membership.state == 'retirada':
                membership.retired_at = now
            membership.save()
            # An observation in another search takes precedence over an absence here.
            other_active = PublicacionFuente.objects.filter(propiedad=membership.propiedad,
                state='activa').exclude(pk=membership.pk).exists()
            if other_active:
                continue
            all_retired = not PublicacionFuente.objects.filter(propiedad=membership.propiedad).exclude(state='retirada').exists()
            global_state = 'retirada' if all_retired else 'posible_retirada'
            PropiedadesCompetencia.objects.filter(pk=membership.propiedad_id).update(
                estado_publicacion=global_state, ausencias_consecutivas=membership.misses,
                fecha_primera_ausencia=membership.first_missing_at,
                fecha_retiro_confirmado=now if all_retired else None)
            retired += int(all_retired)
            possible += int(not all_retired)
    run.estado = 'incomplete' if reason else 'completed'
    run.es_confiable, run.es_linea_base = not reason, baseline
    run.propiedades_vistas, run.posibles_retiradas, run.retiros_confirmados = seen, possible, retired
    run.motivo_no_confiable, run.completado_en = reason or None, now
    run.save()
    return {'reliable': not reason, 'baseline': baseline, 'seen': seen,
            'possible': possible, 'retired': retired, 'reason': reason}
