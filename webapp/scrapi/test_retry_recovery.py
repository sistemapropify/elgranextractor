import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from scrapi import paged_engine
from scrapi.retry_policy import retry_delay, transient_failure, wait_for_retry
from scrapi.contracts import ScrapingInterrupted


class RecoveryTests(unittest.IsolatedAsyncioTestCase):
    def test_network_and_data_errors_have_distinct_budgets(self):
        self.assertEqual(retry_delay(ConnectionError('offline'), 3), 20)
        self.assertIsNone(retry_delay(ConnectionError('offline'), 6))
        self.assertIsNone(retry_delay(RuntimeError('location.coordinates_missing'), 3))
        self.assertFalse(transient_failure(RuntimeError('HTTP 404')))

    def test_wrapped_transport_error_is_preserved(self):
        error = RuntimeError('detail.extraction_failed')
        error.__cause__ = TimeoutError()
        self.assertTrue(transient_failure(error))

    async def test_recovers_same_property_without_partial_attempt_data(self):
        raw = {'ID': 'abc', 'nested': {'price': 10}}
        calls = []
        async def enrich(portal, source, page, candidate):
            calls.append(candidate['ID'])
            self.assertEqual(candidate['nested']['price'], 10)
            if len(calls) < 4:
                candidate['nested']['price'] = 999
                raise ConnectionError('offline')
            candidate['complete'] = True
        emit = AsyncMock()
        with patch.object(paged_engine, 'enrich', enrich), \
             patch.object(paged_engine, 'normalize', return_value={'datos_crudos': {}}), \
             patch.object(paged_engine, 'wait_for_retry', new_callable=AsyncMock):
            await paged_engine.prepare_detail('properati', None, SimpleNamespace(url='detail'), raw, emit)
        self.assertEqual(calls, ['abc'] * 4)
        self.assertTrue(raw['complete'])
        self.assertIn('recovery.succeeded', [call.kwargs['event'] for call in emit.call_args_list])

    async def test_stop_is_honored_during_recovery_wait(self):
        emit = AsyncMock(side_effect=ScrapingInterrupted('stopped'))
        with self.assertRaises(ScrapingInterrupted):
            await wait_for_retry(60, emit)

    async def test_properati_does_not_extract_after_navigation_failure(self):
        from scrapi.properati_scraper import navegar_con_cloudflare
        page = SimpleNamespace(goto=AsyncMock(side_effect=ConnectionError('offline')))
        with self.assertRaisesRegex(RuntimeError, 'navigation.failed') as caught:
            await navegar_con_cloudflare(page, 'https://www.properati.com.pe/detalle/example')
        self.assertTrue(transient_failure(caught.exception))
        self.assertIsNone(page._scraping_initial_html)


if __name__ == '__main__':
    unittest.main()
