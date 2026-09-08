import asyncio
import uuid
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch
from django.test import SimpleTestCase, TestCase

from ingestas.lifecycle import start_or_resume_portal_run, finalize_portal_run
from ingestas.models import ScrapingJob, EjecucionPortal, ScrapingCandidate, PropiedadesCompetencia
from ingestas.scraping_store import record_progress, resume_state
from intelligence.skills.scrapi.db_utils import guardar_propiedades
from scrapi.contracts import ScrapingInterrupted
from scrapi.normalization import urbania_row, prices
from scrapi.source_config import page_url, source_snapshot, validate_url
from scrapi.paged_engine import crawl_pages
from scrapi.telemetry import sanitize


class SourceAndQualityTests(SimpleTestCase):
    def test_hidden_numbers_do_not_define_url_limit(self):
        self.assertEqual(page_url('urbania', 'https://urbania.pe/buscar/casas?page=1&foo=x', 30),
                         'https://urbania.pe/buscar/casas?foo=x&page=30')
        self.assertEqual(page_url('properati', 'https://www.properati.com.pe/s/lima/5?type=house', 31),
                         'https://www.properati.com.pe/s/lima/31?type=house')
        self.assertIn('-pagina-21.html', page_url('adondevivir', 'https://www.adondevivir.com/casas-pagina-2.html', 21))

    def test_supported_placeholders_in_path_and_query(self):
        for marker in ('{n}', '{page}', '{}'):
            self.assertEqual(page_url('urbania', f'https://urbania.pe/buscar/{marker}?f=1', 20),
                             'https://urbania.pe/buscar/20?f=1')

    def test_rejects_deceptive_hosts_and_credentials(self):
        for url in ('http://urbania.pe/', 'https://urbania.pe.evil.test/',
                    'https://urbania.pe@evil.test/', 'https://127.0.0.1/',
                    'https://urbania.pe:8443/', 'https://user:secret@urbania.pe/'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_url('urbania', url)

    def test_search_scope_ignores_page_but_preserves_filter(self):
        a = source_snapshot('urbania', 'https://urbania.pe/buscar/casas?page=1&tipo=venta')
        b = source_snapshot('urbania', 'https://urbania.pe/buscar/casas?tipo=venta&page=30')
        c = source_snapshot('urbania', 'https://urbania.pe/buscar/casas?tipo=alquiler')
        self.assertEqual(a['source_key'], b['source_key'])
        self.assertNotEqual(a['source_key'], c['source_key'])

    def test_both_currencies_and_decimal_area_survive(self):
        row = urbania_row({'ID': '123', 'Precio': 'S/ 816,500 · USD 230,000',
            'Caracteristicas': '128.5 m² tot. 3 dorm. 2 baños', 'Titulo': 'Casa en alquiler',
            'Ubicacion': 'San Miguel, Lima, Lima', 'URL Propiedad': 'https://urbania.pe/inmueble/123'}, '2026-09-07')
        self.assertEqual((row['precio_soles'], row['precio_usd'], row['area_m2']), (816500, 230000, 128.5))
        self.assertEqual((row['tipo_inmueble'], row['tipo_operacion'], row['departamento']), ('Casa', 'Alquiler', 'Lima'))
        self.assertIsNotNone(row['url'])

    def test_ranges_and_unknown_locations_are_not_fabricated(self):
        row = urbania_row({'ID': '123', 'Caracteristicas': '60 a 120 m²'}, '2026-09-07')
        self.assertIsNone(row['area_m2'])
        self.assertIsNone(row['departamento'])
        self.assertIsNone(row['tipo_inmueble'])
        self.assertEqual(prices('US$ 230.000,50')['precio_usd'], 230000.5)

    def test_event_payload_redacts_secrets(self):
        event = sanitize({'cookie': 'secret', 'message': 'https://example.test/?sig=secret&q=casas',
                          'authorization': 'Bearer secret'})
        self.assertNotIn('secret', str(event))
        self.assertIn('casas', event['message'])

    def test_snapshot_preserves_custom_page_template_for_execution(self):
        config = source_snapshot('urbania', 'https://urbania.pe/buscar/pagina/{n}?tipo=casas')
        self.assertEqual(page_url('urbania', config['source_url'], 20), 'https://urbania.pe/buscar/pagina/20?tipo=casas')

    def test_numeric_values_and_apostrophe_thousands(self):
        from scrapi.normalization import number
        self.assertEqual(number(128.123), 128.123)
        self.assertEqual(prices("S/. 1'372,950.00")['precio_soles'], 1372950)

    def test_explicit_page_count_takes_precedence_over_missing_next_text(self):
        from scrapi.paged_engine import terminal_reason
        self.assertIsNone(terminal_reason('remax', {'current':32,'total_pages':34,'pager_present':True,'next_present':False}))
        self.assertEqual(terminal_reason('remax', {'current':34,'total_pages':34}), 'last_page_observed')


class CrawlPolicyTests(IsolatedAsyncioTestCase):
    async def crawl(self, last=30, cap=300, repeat=None, save=None, missing=False):
        page = SimpleNamespace(n=0, url='')
        events = []
        async def navigate(p, source, portal, url, emit):
            p.n += 1
            p.url = url
        async def extract(p):
            n = repeat if repeat and p.n > repeat else p.n
            return [{'ID': '' if missing else str(n), 'Titulo': 'Casa en venta',
                     'URL Propiedad': f'https://urbania.pe/item/{n}'},
                    {'ID': str(n), 'Titulo': 'Casa en venta'}]
        async def state(_):
            return {'next_present': True, 'next_enabled': page.n < last, 'pager_present': True,
                    'next_href': '', 'current': None, 'total_pages': None, 'explicit_empty': False}
        async def emit(**payload):
            events.append(payload)
            return True
        page.evaluate = state
        with patch('scrapi.paged_engine.navigate', navigate):
            rows = await crawl_pages('urbania', 'https://urbania.pe/buscar/casas',
                SimpleNamespace(extraer_listado=extract), page, None, emit=emit,
                max_pages=cap, listing_only=True, batch_callback=save)
        return rows, events

    async def test_follows_all_thirty_pages_with_hidden_numbers(self):
        rows, events = await self.crawl()
        self.assertEqual(len(rows), 30)
        self.assertTrue(rows.discovery.complete)
        self.assertEqual(rows.discovery.stop_reason, 'next_disabled')
        self.assertEqual(rows.discovery.duplicates, 30)
        self.assertEqual([e['checkpoint_page'] for e in events if 'checkpoint_page' in e], list(range(1, 31)))

    async def test_safety_cap_is_partial(self):
        rows, _ = await self.crawl(last=30, cap=5)
        self.assertEqual(len(rows), 5)
        self.assertFalse(rows.discovery.complete)
        self.assertEqual(rows.discovery.stop_reason, 'max_pages')

    async def test_repeated_page_is_not_saved_or_certified(self):
        rows, _ = await self.crawl(repeat=3)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows.discovery.stop_reason, 'repeated_page')
        self.assertFalse(rows.discovery.complete)

    async def test_invalid_cards_prevent_complete_coverage(self):
        rows, _ = await self.crawl(last=1, missing=True)
        self.assertEqual(rows.discovery.invalid, 1)
        self.assertFalse(rows.discovery.complete)

    async def test_failed_write_does_not_confirm_page(self):
        def save(rows):
            raise RuntimeError('database unavailable')
        with self.assertRaisesRegex(RuntimeError, 'database unavailable'):
            await self.crawl(last=1, save=save)


