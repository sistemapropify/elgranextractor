from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from ingestas.management.commands.scraping_watchdog import Command


class ScrapingWatchdogTests(SimpleTestCase):
    @patch('ingestas.management.commands.scraping_watchdog.os.name', 'posix')
    def test_azure_does_not_claim_local_interactive_marketplace_job(self):
        job = MagicMock(
            parametros={'execution_scope': 'local_interactive'}
        )
        self.assertFalse(Command._can_execute_here(job))

    @patch('ingestas.management.commands.scraping_watchdog.os.name', 'nt')
    def test_local_host_can_resume_interactive_marketplace_job(self):
        job = MagicMock(
            parametros={'execution_scope': 'local_interactive'}
        )
        self.assertTrue(Command._can_execute_here(job))

    def test_timeout_error_is_recoverable(self):
        job = MagicMock(
            mensaje_error='Ejecución parcial',
            parametros={
                'resultados_por_portal': {
                    'urbania': {'mensaje': 'URBANIA superó el timeout total'}
                }
            },
        )
        self.assertTrue(Command._is_recoverable_error(job))

    @patch('ingestas.management.commands.scraping_watchdog.ScrapingLog.log')
    @patch('ingestas.management.commands.scraping_watchdog.ScrapingJob')
    def test_orphan_is_returned_to_idle_with_bounded_resume(self, job_model, log):
        job = MagicMock(id=9, estado='running', portal_actual='urbania')
        job.parametros = {'checkpoints': {'urbania': 12}, 'auto_resume_count': 2}
        candidates = job_model.objects.filter.return_value.filter.return_value.exclude.return_value.distinct.return_value
        candidates.__iter__.return_value = iter([job])
        job_model.objects.filter.return_value.order_by.return_value.first.return_value = None
        job_model.objects.filter.return_value.filter.return_value.update.return_value = 1

        Command()._recover_orphan(stale_seconds=180, max_resumes=8)

        update = job_model.objects.filter.return_value.filter.return_value.update.call_args.kwargs
        self.assertEqual(update['estado'], 'idle')
        self.assertIsNone(update['execution_token'])
        self.assertEqual(update['parametros']['auto_resume_count'], 3)
        self.assertEqual(update['parametros']['checkpoints']['urbania'], 12)
        log.assert_called_once()
