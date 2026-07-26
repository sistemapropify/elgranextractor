from datetime import date
from unittest.mock import Mock, patch

from django.http import JsonResponse
from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from routers import DefaultRouter, PropifaiRouter

from .models import AnalysisRun
from .services import normalized_period
from .views import management_summary_api


class LeadIntelligenceRoutingTests(SimpleTestCase):
    def test_models_are_never_routed_to_crm_database(self):
        self.assertIsNone(PropifaiRouter().db_for_read(AnalysisRun))
        self.assertIsNone(PropifaiRouter().db_for_write(AnalysisRun))
        self.assertEqual(DefaultRouter().db_for_read(AnalysisRun), "default")
        self.assertEqual(DefaultRouter().db_for_write(AnalysisRun), "default")
        self.assertFalse(
            PropifaiRouter().allow_migrate(
                "propifai", AnalysisRun._meta.app_label, "analysisrun"
            )
        )

    def test_existing_menu_url_points_to_management_dashboard(self):
        self.assertEqual(reverse("analisis_crm:dashboard"), "/analisis-crm/")
        self.assertEqual(
            reverse("analisis_crm:management_summary_api"),
            "/analisis-crm/api/management/summary/",
        )
        self.assertEqual(
            reverse("analisis_crm:cohorts"),
            "/analisis-crm/cohortes/",
        )


class PeriodTests(SimpleTestCase):
    def test_period_is_normalized_and_limited_to_90_days(self):
        date_from, date_to = normalized_period("2025-01-01", "2026-07-24")
        self.assertEqual(date_to, date(2026, 7, 24))
        self.assertEqual((date_to - date_from).days, 90)

    def test_reversed_period_is_swapped(self):
        date_from, date_to = normalized_period("2026-07-24", "2026-07-01")
        self.assertEqual(date_from, date(2026, 7, 1))
        self.assertEqual(date_to, date(2026, 7, 24))


class ManagementApiTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch("lead_intelligence.views.get_management_dashboard")
    def test_summary_api_serializes_cohort_dates(self, dashboard_mock):
        dashboard_mock.return_value = {
            "generated_at": Mock(isoformat=Mock(return_value="2026-07-24T08:00:00")),
            "overview": {"total_leads": 60},
            "selected_cohort": {"entered": 60},
            "cohorts": [{"cohort_date": date(2026, 7, 24), "total": 60}],
            "data_quality": {},
            "qualification_ready": False,
        }
        request = self.factory.get(
            "/analisis-crm/api/management/summary/?from=2026-07-24&to=2026-07-24&cohort=2026-07-24"
        )
        request.user = Mock(is_authenticated=False, is_superuser=False)
        request.current_user = Mock()
        request.current_user.intelligence_profile = Mock(
            level=5, allowed_domains=["gerencia"]
        )

        response = management_summary_api(request)

        self.assertIsInstance(response, JsonResponse)
        self.assertContains(response, '"cohort_date": "2026-07-24"')

    @patch("lead_intelligence.views.get_management_dashboard")
    def test_summary_api_rejects_non_management_profile(self, dashboard_mock):
        request = self.factory.get("/analisis-crm/api/management/summary/")
        request.user = Mock(is_authenticated=False, is_superuser=False)
        request.current_user = Mock()
        request.current_user.intelligence_profile = Mock(
            level=1, allowed_domains=["publico"]
        )

        response = management_summary_api(request)

        self.assertEqual(response.status_code, 403)
        dashboard_mock.assert_not_called()