class DurableScrapingTests(TestCase):
    def make_run(self, url='https://urbania.pe/buscar/venta-casas'):
        token = uuid.uuid4()
        job = ScrapingJob.objects.create(estado='running', execution_token=token,
            parametros={'urls': {'urbania': url}, 'portales': ['urbania']})
        return job, start_or_resume_portal_run(job, 'urbania'), token

    def save(self, run, token, *ids):
        return guardar_propiedades([{'id_origen': key, 'titulo': f'Casa {key}'} for key in ids],
            'urbania', lifecycle_run_id=run.pk, execution_token=token)

    def complete(self, run, token):
        record_progress(run.pk, {'discovery': {'complete': True, 'stop_reason': 'next_disabled'}}, token)
        return finalize_portal_run(run, execution_token=token)

    def test_repeated_saves_preserve_unique_counters(self):
        job, run, token = self.make_run()
        self.save(run, token, 'a', 'b')
        counts = self.save(run, token, 'a')
        self.assertEqual((counts['total'], counts['nuevas'], counts['actualizadas']), (2, 2, 0))

    def test_superseded_owner_cannot_write_or_checkpoint(self):
        job, run, token = self.make_run()
        ScrapingJob.objects.filter(pk=job.pk).update(execution_token=uuid.uuid4())
        with self.assertRaises(ScrapingInterrupted):
            self.save(run, token, 'a')
        with self.assertRaises(ScrapingInterrupted):
            record_progress(run.pk, {'candidate_batch': [{'id': 'a'}]}, token)
        self.assertEqual(PropiedadesCompetencia.objects.count(), 0)

    def test_discovery_is_durable_before_detail_and_checkpoint_is_blocked(self):
        _, run, token = self.make_run()
        record_progress(run.pk, {'candidate_batch': [{'id': 'a', 'raw': {'ID': 'a'}, 'page': 3}]}, token)
        self.assertEqual(resume_state(run)['pending'][0]['id'], 'a')
        with self.assertRaisesRegex(RuntimeError, 'checkpoint.pending'):
            record_progress(run.pk, {'checkpoint_page': 3}, token)
        self.save(run, token, 'a')
        record_progress(run.pk, {'checkpoint_page': 3}, token)
        self.assertEqual(resume_state(run)['pending'], [])

    def test_unproven_completion_never_applies_absences(self):
        _, baseline, token = self.make_run()
        self.save(baseline, token, 'a', 'b', 'c')
        self.complete(baseline, token)
        _, partial, token = self.make_run()
        self.save(partial, token, 'a', 'b')
        result = finalize_portal_run(partial, execution_token=token)
        self.assertFalse(result['reliable'])
        self.assertEqual(PropiedadesCompetencia.objects.get(id_origen='c').ausencias_consecutivas, 0)

    def test_changed_scope_does_not_retire_previous_search(self):
        _, original, token = self.make_run()
        self.save(original, token, 'old')
        self.complete(original, token)
        for _ in range(3):
            _, changed, token = self.make_run('https://urbania.pe/buscar/alquiler-casas')
            self.save(changed, token, 'new')
            self.complete(changed, token)
        self.assertEqual(PropiedadesCompetencia.objects.get(id_origen='old').estado_publicacion, 'activa')

    def test_finalization_is_idempotent(self):
        _, first, token = self.make_run()
        self.save(first, token, 'a', 'b', 'c')
        self.complete(first, token)
        _, second, token = self.make_run()
        self.save(second, token, 'a', 'b')
        self.complete(second, token)
        finalize_portal_run(second, execution_token=token)
        self.assertEqual(PropiedadesCompetencia.objects.get(id_origen='c').ausencias_consecutivas, 1)

    def test_expired_lease_rejects_writes_even_with_matching_token(self):
        from datetime import timedelta
        from django.utils import timezone
        job, run, token = self.make_run()
        ScrapingJob.objects.filter(pk=job.pk).update(lease_expires_at=timezone.now()-timedelta(seconds=1))
        with self.assertRaises(ScrapingInterrupted):
            self.save(run, token, 'a')

    def test_preview_logs_sample_without_property_or_lifecycle_writes(self):
        from ingestas.scraping_preview import run_preview
        from scrapi.contracts import ScrapeRows
        from unittest.mock import MagicMock
        job = ScrapingJob.objects.create(estado='running', execution_token=uuid.uuid4(),
            parametros={'mode': 'preview', 'portales': ['urbania']})
        with patch('scrapi.paged_engine.run_paged', return_value=ScrapeRows([{'id_origen': 'x'}])), \
             patch('colas.scraping_tasks._start_portal_heartbeat', return_value=(MagicMock(), MagicMock())):
            run_preview(job, job.execution_token)
        job.refresh_from_db()
        self.assertEqual(job.estado, 'completed')
        self.assertEqual(PropiedadesCompetencia.objects.count(), 0)
        self.assertEqual(EjecucionPortal.objects.count(), 0)
        self.assertTrue(job.logs.filter(evento='preview.result').exists())

    def test_log_poll_keeps_all_events_across_batches(self):
        import json
        from django.test import RequestFactory
        from ingestas.models import ScrapingLog
        from ingestas.views import ScrapingStreamView
        job = ScrapingJob.objects.create(estado='completed')
        ScrapingLog.objects.bulk_create([ScrapingLog(job=job, nivel='info', mensaje=f'event {i}') for i in range(205)])
        factory = RequestFactory()
        def poll(params):
            request = factory.get('/', params)
            request.user = SimpleNamespace(is_authenticated=True)
            return json.loads(ScrapingStreamView.as_view()(request, job_id=job.pk).content)
        one = poll({'poll': '1'})
        two = poll({'poll': '1', 'last_id': one['last_id']})
        self.assertEqual((len(one['logs']),len(two['logs'])), (200,5))
        self.assertFalse(one['ended'])
        self.assertTrue(two['ended'])
