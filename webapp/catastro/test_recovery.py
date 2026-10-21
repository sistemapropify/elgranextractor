from unittest import TestCase
from unittest.mock import Mock, patch
from catastro.jobs import collect_with_recovery
from scrapi.geollaqta_scraper import CollectionError, Stopped


class ConnectionRecoveryTests(TestCase):
    job = dict(id='test', ubigeo='040102', limit_lots=0, lot_id=None, retry_missing=False, workers=10)

    def result(self, **values):
        return dict(processed=1, uploaded=1, partial=0, failed=0, remaining_objects=0, **values)

    @patch('catastro.jobs._wait_before_retry')
    @patch('catastro.jobs.collect')
    def test_transport_failure_retries_same_district_from_ledger(self, collect, wait):
        collect.side_effect = [CollectionError('No se pudo conectar con COFOPRI.'), self.result()]
        state, progress, checkpoint = Mock(), Mock(), Mock()
        result = collect_with_recovery(self.job, state, progress, checkpoint)
        self.assertEqual(result['uploaded'], 1)
        self.assertEqual(collect.call_count, 2)
        self.assertEqual(collect.call_args_list[0].args, collect.call_args_list[1].args)
        wait.assert_called_once_with(30, checkpoint)

    @patch('catastro.jobs._wait_before_retry')
    @patch('catastro.jobs.collect')
    def test_access_denial_is_not_retried(self, collect, wait):
        collect.side_effect = CollectionError('COFOPRI requiere acceso o rechazó la descarga; ejecución detenida.', 403)
        with self.assertRaises(CollectionError):
            collect_with_recovery(self.job, Mock(), Mock(), Mock())
        wait.assert_not_called()

    @patch('catastro.jobs._wait_before_retry', side_effect=Stopped('Pausa solicitada'))
    @patch('catastro.jobs.collect', side_effect=CollectionError('No se pudo conectar con COFOPRI.'))
    def test_pause_during_wait_does_not_restart(self, collect, wait):
        with self.assertRaises(Stopped):
            collect_with_recovery(self.job, Mock(), Mock(), Mock())
        self.assertEqual(collect.call_count, 1)

    @patch('catastro.jobs._wait_before_retry')
    @patch('catastro.jobs.collect')
    def test_retry_limit_is_bounded(self, collect, wait):
        collect.side_effect = CollectionError('No se pudo conectar con COFOPRI.')
        with self.assertRaises(CollectionError):
            collect_with_recovery(self.job, Mock(), Mock(), Mock())
        self.assertEqual(collect.call_count, 4)
        self.assertEqual([c.args[0] for c in wait.call_args_list], [30, 60, 120])

    @patch('catastro.jobs._wait_before_retry')
    @patch('catastro.jobs.collect')
    def test_finished_batch_with_connection_error_is_resumed(self, collect, wait):
        failed = self.result()
        failed.update(failed=1, last_error='No se pudo conectar con R2; la carga queda pendiente.')
        collect.side_effect = [failed, self.result()]
        result = collect_with_recovery(self.job, Mock(), Mock(), Mock())
        self.assertEqual(result['failed'], 0)
        self.assertEqual(result['uploaded'], 2)
        self.assertEqual(result['processed'], 2)
        wait.assert_called_once()

    @patch('catastro.jobs._wait_before_retry')
    @patch('catastro.jobs.collect')
    def test_mixed_access_denial_and_network_error_does_not_retry(self, collect, wait):
        failed = self.result()
        failed.update(failed=2, last_error='No se pudo conectar con COFOPRI.', fatal_errors=[
            'COFOPRI requiere acceso o rechazó la descarga; ejecución detenida.',
            'No se pudo conectar con COFOPRI.'])
        collect.return_value = failed
        self.assertEqual(collect_with_recovery(self.job, Mock(), Mock(), Mock())['failed'], 2)
        wait.assert_not_called()
