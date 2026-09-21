"""Database mailbox; screenshots and answers never enter scraping logs."""
import re
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from scrapi.contracts import ScrapingInterrupted
from .models import ScrapingJob, ScrapingVerification
from .scraping_store import lock_run


def valid_answer(value):
    return isinstance(value, str) and bool(re.fullmatch(r'-?[0-9]{1,12}', value))


def active_for_job(job):
    if (job.estado != 'running' or not job.execution_token or not job.lease_expires_at
            or job.lease_expires_at <= timezone.now()):
        return ScrapingVerification.objects.none()
    return ScrapingVerification.objects.filter(
        run__job_id=job.pk, execution_token=job.execution_token,
        expires_at__gt=timezone.now(), state__in=['waiting', 'submitted'])


def public_state(job):
    ScrapingVerification.objects.filter(run__job_id=job.pk, expires_at__lte=timezone.now()).exclude(
        state='closed').update(screenshot='', answer='', state='closed')
    item = active_for_job(job).filter(state='waiting').first()
    if item is None:
        return None
    return {'id': str(item.pk), 'expires_at': item.expires_at.isoformat(),
            'screenshot': item.screenshot}


@transaction.atomic
def submit_answer(job_id, challenge_id, answer):
    if not valid_answer(answer):
        raise ValueError('Escribe únicamente el resultado numérico que ves en la imagen.')
    job = ScrapingJob.objects.select_for_update().get(pk=job_id)
    updated = active_for_job(job).filter(pk=challenge_id, state='waiting').update(
        answer=answer, state='submitted')
    if not updated:
        raise ValueError('La verificación venció, ya fue respondida o el trabajo cambió. Actualiza el estado.')


def mailbox(run_id, execution_token):
    def exchange(action, **payload):
        # Cleanup must also work after the job is stopped/replaced.
        if action == 'close':
            ScrapingVerification.objects.filter(run_id=run_id, execution_token=execution_token).update(
                screenshot='', answer='', state='closed')
            return
        with transaction.atomic():
            run = lock_run(run_id, execution_token)
            if run.portal != 'properati':
                raise ValueError('Verificación manual disponible solo para Properati.')
            query = ScrapingVerification.objects.filter(run_id=run_id, execution_token=execution_token)
            if action == 'open':
                ScrapingVerification.objects.filter(run=run).exclude(state='closed').update(
                    screenshot='', answer='', state='closed')
                query.update(screenshot='', answer='', state='closed')
                item = ScrapingVerification.objects.create(
                    run=run, execution_token=execution_token,
                    expires_at=timezone.now() + timedelta(seconds=min(300, payload['seconds'])),
                    screenshot=payload['screenshot'])
                return str(item.pk)
            item = query.select_for_update().get(pk=payload['id'])
            if item.expires_at <= timezone.now():
                raise ScrapingInterrupted('portal.paused: la verificación manual venció; pendientes conservados')
            if item.state == 'submitted':
                answer = item.answer
                item.answer, item.state = '', 'consumed'
                item.save(update_fields=['answer', 'state'])
                return answer
            return None
    return exchange
