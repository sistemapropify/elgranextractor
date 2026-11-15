"""Cola durable sobre Azure SQL; no depende de Celery memory://."""

import os
import logging
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

from .models import DurableJob

logger = logging.getLogger(__name__)


def enqueue_durable_job(
    kind,
    payload,
    dedupe_key,
    max_attempts=3,
    available_at=None,
):
    job, created = DurableJob.objects.using("default").get_or_create(
        dedupe_key=dedupe_key,
        defaults={
            "kind": kind,
            "payload": payload,
            "max_attempts": max_attempts,
            "available_at": available_at or timezone.now(),
        },
    )
    return job, created


def enqueue_lead_analysis_burst(
    lead_id,
    payload,
    *,
    history_hash,
    delay_seconds=15,
):
    """Coalesce consecutive CRM events for the same lead.

    Each event extends the quiet window. The worker analyzes the latest CRM
    snapshot once, instead of paying for every message written in a burst.
    """
    lead_id = int(lead_id)
    delay_seconds = max(1, min(120, int(delay_seconds)))
    dedupe_key = f"lead-analysis:live:{lead_id}"
    available_at = timezone.now() + timedelta(seconds=delay_seconds)
    with transaction.atomic(using="default"):
        job = (
            DurableJob.objects.using("default")
            .select_for_update()
            .filter(dedupe_key=dedupe_key)
            .first()
        )
        if job is None:
            job = DurableJob.objects.using("default").create(
                kind=DurableJob.Kind.LEAD_ANALYSIS,
                dedupe_key=dedupe_key,
                payload=payload,
                max_attempts=3,
                available_at=available_at,
            )
            return job, True
        if job.status == DurableJob.Status.RUNNING:
            return enqueue_durable_job(
                DurableJob.Kind.LEAD_ANALYSIS,
                payload,
                f"lead-analysis:live:{lead_id}:{history_hash}",
                max_attempts=3,
                available_at=available_at,
            )

        job.status = DurableJob.Status.PENDING
        job.payload = payload
        job.attempts = 0
        job.max_attempts = 3
        job.available_at = available_at
        job.lease_until = None
        job.heartbeat_at = None
        job.started_at = None
        job.completed_at = None
        job.error_summary = ""
        job.save(
            using="default",
            update_fields=[
                "status",
                "payload",
                "attempts",
                "max_attempts",
                "available_at",
                "lease_until",
                "heartbeat_at",
                "started_at",
                "completed_at",
                "error_summary",
            ],
        )
        return job, True


def claim_next_job(lease_seconds=180):
    now = timezone.now()
    with transaction.atomic(using="default"):
        DurableJob.objects.using("default").filter(
            status="running", lease_until__lt=now,
            attempts__gte=models.F("max_attempts"),
        ).update(status="failed", completed_at=now, lease_until=None,
                 error_summary="Worker lease expired after the final attempt.")
        job = (
            DurableJob.objects.using("default")
            .select_for_update()
            .filter(available_at__lte=now)
            .filter(attempts__lt=models.F("max_attempts"))
            .filter(Q(status="pending") | Q(status="running", lease_until__lt=now))
            .order_by("created_at", "id")
            .first()
        )
        if not job:
            return None
        job.status = DurableJob.Status.RUNNING
        job.attempts += 1
        job.started_at = job.started_at or now
        job.heartbeat_at = now
        job.lease_until = now + timedelta(seconds=lease_seconds)
        job.error_summary = ""
        job.save(using="default", update_fields=["status", "attempts", "started_at", "heartbeat_at", "lease_until", "error_summary"])
        return job


def owned_job(job):
    """The claim attempt fences stale workers after lease recovery."""
    return DurableJob.objects.using("default").filter(
        pk=job.pk, status=DurableJob.Status.RUNNING,
        attempts=job.attempts, lease_until__gt=timezone.now(),
    )


def finish_job(job, error=None):
    now = timezone.now()
    if error is None:
        return owned_job(job).update(status=DurableJob.Status.COMPLETED,
            completed_at=now, heartbeat_at=now, lease_until=None)
    from scrapi.telemetry import sanitize
    retry = job.attempts < job.max_attempts
    return owned_job(job).update(
        status=DurableJob.Status.PENDING if retry else DurableJob.Status.FAILED,
        completed_at=None if retry else now, lease_until=None,
        error_summary=sanitize(f"{type(error).__name__}: {error}")[:2000],
    )


def wake_durable_worker(delay_seconds=0):
    """Despierta un proceso separado; el trabajo ya está persistido."""
    if getattr(settings, "DURABLE_EXECUTION_MODE", os.environ.get("DURABLE_EXECUTION_MODE")) == "external":
        return None
    manage_py = Path(settings.BASE_DIR) / "manage.py"
    kwargs = {
        "cwd": str(settings.BASE_DIR),
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    else:
        kwargs["start_new_session"] = True
    def launch():
        try:
            subprocess.Popen(
                [
                    sys.executable,
                    str(manage_py),
                    "run_durable_worker",
                    "--once",
                    "--delay-seconds",
                    str(max(0, int(delay_seconds))),
                ],
                **kwargs,
            )
        except OSError as exc:
            logger.error("durable.worker.wakeup_failed error_type=%s", type(exc).__name__)
    transaction.on_commit(launch, using="default")
