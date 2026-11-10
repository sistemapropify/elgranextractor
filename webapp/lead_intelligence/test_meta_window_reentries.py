import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from django.test import SimpleTestCase

from lead_intelligence.conversation_analysis import meta_window_reentries
from lead_intelligence.services import get_meta_window_reentries


NOW = datetime(2026, 11, 10, 13, tzinfo=timezone.utc)


def message(message_id, sender, text, minutes, sender_id=None):
    return {
        "id": message_id,
        "sender": sender,
        "sender_id": sender_id,
        "sender_name": "Lissy Rondon Pastor" if sender == "agent" else "Lead",
        "text": text,
        "timestamp": (NOW + timedelta(minutes=minutes)).isoformat(),
    }


class MetaWindowReentryTests(SimpleTestCase):
    def test_reentry_requires_more_than_24_hours_since_previous_lead_message(self):
        messages = [
            {"timestamp": NOW, "sender": "lead", "text": "Hola"},
            {
                "timestamp": NOW + timedelta(hours=23),
                "sender": "lead",
                "text": "Sigo interesado",
            },
            {
                "timestamp": NOW + timedelta(hours=49),
                "sender": "lead",
                "text": "Volví",
            },
        ]
        events = meta_window_reentries(messages)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["reentry_message"]["text"], "Volví")
        self.assertEqual(events[0]["gap_seconds"], 26 * 60 * 60)

    def test_agent_messages_do_not_reset_meta_window(self):
        messages = [
            {"timestamp": NOW, "sender": "lead", "text": "Hola"},
            {
                "timestamp": NOW + timedelta(hours=23),
                "sender": "agent",
                "text": "¿Te ayudo?",
            },
            {
                "timestamp": NOW + timedelta(hours=25),
                "sender": "lead",
                "text": "Sí",
            },
        ]
        events = meta_window_reentries(messages)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["gap_seconds"], 25 * 60 * 60)
        self.assertEqual(
            events[0]["window_closed_at"],
            NOW + timedelta(hours=24),
        )

    @patch("lead_intelligence.services._load_user_logins", return_value={46: "lissy"})
    @patch("lead_intelligence.services._lead_result_rows")
    def test_report_maps_responder_to_propify_login(self, lead_rows, _user_logins):
        lead_rows.return_value = [
            {
                "id": 5997,
                "chat_history": json.dumps(
                    [
                        message(1, "lead", "Hola", 0),
                        message(2, "agent", "Respuesta inicial", 5, 46),
                        message(3, "lead", "Volví después", 26 * 60),
                        message(4, "agent", "Te atiendo", 26 * 60 + 4, 46),
                    ]
                ),
                "first_name": "Ana",
                "last_name": "Pérez",
                "business_name": "",
                "agent_name": "Lissy Rondon Pastor",
                "agent_username": "lissy",
                "status_name": "Contactado/Activo",
                "campaign_name": "PROP000321",
                "phone": "+51999999999",
                "entered_at": NOW,
            }
        ]
        result = get_meta_window_reentries()
        self.assertEqual(result["total_reentries"], 1)
        item = result["reentries"][0]
        self.assertEqual(item["responder_login"], "lissy")
        self.assertEqual(item["responder_name"], "Lissy Rondon Pastor")
        self.assertEqual(item["response_label"], "4 min")
        self.assertEqual(result["responded_count"], 1)

