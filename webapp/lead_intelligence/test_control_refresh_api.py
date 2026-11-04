import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import Client, SimpleTestCase
from django.urls import reverse


class LeadControlRefreshApiTests(SimpleTestCase):
    URL_NAME = "analisis_crm:control_refresh_lead"

    def url(self):
        return reverse(self.URL_NAME)

    def post(self, payload, key="clave-test"):
        headers = {"HTTP_X_ANALYTICS_API_KEY": key} if key is not None else {}
        return Client().post(
            self.url(),
            data=json.dumps(payload).encode(),
            content_type="application/json",
            **headers,
        )

    def test_route_resolves(self):
        self.assertEqual(
            self.url(),
            "/api/control/refresh-lead/",
        )

    @patch.dict("os.environ", {"ANALYTICS_BRIDGE_API_KEY": "clave-test"})
    def test_requires_api_key(self):
        self.assertEqual(
            self.post({"lead_id": 5726}, key=None).status_code,
            403,
        )
        self.assertEqual(
            self.post({"lead_id": 5726}, key="incorrecta").status_code,
            403,
        )

    @patch.dict("os.environ", {"ANALYTICS_BRIDGE_API_KEY": "clave-test"})
    def test_rejects_invalid_lead_id(self):
        self.assertEqual(self.post({}).status_code, 400)
        self.assertEqual(self.post({"lead_id": 0}).status_code, 400)
        self.assertEqual(self.post({"lead_id": "abc"}).status_code, 400)

    @patch.dict("os.environ", {"ANALYTICS_BRIDGE_API_KEY": "clave-test"})
    @patch("lead_intelligence.control_views.observe")
    @patch("lead_intelligence.control_views.tick")
    @patch("lead_intelligence.control_views.source_snapshot")
    def test_requires_triggering_message_to_be_visible(
        self, source_snapshot, tick, observe
    ):
        source_snapshot.return_value = {
            "lead_id": 5726,
            "messages": [{"id": 100, "sender": "lead"}],
        }

        response = self.post({"lead_id": 5726, "message_id": 101})

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["status"], "message_not_visible")
        observe.assert_not_called()
        tick.assert_not_called()

    @patch.dict(
        "os.environ",
        {"ANALYTICS_BRIDGE_API_KEY": "clave-test"},
    )
    @patch("lead_intelligence.durable_jobs.wake_durable_worker")
    @patch("lead_intelligence.durable_jobs.enqueue_durable_job")
    @patch("lead_intelligence.control_views.send_pending")
    @patch("lead_intelligence.control_views.enabled", return_value=False)
    @patch("lead_intelligence.control_views.tick")
    @patch("lead_intelligence.control_views.policy")
    @patch("lead_intelligence.control_views.observe")
    @patch("lead_intelligence.control_views.create_obligation")
    @patch("lead_intelligence.control_views.source_snapshot")
    def test_refreshes_only_the_triggering_lead(
        self,
        source_snapshot,
        create_obligation,
        observe,
        policy,
        tick,
        _enabled,
        send_pending,
        enqueue,
        wake,
    ):
        observed_at = datetime(2026, 11, 4, 18, 33, 52, tzinfo=timezone.utc)
        source_snapshot.return_value = {
            "lead_id": 5726,
            "agent_id": None,
            "status_name": "Nuevo",
            "messages": [{"id": 101, "sender": "agent"}],
        }
        obligations = MagicMock()
        obligations.filter.return_value.select_related.return_value = []
        observe.return_value = SimpleNamespace(
            quality="valid",
            observed_at=observed_at,
            active=True,
            obligations=obligations,
        )
        enqueue.return_value = (SimpleNamespace(pk=88), True)

        response = self.post({"lead_id": 5726, "message_id": 101})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["lead_id"], 5726)
        self.assertEqual(response.json()["analysis_job_id"], 88)
        source_snapshot.assert_called_once_with(5726)
        tick.assert_called_once_with(lead_id=5726)
        kind, payload, dedupe_key = enqueue.call_args.args
        self.assertEqual(kind, "lead_analysis")
        self.assertEqual(payload, {"lead_id": 5726, "workers": 1})
        self.assertTrue(dedupe_key.startswith("lead-analysis:5726:"))
        wake.assert_called_once_with()
        send_pending.assert_not_called()

