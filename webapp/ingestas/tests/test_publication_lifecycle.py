from django.test import TestCase, override_settings

from ingestas.lifecycle import (
    fail_portal_run,
    finalize_portal_run,
    start_or_resume_portal_run,
)
from ingestas.models import EjecucionPortal, PropiedadesCompetencia, ScrapingJob
from intelligence.skills.scrapi.db_utils import guardar_propiedades


@override_settings(
    SCRAPING_LIFECYCLE_MIN_COVERAGE=0.65,
    SCRAPING_LIFECYCLE_MISSES_TO_RETIRE=2,
)
class PublicationLifecycleTests(TestCase):
    portal = 'urbania'

    def make_job(self):
        return ScrapingJob.objects.create(
            estado='idle',
            parametros={'portales': [self.portal]},
        )

    def make_run(self):
        from scrapi.source_config import source_snapshot
        config = source_snapshot(self.portal)
        return EjecucionPortal.objects.create(portal=self.portal,
            source_key=config['source_key'], source_config=config,
            discovery={'complete': True, 'stop_reason': 'next_disabled'})

    def save_ids(self, run, *property_ids):
        rows = [
            {
                'id_origen': property_id,
                'titulo': f'Propiedad {property_id}',
            }
            for property_id in property_ids
        ]
        return guardar_propiedades(
            rows,
            fuente=self.portal,
            lifecycle_run_id=run.id,
        )

    def test_first_reliable_run_is_baseline(self):
        legacy = PropiedadesCompetencia.objects.create(
            fuente=self.portal,
            id_origen='legacy',
        )
        run = self.make_run()
        self.save_ids(run, 'a', 'b')

        result = finalize_portal_run(run)

        legacy.refresh_from_db()
        run.refresh_from_db()
        self.assertTrue(result['baseline'])
        self.assertTrue(run.es_confiable)
        self.assertEqual(run.propiedades_vistas, 2)
        self.assertEqual(legacy.estado_publicacion, 'sin_verificar')
        self.assertEqual(
            PropiedadesCompetencia.objects.get(id_origen='a').estado_publicacion,
            'activa',
        )

    def test_two_consecutive_absences_confirm_retirement(self):
        baseline = self.make_run()
        self.save_ids(baseline, 'a', 'b', 'c')
        finalize_portal_run(baseline)

        second = self.make_run()
        self.save_ids(second, 'a', 'b')
        result_second = finalize_portal_run(second)
        missing = PropiedadesCompetencia.objects.get(id_origen='c')
        self.assertEqual(result_second['possible'], 1)
        self.assertEqual(missing.estado_publicacion, 'posible_retirada')
        self.assertEqual(missing.ausencias_consecutivas, 1)
        self.assertIsNotNone(missing.fecha_primera_ausencia)
        self.assertIsNone(missing.fecha_retiro_confirmado)

        third = self.make_run()
        self.save_ids(third, 'a', 'b')
        result_third = finalize_portal_run(third)
        missing.refresh_from_db()
        self.assertEqual(result_third['retired'], 1)
        self.assertEqual(missing.estado_publicacion, 'retirada')
        self.assertEqual(missing.ausencias_consecutivas, 2)
        self.assertIsNotNone(missing.fecha_retiro_confirmado)

    def test_reappearance_reactivates_property_and_clears_absences(self):
        baseline = self.make_run()
        self.save_ids(baseline, 'a', 'b', 'c')
        finalize_portal_run(baseline)
        second = self.make_run()
        self.save_ids(second, 'a', 'b')
        finalize_portal_run(second)
        third = self.make_run()
        self.save_ids(third, 'a', 'b')
        finalize_portal_run(third)

        retired = PropiedadesCompetencia.objects.get(id_origen='c')
        self.assertEqual(retired.estado_publicacion, 'retirada')

        reappearance = self.make_run()
        self.save_ids(reappearance, 'a', 'b', 'c')
        restored = PropiedadesCompetencia.objects.get(id_origen='c')

        self.assertEqual(restored.estado_publicacion, 'activa')
        self.assertEqual(restored.ausencias_consecutivas, 0)
        self.assertIsNone(restored.fecha_primera_ausencia)
        self.assertIsNone(restored.fecha_retiro_confirmado)
        self.assertEqual(restored.ultima_ejecucion_vista, reappearance)

    def test_low_coverage_run_never_marks_absences(self):
        baseline = self.make_run()
        self.save_ids(baseline, 'a', 'b', 'c', 'd')
        finalize_portal_run(baseline)

        partial = self.make_run()
        self.save_ids(partial, 'a', 'b')
        result = finalize_portal_run(partial)

        partial.refresh_from_db()
        missing = PropiedadesCompetencia.objects.get(id_origen='c')
        self.assertFalse(result['reliable'])
        self.assertEqual(partial.estado, 'incomplete')
        self.assertEqual(missing.estado_publicacion, 'activa')
        self.assertEqual(missing.ausencias_consecutivas, 0)

    def test_failed_run_never_marks_absences(self):
        baseline = self.make_run()
        self.save_ids(baseline, 'a', 'b')
        finalize_portal_run(baseline)
        failed = self.make_run()
        self.save_ids(failed, 'a')

        fail_portal_run(failed, 'Camoufox se cerró', status='error')

        missing = PropiedadesCompetencia.objects.get(id_origen='b')
        failed.refresh_from_db()
        self.assertEqual(failed.estado, 'error')
        self.assertFalse(failed.es_confiable)
        self.assertEqual(missing.estado_publicacion, 'activa')

    def test_resume_reuses_stable_run_token_for_same_job(self):
        job = self.make_job()
        job.estado = 'running'
        job.save(update_fields=['estado'])
        first = start_or_resume_portal_run(job, self.portal)
        fail_portal_run(first, 'interrupción', status='incomplete')

        resumed = start_or_resume_portal_run(job, self.portal)

        job.refresh_from_db()
        self.assertEqual(resumed.id, first.id)
        self.assertEqual(resumed.estado, 'running')
        self.assertEqual(
            job.parametros['lifecycle_runs'][self.portal],
            str(first.token),
        )
