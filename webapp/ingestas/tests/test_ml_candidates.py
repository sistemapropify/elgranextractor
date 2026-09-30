from datetime import datetime, timezone as tz
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from django.db import transaction
from django.test import TestCase, SimpleTestCase, RequestFactory
from django.utils import timezone
from ingestas import ml_candidates as service
from ingestas.ml_eligibility import digest, evaluate
from ingestas.models import (PropiedadesCompetencia, MLObservation, MLCandidate,
                            RevisionPropiedadScraping, CambioPropiedadScraping, MLPipelineState)
from ingestas.ml_candidate_views import dashboard, history
from scrapi.normalization import construction_age


def valid():
    return dict(fuente='remax', id_origen='ml-test', tipo_inmueble='Casa', tipo_operacion='Venta',
                precio_usd=Decimal('300000'), area_terreno=Decimal('200'), area_construida=Decimal('240'),
                latitud=Decimal('-16.4'), longitud=Decimal('-71.5'), precision_ubicacion='exacta',
                titulo='Casa', fecha_extraccion=timezone.now())


class RuleTests(SimpleTestCase):
    def test_archived_warning_on_unused_field_does_not_exclude(self):
        row = {**valid(), 'normalizer_issues': ['area_m2', 'precio_soles']}
        self.assertEqual(evaluate(row)['status'], 'eligible')

    def test_required_surfaces_and_no_fake_zero_age(self):
        row = valid()
        self.assertEqual(evaluate(row)['status'], 'eligible')
        row['area_construida'] = None
        self.assertEqual(evaluate(row)['status'], 'review')
        row['tipo_inmueble'] = 'Terreno'
        self.assertEqual(evaluate(row)['status'], 'eligible')

    def test_approximate_is_reference_not_bad_coordinate(self):
        row = {**valid(), 'precision_ubicacion': 'aproximada'}
        result = evaluate(row)
        self.assertEqual(result['status'], 'reference')
        self.assertEqual([r['code'] for r in result['reasons']], ['location.not_exact'])

    def test_no_fixed_conversion_or_fake_closed_sale(self):
        row = {**valid(), 'precio_usd': None, 'precio_soles': '100000', 'estado_publicacion': 'retirada'}
        result = evaluate(row)
        self.assertEqual(result['status'], 'review')
        self.assertIn('price.currency_pending', [r['code'] for r in result['reasons']])
        self.assertTrue(any('no demuestra' in n for n in result['notes']))

    def test_fingerprint_ignores_seen_dates_but_not_prices(self):
        row = valid()
        self.assertEqual(digest(row), digest({**row, 'fecha_extraccion': '2030-01-01', 'last_seen': '2030-01-01'}))
        self.assertNotEqual(digest(row), digest({**row, 'precio_usd': '350000'}))
        self.assertNotEqual(digest(row), digest({**row, 'manual_reason': 'dato falso'}))

    def test_age_with_evidence_conflicts_and_historical_year(self):
        stamp = datetime(2026, 9, 30, tzinfo=tz.utc)
        self.assertEqual(construction_age({'description': 'Casa construida en 1986'}, stamp)[0], 40)
        self.assertEqual(construction_age({'description': 'Casa 20 años de antigüedad'}, stamp)[0], 20)
        self.assertIsNone(construction_age({'description': 'Casa: antigüedad 20 años, 40 años de antigüedad'}, stamp)[0])
        self.assertIsNone(construction_age({'description': 'Casa de 20 años de antigüedad. Construida en 1986'}, stamp)[0])
        self.assertIsNone(construction_age({'description': 'Entrega 2020. Propietario hace 20 años.'}, stamp)[0])
        self.assertIsNone(construction_age({'description': 'Casa construida en 1986'})[0])
        self.assertEqual(construction_age({'Antiguedad': 0})[0], 0)


