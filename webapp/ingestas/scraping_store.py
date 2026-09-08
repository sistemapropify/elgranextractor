"""Durable checkpoints, with the job owner fenced inside each transaction."""
from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from .models import EjecucionPortal, ScrapingCandidate, ScrapingJob
from scrapi.contracts import ScrapingInterrupted


def lock_run(run_id, execution_token=None):
    identity = EjecucionPortal.objects.only('job_id').get(pk=run_id)
    if identity.job_id:
        job = ScrapingJob.objects.select_for_update().get(pk=identity.job_id)
        if (execution_token is None or str(job.execution_token) != str(execution_token)
                or job.estado != 'running'
                or (job.lease_expires_at and job.lease_expires_at <= timezone.now())):
            raise ScrapingInterrupted('execution.owner_lost: el ejecutor ya no puede escribir')
    return EjecucionPortal.objects.select_for_update().get(pk=run_id)


@transaction.atomic
def record_progress(run_id, payload, execution_token):
    run = lock_run(run_id, execution_token)
    for candidate in payload.get('candidate_batch') or []:
        source_id = str(candidate.get('id') or '').strip()
        if not source_id or len(source_id) > 100:
            raise ValueError('listing.missing_id: candidato sin ID válido')
        ScrapingCandidate.objects.get_or_create(run=run, source_id=source_id, defaults={
            'raw': candidate.get('raw') or {'id': source_id, 'url': candidate.get('url')},
            'page': max(1, int(candidate.get('page') or 1)),
        })
    error = payload.get('candidate_error')
    if error:
        ScrapingCandidate.objects.filter(run=run, source_id=str(error['id'])).update(
            status='error', error=str(error.get('error') or '')[:4000])
    excluded = payload.get('candidate_excluded')
    if excluded:
        ScrapingCandidate.objects.filter(run=run, source_id=str(excluded)).update(status='excluded', error='')
    if payload.get('discovery') is not None:
        run.discovery = dict(payload['discovery'])
        run.save(update_fields=['discovery'])
    checkpoint = payload.get('checkpoint_page')
    if (checkpoint is not None and run.portal != 'facebook_marketplace'
            and run.candidates.filter(page__lte=checkpoint, status__in=['pending', 'error']).exists()):
        raise RuntimeError('checkpoint.pending: quedan fichas sin confirmar antes de esta página')


def resume_state(run):
    rows = list(run.candidates.order_by('page', 'id').values('source_id', 'raw', 'page', 'status'))
    return {
        'known_ids': [r['source_id'] for r in rows],
        'saved_ids': [r['source_id'] for r in rows if r['status'] in ('saved', 'excluded')],
        'pending': [{'id': r['source_id'], 'raw': r['raw'], 'page': r['page']}
                    for r in rows if r['status'] in ('pending', 'error')],
        'candidates': [{'id': r['source_id'], **r['raw']} for r in rows],
        'discovery': dict(run.discovery or {}),
    }


def run_counters(run_id):
    query = ScrapingCandidate.objects.filter(run_id=run_id)
    outcomes = {r['save_outcome']: r['n'] for r in query.exclude(save_outcome='').values('save_outcome').annotate(n=Count('id'))}
    return {'total': sum(outcomes.values()), 'nuevas': outcomes.get('created', 0),
            'actualizadas': outcomes.get('updated', 0), 'errores': query.filter(status='error').count(),
            'discovered': query.count(), 'pending': query.filter(status__in=['pending', 'error']).count()}
