from datetime import timedelta
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from lead_intelligence.durable_jobs import claim_next_job, enqueue_durable_job, finish_job, owned_job
from lead_intelligence.models import DurableJob


class DurableJobQueueTests(TestCase):
    databases = {"default"}

    @patch('response_intelligence.shadow.shadow_mode_enabled', return_value=True)
    @patch('lead_intelligence.durable_jobs.wake_durable_worker')
    def test_distinct_message_events_with_same_text_are_not_collapsed(self, wake, enabled):
        from response_intelligence.shadow import spawn_shadow_draft
        first = spawn_shadow_draft(source_event_id='event-1', client_message='Hola', thread_id='thread-1')
        duplicate = spawn_shadow_draft(source_event_id='event-1', client_message='Hola', thread_id='thread-1')
        second = spawn_shadow_draft(source_event_id='event-2', client_message='Hola', thread_id='thread-1')
        self.assertEqual(first.pk, duplicate.pk)
        self.assertNotEqual(first.pk, second.pk)
        self.assertNotIn('source_event_id', first.payload['client_message'])

    @patch('response_intelligence.shadow.shadow_mode_enabled', return_value=True)
    @patch('response_intelligence.shadow.maybe_generate_shadow_draft', return_value=None)
    def test_missing_shadow_result_is_retried_not_marked_successful(self, generate, enabled):
        enqueue_durable_job(DurableJob.Kind.SHADOW_RECONCILE,
            {'client_message': {'client_message': 'Hola'}}, 'shadow:failure', max_attempts=2)
        call_command('run_durable_worker', once=True)
        job = DurableJob.objects.get(dedupe_key='shadow:failure')
        self.assertEqual(job.status, DurableJob.Status.FAILED)
        self.assertEqual(job.attempts, 2)

    def test_expired_owner_cannot_finish_or_renew_a_reclaimed_job(self):
        enqueue_durable_job(DurableJob.Kind.LEAD_ANALYSIS, {}, 'analysis:fencing')
        old_claim = claim_next_job()
        DurableJob.objects.filter(pk=old_claim.pk).update(lease_until=timezone.now() - timedelta(seconds=1))
        new_claim = claim_next_job()
        self.assertEqual(new_claim.attempts, old_claim.attempts + 1)
        self.assertEqual(finish_job(old_claim), 0)
        self.assertEqual(finish_job(old_claim, RuntimeError('old worker')), 0)
        self.assertEqual(owned_job(old_claim).update(heartbeat_at=timezone.now()), 0)
        self.assertEqual(finish_job(new_claim), 1)

    def test_crash_on_last_attempt_becomes_failed_after_lease_expires(self):
        job = DurableJob.objects.create(kind=DurableJob.Kind.LEAD_ANALYSIS,
            status=DurableJob.Status.RUNNING, dedupe_key='analysis:exhausted',
            attempts=3, max_attempts=3, lease_until=timezone.now() - timedelta(seconds=1))
        self.assertIsNone(claim_next_job())
        job.refresh_from_db()
        self.assertEqual(job.status, DurableJob.Status.FAILED)
        self.assertIsNotNone(job.completed_at)

    def test_cancelled_job_is_not_completed_by_its_worker(self):
        enqueue_durable_job(DurableJob.Kind.LEAD_ANALYSIS, {}, 'analysis:cancel')
        job = claim_next_job()
        DurableJob.objects.filter(pk=job.pk).update(status=DurableJob.Status.CANCELLED)
        self.assertEqual(finish_job(job), 0)

    def test_retry_records_redacted_failure_and_stops_at_limit(self):
        enqueue_durable_job(DurableJob.Kind.LEAD_ANALYSIS, {}, 'analysis:retry', max_attempts=2)
        job = claim_next_job()
        finish_job(job, RuntimeError('password=private-value'))
        job.refresh_from_db()
        self.assertEqual(job.status, DurableJob.Status.PENDING)
        self.assertNotIn('private-value', job.error_summary)
        retry = claim_next_job()
        finish_job(retry, RuntimeError('last failure'))
        retry.refresh_from_db()
        self.assertEqual(retry.status, DurableJob.Status.FAILED)
        self.assertIsNone(claim_next_job())

    def test_enqueue_is_idempotent_for_same_event(self):
        first, created_first = enqueue_durable_job(
            DurableJob.Kind.SHADOW_RECONCILE,
            {"lead_id": 3561},
            "shadow:3561:event-1",
        )
        second, created_second = enqueue_durable_job(
            DurableJob.Kind.SHADOW_RECONCILE,
            {"lead_id": 3561},
            "shadow:3561:event-1",
        )

        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(DurableJob.objects.count(), 1)

    def test_expired_lease_is_recovered_after_restart(self):
        job = DurableJob.objects.create(
            kind=DurableJob.Kind.LEAD_ANALYSIS,
            status=DurableJob.Status.RUNNING,
            dedupe_key="analysis:expired",
            payload={},
            attempts=1,
            max_attempts=3,
            lease_until=timezone.now() - timedelta(seconds=1),
        )

        claimed = claim_next_job()

        self.assertEqual(claimed.pk, job.pk)
        self.assertEqual(claimed.status, DurableJob.Status.RUNNING)
        self.assertEqual(claimed.attempts, 2)
        self.assertGreater(claimed.lease_until, timezone.now())

    @patch(
        "lead_intelligence.management.commands.run_durable_worker.Command._execute"
    )
    def test_once_drains_every_pending_job(self, execute):
        for index in range(2):
            DurableJob.objects.create(
                kind=DurableJob.Kind.SHADOW_RECONCILE,
                dedupe_key=f"shadow:drain:{index}",
                payload={},
            )

        call_command("run_durable_worker", once=True)

        self.assertEqual(execute.call_count, 2)
        self.assertEqual(
            DurableJob.objects.filter(status=DurableJob.Status.COMPLETED).count(),
            2,
        )
