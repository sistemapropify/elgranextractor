from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.template.loader import get_template
from django.test import SimpleTestCase

from colas.scraping_tasks import (
    _actualizar_contadores,
    _run_scraping,
    _error_camoufox_no_reintentable,
    _resultado_portal_valido,
)
from ingestas.views import _decorate_scraping_job
from intelligence.skills.scrapi.scraper_adondevivir import (
    ScraperAdondevivirSkill,
)
from intelligence.skills.scrapi.scraper_remax import ScraperRemaxSkill
from intelligence.skills.scrapi.scraper_urbania import ScraperUrbaniaSkill


class ScrapingJobReportingTests(SimpleTestCase):
    def test_history_template_compiles(self):
        self.assertIsNotNone(
            get_template("ingestas/scraping_historial.html")
        )

    def test_job_decoration_exposes_selected_portals_and_detected_total(self):
        job = SimpleNamespace(
            parametros={
                "portales": ["remax", "properati"],
                "resultados_por_portal": {
                    "remax": {
                        "estado": "completed",
                        "detectadas": 12,
                    },
                    "properati": {
                        "estado": "error",
                        "detectadas": 0,
                    },
                },
            },
            total_propiedades=12,
            procesadas=12,
            nuevas=4,
            actualizadas=8,
            errores=0,
            estado="completed",
            mensaje_error=None,
            get_estado_display=lambda: "Completado",
        )

        _decorate_scraping_job(job)

        self.assertEqual(job.origen_display, "Remax, Properati")
        self.assertEqual(job.detectadas_display, 12)
        self.assertEqual(
            [portal["nombre"] for portal in job.portales_detalle],
            ["Remax", "Properati"],
        )
        self.assertEqual(job.portales_detalle[0]["detectadas"], 12)
        self.assertEqual(job.estado_efectivo, "completed")

    def test_historical_empty_completion_is_reported_as_error(self):
        job = SimpleNamespace(
            parametros={"portales": ["remax"]},
            total_propiedades=0,
            procesadas=0,
            nuevas=0,
            actualizadas=0,
            errores=0,
            estado="completed",
            mensaje_error=None,
            get_estado_display=lambda: "Completado",
        )

        _decorate_scraping_job(job)

        self.assertEqual(job.estado_efectivo, "error")
        self.assertEqual(job.estado_display, "Error: sin resultados")
        self.assertIn("sin detectar", job.mensaje_error_display)

    @patch("colas.scraping_tasks._instanciar_skill")
    @patch("ingestas.models.ScrapingJob")
    def test_duplicate_executor_does_not_open_browser(
        self, job_model, instantiate_skill
    ):
        job = MagicMock(id=87, estado="running", parametros={})
        job_model.objects.get.return_value = job
        claim = job_model.objects.filter.return_value
        claim.update.return_value = 0

        _run_scraping(87)

        claim.update.assert_called_once()
        job.refresh_from_db.assert_not_called()

        instantiate_skill.assert_not_called()
    def test_facebook_auth_failure_is_not_retried(self):
        result = SimpleNamespace(
            message=(
                "FACEBOOK_AUTH_REQUIRED: Azure no tiene una sesión autorizada"
            )
        )
        self.assertTrue(_error_camoufox_no_reintentable(result))

    def test_missing_linux_library_is_not_retried(self):
        result = SimpleNamespace(
            message=(
                "XPCOMGlueLoad error: libgtk-3.so.0: "
                "cannot open shared object file"
            )
        )
        self.assertTrue(_error_camoufox_no_reintentable(result))

    def test_transient_browser_failure_can_be_retried(self):
        result = SimpleNamespace(message="Timeout esperando respuesta del portal")
        self.assertFalse(_error_camoufox_no_reintentable(result))

    def test_success_without_detected_properties_is_not_valid(self):
        result = SimpleNamespace(
            success=True,
            data={"total": 0, "nuevas": 0, "actualizadas": 0},
        )

        self.assertFalse(_resultado_portal_valido(result))

    def test_success_with_detected_properties_is_valid(self):
        result = SimpleNamespace(
            success=True,
            data={"total": 3, "nuevas": 1, "actualizadas": 2},
        )

        self.assertTrue(_resultado_portal_valido(result))

    @patch("ingestas.models.ScrapingJob")
    def test_counter_consolidation_saves_detected_total(self, job_model):
        job = MagicMock(id=7)
        base = {
            "total_propiedades": 10,
            "procesadas": 10,
            "nuevas": 3,
            "actualizadas": 7,
            "errores": 0,
        }

        _actualizar_contadores(
            job,
            {
                "total": 6,
                "nuevas": 2,
                "actualizadas": 3,
                "errores": 1,
            },
            base,
        )

        job_model.objects.filter.assert_called_once_with(id=7)
        job_model.objects.filter.return_value.update.assert_called_once_with(
            total_propiedades=16,
            procesadas=16,
            nuevas=5,
            actualizadas=10,
            errores=1,
        )

    @patch(
        "intelligence.skills.scrapi.scraper_remax._ejecutar_scraping",
        return_value=[],
    )
    def test_remax_empty_result_is_error(self, _scrape):
        result = ScraperRemaxSkill().execute({})
        self.assertFalse(result.success)

    @patch(
        "intelligence.skills.scrapi.scraper_urbania._ejecutar_scraping",
        return_value=[],
    )
    def test_urbania_empty_result_is_error(self, _scrape):
        result = ScraperUrbaniaSkill().execute({})
        self.assertFalse(result.success)

    @patch(
        "intelligence.skills.scrapi.scraper_urbania.guardar_propiedades",
        return_value={"total": 1, "nuevas": 1, "actualizadas": 0, "errores": 0},
    )
    @patch("intelligence.skills.scrapi.scraper_urbania._ejecutar_scraping")
    def test_urbania_wires_incremental_progress_and_checkpoint(
        self, scrape, _guardar
    ):
        lote = [{"id_origen": "urbania-1"}]
        progreso = MagicMock(return_value=True)

        def ejecutar(_max_paginas, **kwargs):
            kwargs["batch_callback"](lote)
            return lote

        scrape.side_effect = ejecutar
        result = ScraperUrbaniaSkill().execute(
            {"max_paginas": 5, "start_page": 3},
            context={"progress_callback": progreso},
        )

        self.assertTrue(result.success)
        self.assertEqual(result.data["total"], 1)
        _, kwargs = scrape.call_args
        self.assertEqual(kwargs["start_page"], 3)
        self.assertIs(kwargs["progress_callback"], progreso)
        self.assertTrue(callable(kwargs["batch_callback"]))
    @patch(
        "intelligence.skills.scrapi.scraper_adondevivir._ejecutar_scraping",
        return_value=[],
    )
    def test_adondevivir_empty_result_is_error(self, _scrape):
        result = ScraperAdondevivirSkill().execute({})
        self.assertFalse(result.success)
