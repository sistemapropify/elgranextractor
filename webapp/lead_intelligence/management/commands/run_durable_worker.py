import threading
import logging
from datetime import timedelta

from django.core.management import BaseCommand, call_command
from django.db import close_old_connections
from django.utils import timezone

from lead_intelligence.durable_jobs import claim_next_job, finish_job, owned_job
from lead_intelligence.models import DurableJob

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Ejecuta trabajos persistidos; recupera leases vencidos tras reinicios."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")
        parser.add_argument("--poll-seconds", type=int, default=5)

    def _heartbeat(self, job, stop, lease_seconds=180):
        close_old_connections()
        try:
            while not stop.wait(30):
                now = timezone.now()
                updated = owned_job(job).update(
                    heartbeat_at=now, lease_until=now + timedelta(seconds=lease_seconds)
                )
                if not updated:
                    if job.kind == DurableJob.Kind.LEAD_ANALYSIS:
                        from lead_intelligence.management.commands.analyze_lead_conversations import request_cancel
                        request_cancel()
                    return
        finally:
            close_old_connections()

    def _execute(self, job):
        payload = job.payload or {}
        if job.kind == DurableJob.Kind.SCRAPING:
            from colas.scraping_tasks import scraping_task_run
            return scraping_task_run(int(payload["scraping_job_id"]))
        if job.kind == DurableJob.Kind.LEAD_ANALYSIS:
            from lead_intelligence.management.commands.analyze_lead_conversations import reset_cancel
            reset_cancel()
            kwargs = {"workers": int(payload.get("workers", 1)), "fail_on_error": True}
            if payload.get("date_from") and payload.get("date_to"):
                kwargs.update(
                    date_from=payload["date_from"],
                    date_to=payload["date_to"],
                    force=bool(payload.get("force")) and job.attempts == 1,
                )
            else:
                kwargs.update(
                    stages=payload.get("stages", "entered"),
                    lookback_hours=int(payload.get("lookback_hours", 24)),
                )
            return call_command("analyze_lead_conversations", **kwargs)
        if job.kind == DurableJob.Kind.SHADOW_RECONCILE:
            if payload.get("client_message"):
                from response_intelligence.shadow import maybe_generate_shadow_draft, shadow_mode_enabled
                if not shadow_mode_enabled():
                    logger.info("durable.job.skipped id=%s reason=shadow_disabled", job.pk)
                    return None
                draft = maybe_generate_shadow_draft(**payload["client_message"])
                if draft is None:
                    raise RuntimeError("Shadow generation did not persist a result")
                return draft
            return call_command(
                "generate_draft_responses",
                mode="shadow_live",
                date_from=payload["date_from"],
                date_to=payload["date_to"],
                all_messages=True,
                workers=int(payload.get("workers", 1)),
            )
        raise ValueError(f"Tipo de trabajo no soportado: {job.kind}")

    def handle(self, *args, **options):
        import time
        while True:
            close_old_connections()
            job = claim_next_job()
            if not job:
                if options["once"]:
                    return
                time.sleep(max(1, options["poll_seconds"]))
                continue
            stop = threading.Event()
            beat = threading.Thread(target=self._heartbeat, args=(job, stop), daemon=True)
            beat.start()
            logger.info("durable.job.started id=%s kind=%s attempt=%s", job.pk, job.kind, job.attempts)
            try:
                self._execute(job)
            except Exception as exc:
                updated = finish_job(job, error=exc)
                logger.warning("durable.job.error id=%s attempt=%s recorded=%s error_type=%s", job.pk, job.attempts, bool(updated), type(exc).__name__)
            else:
                updated = finish_job(job)
                logger.info("durable.job.finished id=%s attempt=%s recorded=%s", job.pk, job.attempts, bool(updated))
            finally:
                stop.set()
                beat.join(timeout=2)
                close_old_connections()
