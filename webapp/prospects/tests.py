from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from .crm_alerts import sync_crm_visit_alerts
from .mobile_api import (
    MobilePrincipal,
    mobile_crm_alerts,
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
