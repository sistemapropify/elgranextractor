import asyncio
import copy
import uuid
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from django.test import TestCase
from django.utils import timezone
from colas.scraping_tasks import _release_for_shutdown
from ingestas.lifecycle import start_or_resume_portal_run
from ingestas.models import ScrapingJob, PropiedadesCompetencia, ScrapingHistoryRepair
from ingestas.scraping_history import propose, apply_plan, rollback_batch
from scrapi.contracts import ScrapingInterrupted
from scrapi.paged_engine import prepare_detail


class HistoryRepairTests(TestCase):
    def prop(self, key='1'):
        return PropiedadesCompetencia.objects.create(fuente='urbania', id_origen=key,
            precio_usd=230, area_m2=1285, datos_crudos={'ID': key, 'Precio': 'USD 230,000',
                'Caracteristicas': '128.5 m²', 'Titulo': 'Casa en venta'})

    def test_dry_run_apply_and_idempotent_rollback(self):
        prop = self.prop()
        plan = [propose(prop)]
        self.assertEqual(apply_plan(plan)['count'], 1)
        self.assertFalse(ScrapingHistoryRepair.objects.exists())
        prop.refresh_from_db()
        self.assertEqual(prop.area_m2, Decimal('1285'))
        result = apply_plan(plan, apply=True)
        prop.refresh_from_db()
        self.assertEqual(prop.area_m2, Decimal('128.50'))
        self.assertEqual(prop.precio_usd, Decimal('230000'))
        self.assertEqual(rollback_batch(result['batch'])['count'], 1)
        rollback_batch(result['batch'], apply=True)
        prop.refresh_from_db()
        self.assertEqual(prop.area_m2, Decimal('1285'))
        self.assertEqual(rollback_batch(result['batch'], apply=True)['count'], 0)

    def test_stale_plan_rolls_back_entire_batch(self):
        first, second = self.prop('1'), self.prop('2')
        plan = [propose(first), propose(second)]
        PropiedadesCompetencia.objects.filter(pk=second.pk).update(precio_usd=999)
        with self.assertRaisesRegex(ValueError, 'cambiaron'):
            apply_plan(plan, apply=True)
        first.refresh_from_db()
        self.assertEqual(first.precio_usd, Decimal('230'))
        self.assertFalse(ScrapingHistoryRepair.objects.exists())

    def test_tampered_plan_cannot_inject_an_arbitrary_price(self):
        plan = [propose(self.prop())]
        plan[0]['changes']['precio_usd']['after'] = 42
        with self.assertRaises(ValueError):
            apply_plan(plan, apply=True)

    def test_rollback_preserves_subsequent_scraper_data(self):
        prop = self.prop()
        result = apply_plan([propose(prop)], apply=True)
        PropiedadesCompetencia.objects.filter(pk=prop.pk).update(precio_usd=240000)
        with self.assertRaisesRegex(ValueError, 'no se sobrescribirá'):
            rollback_batch(result['batch'], apply=True)
        self.assertIsNone(ScrapingHistoryRepair.objects.get().rolled_back_at)

    def test_wrong_raw_identity_never_proposes_correction(self):
        prop = self.prop()
        prop.datos_crudos['ID'] = 'other'
        self.assertIsNone(propose(prop))


class WorkerShutdownTests(TestCase):
    def test_shutdown_preserves_checkpoint_and_releases_claim(self):
        token = uuid.uuid4()
        job = ScrapingJob.objects.create(estado='running', execution_token=token,
            lease_expires_at=timezone.now() + timedelta(seconds=180),
            parametros={'checkpoints': {'urbania': 12}})
        _release_for_shutdown(job.pk, token)
        job.refresh_from_db()
        self.assertEqual(job.estado, 'idle')
        self.assertIsNone(job.execution_token)
        self.assertEqual(job.parametros['checkpoints']['urbania'], 12)
        self.assertEqual(job.logs.get().evento, 'worker.stopping')

    def test_old_owner_cannot_release_or_start_a_replacement(self):
        old = uuid.uuid4()
        job = ScrapingJob.objects.create(estado='running', execution_token=old)
        current = uuid.uuid4()
        ScrapingJob.objects.filter(pk=job.pk).update(execution_token=current)
        _release_for_shutdown(job.pk, old)
        with self.assertRaises(ScrapingInterrupted):
            start_or_resume_portal_run(job, 'urbania')
        job.refresh_from_db()
        self.assertEqual(job.execution_token, current)
        self.assertFalse(job.ejecuciones_portal.exists())


class DetailRecoveryTests(IsolatedAsyncioTestCase):
    async def test_transient_failure_retries_and_normalizes(self):
        events = []
        async def emit(**event):
            events.append(event)
        raw = {'ID': '1', 'Precio': 'USD 230,000', 'Caracteristicas': '128.5 m²'}
        with patch('scrapi.paged_engine.enrich', AsyncMock(side_effect=[RuntimeError('timeout'), None])) as enrich, patch('scrapi.paged_engine.asyncio.sleep', AsyncMock()):
            row = await prepare_detail('urbania', None, SimpleNamespace(url='https://urbania.pe/item/1'), raw, emit)
        self.assertEqual(enrich.await_count, 2)
        self.assertEqual(row['area_m2'], 128.5)
        self.assertEqual(events[1]['event'], 'detail.retry')

    async def test_cancel_never_retries(self):
        emit = AsyncMock(side_effect=ScrapingInterrupted('stopped'))
        with patch('scrapi.paged_engine.enrich', AsyncMock()) as enrich:
            with self.assertRaises(ScrapingInterrupted):
                await prepare_detail('urbania', None, None, {'ID': '1'}, emit)
        enrich.assert_not_awaited()
