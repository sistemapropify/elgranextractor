import json
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from lead_intelligence.conversation_analysis import analyze_chat_history
from lead_intelligence.models import LeadConversationAssessment
from lead_intelligence.services import _recontact_assessment, get_lead_results


NOW = datetime(2026, 11, 6, 15, tzinfo=timezone.utc)


def assessment(qualified="not_confirmed", visit="not_confirmed", confidence=0.95):
    return SimpleNamespace(
        qualified_status=qualified,
        visit_intent_status=visit,
        qualified_confidence=confidence,
        visit_intent_confidence=confidence,
    )


def analysis(messages):
    return analyze_chat_history(json.dumps(messages))


def message(sender, text, minutes):
    return {
        "id": f"{sender}-{minutes}",
        "sender": sender,
        "text": text,
        "timestamp": (NOW - timedelta(minutes=minutes)).isoformat(),
    }


class RecontactPriorityTests(SimpleTestCase):
    def test_generic_information_without_confirmed_interest_is_nurture(self):
        data = analysis([
            message("lead", "Quiero más información", 60),
            message("agent", "Es un terreno de 300 m²", 30),
        ])
        result = _recontact_assessment(
            data,
            assessment(),
            {"status_name": "Contactado/Activo", "budget": None, "timeline": ""},
            now=NOW,
        )
        self.assertEqual(result["status"], "nurture")
        self.assertEqual(result["channel"], "whatsapp")
        self.assertIn("interés comercial concreto", result["reason"])

    def test_confirmed_interest_becomes_call(self):
        data = analysis([
            message("lead", "Me interesa la propiedad y quiero visitarla", 120),
            message("agent", "Podemos coordinar mañana", 90),
            message("lead", "Sí, ¿a qué hora?", 60),
            message("agent", "Te propongo las 10", 30),
        ])
        result = _recontact_assessment(
            data,
            assessment("confirmed", "confirmed", 0.9),
            {"status_name": "Interesado en compra", "budget": 100000, "timeline": "este mes"},
            now=NOW,
        )
        self.assertEqual(result["status"], "call_now")
        self.assertEqual(result["channel"], "call")
        self.assertGreaterEqual(result["score"], 60)

    def test_unanswered_lead_is_operational_response_not_remarketing(self):
        data = analysis([
            message("lead", "Quiero información", 90),
            message("agent", "Claro", 60),
            message("lead", "¿Cuál es el precio?", 15),
        ])
        result = _recontact_assessment(
            data,
            assessment(),
            {"status_name": "Contactado/Activo"},
            now=NOW,
        )
        self.assertEqual(result["status"], "waiting_response")
        self.assertEqual(result["channel"], "none")

    def test_opt_out_is_never_recontacted(self):
        data = analysis([
            message("lead", "No me interesa, no me escribas más", 90),
            message("agent", "Entendido", 60),
        ])
        result = _recontact_assessment(
            data,
            assessment(),
            {"status_name": "Contactado/Activo"},
            now=NOW,
        )
        self.assertEqual(result["status"], "do_not_contact")

    def test_pending_context_analysis_is_not_a_candidate(self):
        data = analysis([
            message("lead", "Hola", 90),
            message("agent", "Hola", 60),
        ])
        result = _recontact_assessment(data, None, {"status_name": "Nuevo"}, now=NOW)
        self.assertEqual(result["status"], "pending_analysis")

    @patch("lead_intelligence.services._prepare_lead_result")
    @patch("lead_intelligence.services._assessment_map", return_value={})
    @patch(
        "lead_intelligence.services._lead_result_rows",
        return_value=[
            {"id": 1, "chat_history": "[]"},
            {"id": 2, "chat_history": "[]"},
        ],
    )
    def test_existing_results_filter_by_recontact_group(
        self, _rows, _assessments, prepare
    ):
        prepare.side_effect = [
            {"id": 1, "recontact_status": "call_now"},
            {"id": 2, "recontact_status": "nurture"},
        ]
        result = get_lead_results(
            date(2026, 11, 1),
            date(2026, 11, 6),
            "entered",
            recontact="call_now",
        )
        self.assertEqual([lead["id"] for lead in result["leads"]], [1])
        self.assertEqual(result["recontact"], "call_now")

    @patch("lead_intelligence.services._prepare_lead_result")
    @patch("lead_intelligence.services._assessment_map", return_value={})
    @patch(
        "lead_intelligence.services._lead_result_rows",
        return_value=[
            {"id": 1, "chat_history": "[]"},
            {"id": 2, "chat_history": "[]"},
            {"id": 3, "chat_history": "[]"},
        ],
    )
    def test_funnel_queue_uses_official_stages_and_numbers_results(
        self, _rows, _assessments, prepare
    ):
        prepare.side_effect = [
            {
                "id": 1,
                "entered": True,
                "contacted": True,
            },
            {
                "id": 2,
                "entered": True,
                "contacted": True,
                "bidirectional": True,
            },
            {
                "id": 3,
                "entered": True,
                "contacted": True,
                "bidirectional": True,
                "qualified": True,
            },
        ]
        result = get_lead_results(
            date(2026, 11, 1),
            date(2026, 11, 6),
            "entered",
            order="funnel",
        )
        self.assertEqual(
            [lead["id"] for lead in result["leads"]],
            [3, 2, 1],
        )
        self.assertEqual(
            [lead["queue_rank"] for lead in result["leads"]],
            [1, 2, 3],
        )
        self.assertEqual(
            [lead["funnel_stage_label"] for lead in result["leads"]],
            ["Calificados por IA", "Bidireccionales", "Contactados"],
        )