class CandidateTests(TestCase):
    def setUp(self):
        service._schema_cache = (0, False)
        self.obj = PropiedadesCompetencia.objects.create(**valid())

    def test_signal_idempotency_versions_and_reversal(self):
        self.assertEqual(MLObservation.objects.count(), 1)
        self.obj.ultima_vez_vista = timezone.now()
        self.obj.save()
        self.assertEqual(MLObservation.objects.count(), 1)
        self.obj.area_terreno = Decimal('210')
        self.obj.save()
        self.obj.area_terreno = Decimal('200')
        self.obj.save()
        self.assertEqual(list(MLObservation.objects.order_by('sequence').values_list('sequence', flat=True)), [1,2,3])
        self.assertEqual(MLCandidate.objects.get().latest.sequence, 3)

    def test_old_evaluation_cannot_replace_new_version(self):
        self.obj.precision_ubicacion = 'aproximada'
        self.obj.save()
        service.process_pending(1)
        self.assertEqual(MLCandidate.objects.get().status, 'pending')
        service.process_pending(1)
        self.assertEqual(MLCandidate.objects.get().status, 'reference')

    def test_repair_logs_evidence_keeps_dates_and_reevaluates(self):
        self.obj.descripcion = 'Casa construida en 1986'
        self.obj.fecha_extraccion = datetime(2026,9,30,tzinfo=tz.utc)
        self.obj.save()
        stamp = self.obj.fecha_extraccion
        self.assertTrue(service.repair_age(self.obj.pk))
        self.obj.refresh_from_db()
        self.assertEqual(self.obj.antiguedad_anios, 40)
        self.assertEqual(self.obj.fecha_extraccion, stamp)
        self.assertEqual(CambioPropiedadScraping.objects.get().cambios['antiguedad_anios']['despues'], 40)
        self.assertEqual(MLCandidate.objects.get().latest.snapshot['antiguedad_anios'], 40)
        self.assertFalse(service.repair_age(self.obj.pk))

    def test_protected_age_and_manual_exclusion(self):
        self.obj.descripcion = 'Casa 40 años de antigüedad'
        self.obj.save()
        RevisionPropiedadScraping.objects.create(propiedad=self.obj, excluida=True, motivo='verificación', campos_protegidos=['antiguedad_anios'])
        self.assertFalse(service.repair_age(self.obj.pk))
        service.process_pending(50)
        self.assertEqual(MLCandidate.objects.get().status, 'excluded')

    def test_conflicting_description_is_not_silently_admitted(self):
        self.obj.descripcion = 'Casa antigüedad 20 años. 40 años de antigüedad.'
        self.obj.save()
        service.process_pending(50)
        candidate = MLCandidate.objects.select_related('latest').get()
        self.assertEqual(candidate.status, 'review')
        self.assertIn('age.conflict', [r['code'] for r in candidate.latest.reasons])
        self.obj.refresh_from_db()
        self.assertIsNone(self.obj.antiguedad_anios)

    def test_transaction_rollback_keeps_both_consistent(self):
        try:
            with transaction.atomic():
                self.obj.precio_usd = 500000
                self.obj.save()
                raise RuntimeError('abort')
        except RuntimeError:
            pass
        self.assertEqual(MLObservation.objects.count(), 1)
        self.obj.refresh_from_db()
        self.assertEqual(self.obj.precio_usd, Decimal('300000'))

    def test_reconciliation_recovers_bulk_update_and_resumes(self):
        PropiedadesCompetencia.objects.filter(pk=self.obj.pk).update(precio_usd=400000)
        result = service.reconcile_chunk(1, force=True)
        self.assertEqual(result['queued'], 1)
        self.assertEqual(MLPipelineState.objects.get().cursor, self.obj.pk)
        self.assertTrue(service.reconcile_chunk(1, force=True)['complete'])
        self.assertEqual(MLPipelineState.objects.get().cursor, 0)
        self.assertEqual(MLCandidate.objects.get().latest.snapshot['precio_usd'], '400000')

    def test_retries_become_visible_error(self):
        with patch('ingestas.ml_candidates.evaluate', side_effect=ValueError('bad data')):
            with self.assertLogs('ingestas.ml_candidates', level='ERROR'):
                for _ in range(3):
                    service.process_pending(1)
        self.assertEqual(MLCandidate.objects.get().status, 'error')
        self.assertEqual(MLObservation.objects.get().attempts, 3)

    def test_authenticated_summary_export_history(self):
        rf = RequestFactory()
        self.assertEqual(dashboard(rf.get('/?format=summary')).status_code, 401)
        self.assertEqual(history(rf.get('/'), self.obj.pk).status_code, 401)
        request = rf.get('/?format=summary')
        request.current_user = SimpleNamespace(is_authenticated=True, is_active=True)
        self.assertContains(dashboard(request), '"model_trained": false')
        request = rf.get('/?exportar=csv&estado=pending')
        request.current_user = SimpleNamespace(is_authenticated=True, is_active=True)
        self.assertContains(dashboard(request), 'ml-test')
        self.assertEqual(history(request, self.obj.pk).status_code, 200)

    def test_candidate_template_renders_with_existing_editor(self):
        from django.template import engines
        # Exercise actual template with a tiny base to avoid unrelated menu routes.
        template = engines['django'].engine.get_template('ingestas/ml_candidates_panel.html')
        from django.template import Context
        service.process_pending(10)
        c = MLCandidate.objects.select_related('latest').get()
        c.status_label = 'Candidata preliminar'
        from django.core.paginator import Paginator
        html = template.render(Context({'ml_ready': True, 'ml_summary': {'versions': 1}, 'ml_page': Paginator([c],50).page(1)}))
        self.assertIn('Historial de cambios', html)
        self.assertIn('openScrapedEditor', html)
        self.assertIn('aún no entrenado', html)

    def test_one_shot_worker_finishes_sweep_and_reports_pending(self):
        import io, json
        from django.core.management import call_command
        output = io.StringIO()
        call_command('ml_candidates_worker', once=True, reconcile=True, batch_size=1, stdout=output)
        last = json.loads(output.getvalue().splitlines()[-1])
        self.assertEqual(last['event'], 'ml.pipeline.finished')
        self.assertEqual(last['pending_versions'], 0)
        self.assertEqual(last['scanned'], 1)
        self.assertEqual(MLCandidate.objects.get().status, 'eligible')
