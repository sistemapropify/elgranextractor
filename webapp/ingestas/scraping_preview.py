"""Queued preview: sample logs without touching properties or lifecycle tables."""
from django.utils import timezone
from .models import ScrapingJob
from scrapi.contracts import ScrapingInterrupted


def run_preview(job, token, stop_event=None):
    from colas.scraping_tasks import _crear_log, _start_portal_heartbeat
    from scrapi.paged_engine import run_paged
    from scrapi.source_config import source_snapshot
    sources = (job.parametros or {}).get('sources') or {}
    try:
        for portal in (job.parametros or {}).get('portales') or []:
            config = sources.get(portal) or source_snapshot(portal)
            def progress(payload):
                if stop_event and stop_event.is_set():
                    from colas.scraping_tasks import _release_for_shutdown
                    _release_for_shutdown(job.pk, token)
                    raise ScrapingInterrupted('Worker detenido; vista previa en cola')
                current = ScrapingJob.objects.get(pk=job.pk)
                if current.execution_token != token or current.estado != 'running':
                    raise ScrapingInterrupted('Vista previa detenida')
                context = {k: v for k, v in payload.items() if k not in ('candidate_batch', 'resume_item_ids')}
                _crear_log(job, payload.get('level', 'info'), payload.get('message', 'Vista previa'),
                    portal=portal, evento=payload.get('event', 'preview.progress'), contexto=context)
                return True
            stop, heartbeat = _start_portal_heartbeat(job.pk, portal, token)
            try:
                if portal == 'facebook_marketplace':
                    from scrapi.facebook_marketplace_scraper import run_scraper
                    rows = run_scraper(search_url=config['source_url'], max_items=60,
                                       discovery_only=True, progress_callback=progress)
                else:
                    rows = run_paged(portal, source_url=config['source_url'], max_paginas=1,
                                     listing_only=True, progress_callback=progress)
                progress({'event': 'preview.result', 'message': f'{portal}: muestra de {len(rows)} anuncios; sin guardar propiedades',
                          'source': config, 'discovery': rows.discovery.as_dict(), 'sample': list(rows[:3])})
                if not rows:
                    raise RuntimeError(f'{portal}: la vista previa no encontró anuncios válidos')
            finally:
                stop.set()
                heartbeat.join(timeout=2)
        ScrapingJob.objects.filter(pk=job.pk, execution_token=token, estado='running').update(
            estado='completed', progreso=100, completado_en=timezone.now(), execution_token=None)
    except Exception as exc:
        _crear_log(job, 'error', str(exc), evento='preview.failed')
        ScrapingJob.objects.filter(pk=job.pk, execution_token=token, estado='running').update(
            estado='error', mensaje_error=str(exc)[:2000], completado_en=timezone.now(), execution_token=None)
