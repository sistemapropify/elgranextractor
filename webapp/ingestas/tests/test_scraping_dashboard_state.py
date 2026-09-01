import json
from unittest.mock import MagicMock, patch

from django.template.loader import get_template
from django.test import RequestFactory, SimpleTestCase, override_settings

from ingestas.views import (
    ScrapingControlView,
    _launch_scraping_job,
    _reconcile_stale_scraping_jobs,
)


class ScrapingDashboardStateTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_dashboard_template_compiles(self):
        self.assertIsNotNone(get_template("ingestas/scraping_dashboard.html"))

    @patch("ingestas.views.ScrapingJob")
    def test_reconcile_marks_old_active_jobs_as_error(self, job_model):
        queryset = MagicMock()
        queryset.filter.return_value = queryset
        queryset.exclude.return_value = queryset
        queryset.values_list.return_value = queryset
        queryset.distinct.return_value = [7, 8]
        queryset.update.return_value = 2
        job_model.objects.filter.return_value = queryset

        updated = _reconcile_stale_scraping_jobs()

        self.assertEqual(updated, 2)
        idle_filters = job_model.objects.filter.call_args_list[0].kwargs
        self.assertEqual(idle_filters["estado"], "idle")
        active_filters = job_model.objects.filter.call_args_list[1].kwargs
        self.assertEqual(active_filters["estado__in"], ("running", "paused"))
        queryset.filter.assert_called_once()
        update = queryset.update.call_args.kwargs
        self.assertEqual(update["estado"], "error")
        self.assertIsNone(update["execution_token"])
        self.assertIsNotNone(update["completado_en"])
        self.assertIn("huérfana", update["mensaje_error"])

    @override_settings(CELERY_BROKER_URL="memory://")
    @patch("ingestas.views.threading.Thread")
    def test_memory_broker_uses_local_thread(self, thread_class):
        thread = thread_class.return_value

        mode = _launch_scraping_job(42)

        self.assertEqual(mode, "thread")
        thread_class.assert_called_once()
        thread.start.assert_called_once_with()

    @override_settings(
        CELERY_BROKER_URL="redis://broker:6379/0",
        SCRAPING_EXECUTION_MODE="celery",
    )
    @patch("colas.scraping_tasks.scraping_task.apply_async")
    def test_explicit_celery_mode_uses_celery(self, apply_async):
        mode = _launch_scraping_job(42)

        self.assertEqual(mode, "celery")
        apply_async.assert_called_once_with(args=(42,), retry=False)

    @override_settings(
        CELERY_BROKER_URL="redis://broker:6379/0",
        SCRAPING_EXECUTION_MODE="thread",
    )
    @patch("ingestas.views.threading.Thread")
    def test_redis_url_does_not_force_blocking_celery_dispatch(self, thread_class):
        mode = _launch_scraping_job(42)

        self.assertEqual(mode, "thread")
        thread_class.return_value.start.assert_called_once_with()

    @patch("ingestas.views.ScrapingJob")
    def test_pause_requires_running_job(self, job_model):
        queryset = MagicMock()
        queryset.update.return_value = 1
        job_model.objects.filter.return_value = queryset
        request = self.factory.post(
            "/ingestas/scraping/control/",
            {"action": "pause", "job_id": "7"},
        )

        response = ScrapingControlView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        job_model.objects.filter.assert_called_once_with(
            id="7", estado="running"
        )
        queryset.update.assert_called_once_with(estado="paused")

    @patch("ingestas.views._terminate_scraping_browsers")
    @patch("ingestas.views.ScrapingJob")
    def test_stop_sets_completion_timestamp(self, job_model, terminate_browsers):
        terminate_browsers.return_value = 2
        queryset = MagicMock()
        queryset.update.return_value = 1
        job_model.objects.filter.return_value = queryset
        request = self.factory.post(
            "/ingestas/scraping/control/",
            {"action": "stop", "job_id": "7"},
        )

        response = ScrapingControlView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        update = queryset.update.call_args.kwargs
        self.assertEqual(update["estado"], "stopped")
        self.assertIsNone(update["execution_token"])
        self.assertIsNotNone(update["completado_en"])
        self.assertEqual(json.loads(response.content)["browsers_terminated"], 2)
        terminate_browsers.assert_called_once_with()
