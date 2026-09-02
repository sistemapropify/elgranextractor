from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from .crm_alerts import sync_crm_visit_alerts
from .mobile_api import (
    MobilePrincipal,
    mobile_crm_alerts,
    mobile_crm_alert_detail,
    mobile_login,
    mobile_notification_device,
    mobile_schema_health,
)
from .models import CrmVisitIntentAlert, MobileNotificationDevice, MobileProspectSession, MobileProspectUser


class MobileLoginApiTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    @patch("prospects.mobile_api.requests.post")
    def test_propify_login_creates_an_independent_prometeo_session(self, propify_post):
        propify_post.return_value.status_code = 200
        request = self.factory.post(
            "/prospects/api/mobile/login/",
            {"username": "agente", "password": "secreto"},
            format="json",
        )

        response = mobile_login(request)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["access"])
        self.assertTrue(MobileProspectSession.objects.filter(user__username="agente").exists())

    def test_mobile_schema_health_checks_alert_tables_and_permission_column(self):
        request = self.factory.get("/prospects/api/mobile/schema-health/")

        response = mobile_schema_health(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"status": "ok"})


class MobileCrmAlertApiTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.supervisor = MobileProspectUser.objects.create(
            username="supervisor",
            can_view_crm_alerts=True,
        )
        self.regular = MobileProspectUser.objects.create(username="agente")

    def _authenticate(self, request, user):
        force_authenticate(request, user=MobilePrincipal(user))
        return request

    @patch("prospects.mobile_api.sync_crm_visit_alerts")
    def test_supervisor_reads_global_pending_alerts(self, sync_mock):
        CrmVisitIntentAlert.objects.create(
            source_lead_id=42,
            agent_name="Agente Uno",
            detected_at=timezone.now(),
        )
        request = self._authenticate(
            self.factory.get("/prospects/api/mobile/crm-alerts/?status=pending"),
            self.supervisor,
        )

        response = mobile_crm_alerts(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["lead_id"], 42)
        sync_mock.assert_called_once()

    @patch("prospects.mobile_api.sync_crm_visit_alerts")
    def test_alerts_before_operational_start_are_not_listed(self, sync_mock):
        CrmVisitIntentAlert.objects.create(
            source_lead_id=41,
            agent_name="Agente antiguo",
            detected_at=timezone.make_aware(datetime(2026, 8, 23, 23, 59)),
        )
        CrmVisitIntentAlert.objects.create(
            source_lead_id=42,
            agent_name="Agente vigente",
            detected_at=timezone.make_aware(datetime(2026, 8, 24, 0, 0)),
        )
        request = self._authenticate(
            self.factory.get("/prospects/api/mobile/crm-alerts/?status=pending"),
            self.supervisor,
        )

        response = mobile_crm_alerts(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["lead_id"], 42)
        self.assertNotIn("evidence", response.data["results"][0])

    @patch("prospects.mobile_api.get_crm_lead_conversation")
    def test_alert_detail_contains_complete_conversation(self, conversation_mock):
        alert = CrmVisitIntentAlert.objects.create(
            source_lead_id=90,
            detected_at=timezone.now(),
        )
        conversation_mock.return_value = [
            {"sender": "lead", "text": "Quiero visitar", "timestamp": timezone.now().isoformat()},
            {"sender": "agent", "text": "Coordinemos", "timestamp": timezone.now().isoformat()},
        ]
        request = self._authenticate(
            self.factory.get(f"/prospects/api/mobile/crm-alerts/{alert.pk}/"),
            self.supervisor,
        )

        response = mobile_crm_alert_detail(request, alert.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["conversation"]), 2)
        self.assertIn("evidence", response.data["alert"])

    def test_regular_user_cannot_open_control_module(self):
        request = self._authenticate(
            self.factory.get("/prospects/api/mobile/crm-alerts/"),
            self.regular,
        )
        response = mobile_crm_alerts(request)
        self.assertEqual(response.status_code, 403)

    def test_supervisor_registers_firebase_installation(self):
        request = self._authenticate(
            self.factory.post(
                "/prospects/api/mobile/notification-device/",
                {"registration_id": "fid-example", "target_type": "fid"},
                format="json",
            ),
            self.supervisor,
        )
        response = mobile_notification_device(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            MobileNotificationDevice.objects.filter(
                user=self.supervisor,
                registration_id="fid-example",
                active=True,
            ).exists()
        )


class CrmAlertSynchronizationTests(TestCase):
    @patch("prospects.crm_alerts.send_new_alert_push")
    @patch("prospects.crm_alerts.connections")
    @patch("prospects.crm_alerts.get_visit_intent_leads")
    def test_new_intention_is_persisted_once_and_notified(self, leads_mock, connections_mock, push_mock):
        detected_at = timezone.now() - timedelta(minutes=2)
        leads_mock.return_value = [{
            "lead_id": 91,
            "agent_id": 8,
            "agent_name": "Agente Dos",
            "contact_name": "Contacto",
            "phone": "999999999",
            "property_id": 3,
            "property_code": "P-3",
            "property_title": "Propiedad",
            "visit_intent_at": detected_at.isoformat(),
            "visit_intent_evidence": [{"text": "Quiero visitarla", "timestamp": detected_at.isoformat()}],
        }]
        cursor = MagicMock()
        cursor.fetchall.return_value = [(91, "[]")]
        connections_mock.__getitem__.return_value.cursor.return_value.__enter__.return_value = cursor

        first = sync_crm_visit_alerts()
        second = sync_crm_visit_alerts()

        self.assertEqual(first["created"], 1)
        self.assertEqual(second["created"], 0)
        self.assertEqual(CrmVisitIntentAlert.objects.filter(source_lead_id=91).count(), 1)
        push_mock.assert_called_once()

    @patch("prospects.crm_alerts.send_new_alert_push")
    @patch("prospects.crm_alerts.connections")
    @patch("prospects.crm_alerts.get_visit_intent_leads")
    def test_intentions_before_august_24_are_ignored(self, leads_mock, connections_mock, push_mock):
        leads_mock.return_value = [{
            "lead_id": 15,
            "visit_intent_at": "2026-08-23T23:59:59-05:00",
            "visit_intent_evidence": [{"text": "Visita antigua"}],
        }]

        result = sync_crm_visit_alerts(date_from=date(2026, 8, 1), date_to=date(2026, 9, 2))

        self.assertEqual(result["created"], 0)
        self.assertFalse(CrmVisitIntentAlert.objects.filter(source_lead_id=15).exists())
        connections_mock.__getitem__.assert_not_called()
        push_mock.assert_not_called()
