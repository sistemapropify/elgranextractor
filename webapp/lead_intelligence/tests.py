import inspect
import json
import re
from datetime import date, datetime, timedelta, timezone as datetime_timezone
from pathlib import Path
from unittest.mock import Mock, patch

from django.http import JsonResponse
from django.template.loader import get_template
from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from routers import DefaultRouter, PropifaiRouter

from .attention_quality import (
    first_exchange,
    possible_missing_media,
    response_wait_seconds,
    template_signature,
    validate_initial_request_items,
)
from .conversation_analysis import (
    analyze_chat_history,
    has_interest,
    lima_date,
    milestone_within_days,
)
from .contextual_analysis import analyze_conversation_context
from .models import (
    AnalysisRun,
    LeadConversationAssessment,
    LeadConversationReview,
)
from .services import (
    _lead_result_rows,
    _waiting_attention,
    build_daily_incoming,
    get_management_dashboard,
    normalized_period,
    _responsible_at,
    save_conversation_review,
)
from .views import management_summary_api


class LeadIntelligenceRoutingTests(SimpleTestCase):
    def test_models_are_never_routed_to_crm_database(self):
        self.assertIsNone(PropifaiRouter().db_for_read(AnalysisRun))
        self.assertIsNone(PropifaiRouter().db_for_write(AnalysisRun))
        self.assertEqual(DefaultRouter().db_for_read(AnalysisRun), "default")
        self.assertEqual(DefaultRouter().db_for_write(AnalysisRun), "default")
        self.assertIsNone(
            PropifaiRouter().db_for_write(LeadConversationAssessment)
        )
        self.assertEqual(
            DefaultRouter().db_for_write(LeadConversationAssessment), "default"
        )
        self.assertIsNone(
            PropifaiRouter().db_for_write(LeadConversationReview)
        )
        self.assertEqual(
            DefaultRouter().db_for_write(LeadConversationReview), "default"
        )
        self.assertFalse(
            PropifaiRouter().allow_migrate(
                "propifai", AnalysisRun._meta.app_label, "analysisrun"
            )
        )

    def test_crm_analytics_service_contains_only_read_statements(self):
        source = inspect.getsource(get_management_dashboard)
        self.assertNotRegex(
            source,
            re.compile(r"\b(?:INSERT|UPDATE|DELETE|MERGE|ALTER|DROP|CREATE)\b"),
        )
        self.assertNotIn("lead_status" + "_history", source)
        result_source = inspect.getsource(_lead_result_rows)
        self.assertNotRegex(
            result_source,
            re.compile(r"\b(?:INSERT|UPDATE|DELETE|MERGE|ALTER|DROP|CREATE)\b"),
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
        self.assertEqual(
            reverse("analisis_crm:lead_results"),
            "/analisis-crm/resultados/",
        )
        self.assertEqual(
            reverse("analisis_crm:lead_conversation", args=[2411]),
            "/analisis-crm/resultados/2411/",
        )
        self.assertEqual(
            reverse("analisis_crm:attention_quality"),
            "/analisis-crm/calidad-atencion/",
        )
        self.assertEqual(
            reverse("analisis_crm:analysis_quality"),
            "/analisis-crm/calidad-motor/",
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

    def test_daily_incoming_includes_days_without_leads(self):
        metrics = {
            date(2026, 7, 1): [{}, {}],
            date(2026, 7, 3): [{}],
        }
        self.assertEqual(
            build_daily_incoming(metrics, date(2026, 7, 1), date(2026, 7, 3)),
            [
                {"date": "2026-07-01", "count": 2},
                {"date": "2026-07-02", "count": 0},
                {"date": "2026-07-03", "count": 1},
            ],
        )


class ConversationAnalysisTests(SimpleTestCase):
    @staticmethod
    def message(sender, text, minute=0, timestamp=None):
        return {
            "sender": sender,
            "text": text,
            "timestamp": timestamp or f"2026-07-27T20:{minute:02d}:00+00:00",
        }

    def test_empty_json_variants(self):
        for raw in (None, "", "   ", "[]"):
            with self.subTest(raw=raw):
                result = analyze_chat_history(raw)
                self.assertTrue(result["valid_json"])
                self.assertEqual(result["total_messages"], 0)

    def test_invalid_json(self):
        result = analyze_chat_history("{not-json")
        self.assertFalse(result["valid_json"])
        self.assertEqual(result["total_messages"], 0)

    def test_only_lead_messages_are_unattended(self):
        result = analyze_chat_history(
            '[{"sender":"lead","text":"Hola","timestamp":"2026-07-27T20:00:00Z"}]'
        )
        self.assertTrue(result["unattended"])
        self.assertFalse(result["contacted"])

    def test_unanswered_lead_turn_over_24_hours_is_attention_overdue(self):
        analysis = analyze_chat_history(
            [
                self.message("lead", "Buenas tardes", timestamp="2026-07-27T20:00:00Z"),
                self.message("agent", "¿En qué puedo ayudar?", timestamp="2026-07-27T20:05:00Z"),
                self.message("lead", "¿Tiene título?", timestamp="2026-07-27T21:00:00Z"),
            ]
        )
        waiting = _waiting_attention(
            analysis,
            datetime(2026, 7, 29, 22, 0, tzinfo=datetime_timezone.utc),
        )
        self.assertTrue(waiting["attention_overdue"])
        self.assertEqual(waiting["unattended_seconds"], 49 * 60 * 60)
        self.assertEqual(waiting["unattended_label"], "2 d 1 h")

    def test_answered_conversation_is_not_attention_overdue(self):
        analysis = analyze_chat_history(
            [
                self.message("lead", "¿Tiene título?", timestamp="2026-07-27T21:00:00Z"),
                self.message("agent", "Sí, está inscrito.", timestamp="2026-07-27T21:05:00Z"),
            ]
        )
        waiting = _waiting_attention(
            analysis,
            datetime(2026, 7, 29, 22, 0, tzinfo=datetime_timezone.utc),
        )
        self.assertFalse(waiting["attention_overdue"])
        self.assertIsNone(waiting["unattended_seconds"])

    def test_lead_agent_is_contacted_not_bidirectional(self):
        result = analyze_chat_history(
            [
                self.message("lead", "Hola", 0),
                self.message("agent", "¿Cómo le ayudo?", 5),
            ]
        )
        self.assertTrue(result["contacted"])
        self.assertFalse(result["bidirectional"])
        self.assertFalse(result["qualified"])
        self.assertEqual(result["first_response_seconds"], 300)

    def test_propibot_counts_as_agent_response(self):
        result = analyze_chat_history(
            [
                self.message("lead", "Quiero más detalles", 0),
                self.message("bot", "Claro, te comparto la información", 5),
            ]
        )
        self.assertEqual(result["total_messages"], 2)
        self.assertEqual(result["agent_messages"], 1)
        self.assertEqual(result["last_sender"], "agent")
        self.assertTrue(result["contacted"])
        self.assertFalse(result["unattended"])
        self.assertEqual(result["unknown_senders"], 0)
    def test_lead_agent_lead_is_bidirectional(self):
        result = analyze_chat_history(
            [
                self.message("lead", "Hola", 0),
                self.message("agent", "Buenos días", 5),
                self.message("lead", "Gracias", 8),
            ]
        )
        self.assertTrue(result["bidirectional"])
        self.assertFalse(result["qualified"])

    def test_bidirectional_with_interest_is_qualified(self):
        # Caso conceptual equivalente al lead 2411 / Chatwoot 2673, sin PII.
        result = analyze_chat_history(
            [
                self.message("lead", "Hola", 0),
                self.message("agent", "¿En qué podemos ayudar?", 5),
                self.message("lead", "Me interesa conocer el precio", 8),
            ]
        )
        self.assertTrue(result["bidirectional"])
        self.assertTrue(result["qualified"])
        self.assertTrue(result["has_interest"])

    def test_thanks_only_does_not_qualify(self):
        result = analyze_chat_history(
            [
                self.message("lead", "Hola", 0),
                self.message("agent", "Buenos días", 5),
                self.message("lead", "Ok, gracias", 8),
            ]
        )
        self.assertTrue(result["bidirectional"])
        self.assertFalse(result["qualified"])
        self.assertFalse(has_interest("No me interesa, gracias"))

    def test_out_of_order_messages_are_sorted(self):
        result = analyze_chat_history(
            [
                self.message("lead", "Me interesa el precio", 8),
                self.message("lead", "Hola", 0),
                self.message("agent", "Buenos días", 5),
            ]
        )
        self.assertTrue(result["contacted"])
        self.assertTrue(result["bidirectional"])
        self.assertTrue(result["qualified"])
        self.assertEqual(result["last_sender"], "lead")

    def test_invalid_timestamps_and_incomplete_items_are_ignored(self):
        result = analyze_chat_history(
            [
                {"sender": "lead", "text": "Hola", "timestamp": "ayer"},
                {"sender": "agent", "text": "", "timestamp": "2026-07-27T20:01:00Z"},
                {"sender": "other", "text": "interno", "timestamp": "2026-07-27T20:02:00Z"},
                None,
            ]
        )
        self.assertEqual(result["total_messages"], 0)
        self.assertEqual(result["messages_without_valid_timestamp"], 1)
        self.assertEqual(result["unknown_senders"], 1)

    def test_links_and_image_markers_are_activity(self):
        result = analyze_chat_history(
            [
                self.message("lead", "https://maps.google.com/example", 0),
                self.message("agent", "Recibido", 2),
                self.message("lead", "[imagen]", 3),
            ]
        )
        self.assertEqual(result["total_messages"], 3)
        self.assertTrue(result["bidirectional"])
        self.assertTrue(result["qualified"])
        self.assertFalse(result["visit_intent"])

    def test_agent_visit_offer_without_lead_acceptance_is_not_intent(self):
        result = analyze_chat_history(
            [
                self.message("lead", "Quiero saber la ubicación exacta", 0),
                self.message(
                    "agent",
                    "Podríamos coordinar una visita para que lo vea",
                    2,
                ),
                self.message("lead", "De preferencia con cochera", 4),
            ]
        )
        self.assertFalse(result["visit_intent"])

    def test_lead_accepting_or_proposing_visit_is_intent(self):
        accepted = analyze_chat_history(
            [
                self.message("lead", "Hola", 0),
                self.message("agent", "¿Quiere agendar una visita?", 2),
                self.message("lead", "Sí, de acuerdo", 4),
            ]
        )
        proposed = analyze_chat_history(
            [
                self.message("lead", "Quisiera visitarlo mañana", 0),
            ]
        )
        self.assertTrue(accepted["visit_intent"])
        self.assertTrue(proposed["visit_intent"])

    def test_mixed_naive_and_aware_timestamps_are_utc(self):
        result = analyze_chat_history(
            [
                self.message("lead", "Hola", timestamp="2026-07-24T10:00:00"),
                self.message(
                    "agent", "Claro", timestamp="2026-07-24T10:05:00+00:00"
                ),
            ]
        )
        self.assertEqual(
            result["contacted_at"].utcoffset(),
            datetime_timezone.utc.utcoffset(None),
        )

    def test_response_waits_use_last_message_of_each_lead_turn(self):
        result = analyze_chat_history(
            [
                self.message("lead", "Hola", 0),
                self.message("lead", "Quiero precio y ubicación", 2),
                self.message("agent", "Claro", 7),
                self.message("lead", "¿Tiene cochera?", 10),
                self.message("agent", "Sí", 12),
            ]
        )
        self.assertEqual(response_wait_seconds(result["messages"]), [300, 120])
        lead_block, agent_block = first_exchange(result["messages"])
        self.assertEqual(len(lead_block), 2)
        self.assertEqual(len(agent_block), 1)

    def test_template_signature_ignores_numbers_and_links(self):
        first = template_signature(
            "Hola, tenemos el departamento 200 por $120000. "
            "https://example.com/200"
        )
        second = template_signature(
            "Hola, tenemos el departamento 315 por $99000. "
            "https://example.com/315"
        )
        self.assertEqual(first, second)

    def test_inferred_price_and_location_are_not_initial_requests(self):
        analysis = analyze_chat_history(
            [
                self.message(
                    "lead",
                    "Más info sobre los departamentos de estreno (PROP000200)",
                    0,
                ),
                self.message(
                    "agent",
                    "Tenemos opciones de 2 y 3 habitaciones. ¿Cuál prefiere?",
                    2,
                ),
                self.message("lead", "¿Dónde queda y cuánto cuesta?", 4),
            ]
        )
        grounded, unsupported = validate_initial_request_items(
            analysis["messages"],
            ["Ubicación", "Precio", "Características adicionales"],
        )
        self.assertEqual(grounded, [])
        self.assertEqual(
            unsupported,
            ["Ubicación", "Precio", "Características adicionales"],
        )

    def test_explicit_initial_price_request_is_grounded(self):
        analysis = analyze_chat_history(
            [
                self.message("lead", "¿Cuál es el precio?", 0),
                self.message("agent", "Le confirmo en un momento", 2),
            ]
        )
        grounded, unsupported = validate_initial_request_items(
            analysis["messages"], ["Precio"]
        )
        self.assertEqual(grounded, ["Precio"])
        self.assertEqual(unsupported, [])

    def test_missing_chatwoot_media_makes_text_quality_uncertain(self):
        result = analyze_chat_history(
            [
                self.message("lead", "Se puede ver los ambientes", 0),
                self.message("agent", "Hola, sÃ­ claro", 5),
            ]
        )
        self.assertTrue(possible_missing_media(result["messages"]))

        with_attachment = analyze_chat_history(
            [
                self.message("lead", "Se puede ver los ambientes", 0),
                self.message("agent", "Hola, sÃ­ claro", 5),
                {
                    "sender": "agent",
                    "attachments": [{"type": "image"}],
                    "timestamp": "2026-07-27T20:06:00+00:00",
                },
            ]
        )
        self.assertFalse(possible_missing_media(with_attachment["messages"]))

    def test_responsible_at_uses_assignment_effective_at_response(self):
        changed_at = datetime(
            2026, 7, 16, 19, 43, tzinfo=datetime_timezone.utc
        )
        timeline = [
            {
                "effective_at": changed_at,
                "old_agent_id": None,
                "old_agent_name": "Sin asignar",
                "new_agent_id": 11,
                "new_agent_name": "Valery Gonzales Pastor",
            }
        ]
        before = _responsible_at(
            timeline,
            changed_at - timedelta(minutes=1),
            99,
            "Responsable actual",
        )
        after = _responsible_at(
            timeline,
            changed_at + timedelta(minutes=13),
            99,
            "Responsable actual",
        )
        self.assertIsNone(before["agent_id"])
        self.assertEqual(after["agent_id"], 11)
        self.assertEqual(after["agent_name"], "Valery Gonzales Pastor")


class ContextualAnalysisTests(SimpleTestCase):
    @patch("lead_intelligence.contextual_analysis.LLMService.extract_structured_data")
    def test_generic_more_info_does_not_imply_price_or_location(self, extract_mock):
        extract_mock.return_value = (
            True,
            "ok",
            {
                "qualified_status": "not_confirmed",
                "qualified_confidence": 0.9,
                "qualified_evidence_indices": [],
                "visit_intent_status": "not_confirmed",
                "visit_intent_confidence": 0.9,
                "visit_intent_evidence_indices": [],
                "first_response_status": "adequate",
                "first_response_confidence": 0.9,
                "first_response_agent_indices": [1],
                "lead_request_items": ["Información general"],
                "answered_request_items": ["Información general"],
                "unanswered_request_items": [],
                "reason": "Solicitud genérica atendida.",
            },
        )
        messages = [
            {
                "sender": "lead",
                "text": "Más info sobre los departamentos",
                "timestamp": datetime(
                    2026, 7, 25, tzinfo=datetime_timezone.utc
                ),
            },
            {
                "sender": "agent",
                "text": "Tenemos opciones de 2 y 3 habitaciones. ¿Cuál prefiere?",
                "timestamp": datetime(
                    2026, 7, 25, 1, tzinfo=datetime_timezone.utc
                ),
            },
        ]
        result = analyze_conversation_context(messages)
        prompt = json.loads(extract_mock.call_args.kwargs["text"])
        self.assertIn("NO autorizan a inventar", prompt["explicit_request_rule"])
        self.assertIn("no descompongas 'más info'", extract_mock.call_args.kwargs["schema"]["lead_request_items"])
        self.assertEqual(result["first_response_status"], "adequate")
        self.assertEqual(result["unanswered_request_items"], [])

    @patch("lead_intelligence.contextual_analysis.LLMService.extract_structured_data")
    def test_only_lead_evidence_is_accepted(self, extract_mock):
        extract_mock.return_value = (
            True,
            "ok",
            {
                "qualified_status": "confirmed",
                "qualified_confidence": 0.9,
                "qualified_evidence_indices": [0, 1],
                "visit_intent_status": "confirmed",
                "visit_intent_confidence": 0.8,
                "visit_intent_evidence_indices": [1],
                "reason": "Prueba",
            },
        )
        messages = [
            {
                "sender": "lead",
                "text": "Mi presupuesto es 120000",
                "timestamp": datetime(
                    2026, 7, 25, tzinfo=datetime_timezone.utc
                ),
            },
            {
                "sender": "agent",
                "text": "¿Quiere visitar?",
                "timestamp": datetime(
                    2026, 7, 25, 1, tzinfo=datetime_timezone.utc
                ),
            },
        ]
        result = analyze_conversation_context(messages)
        self.assertEqual(len(result["qualified_evidence"]), 1)
        self.assertEqual(result["qualified_evidence"][0]["sender"], "lead")
        self.assertEqual(result["visit_intent_status"], "ambiguous")

    @patch("lead_intelligence.contextual_analysis.LLMService.extract_structured_data")
    def test_invalid_structured_response_is_retried_once(self, extract_mock):
        extract_mock.side_effect = [
            (False, "JSON inválido", None),
            (
                True,
                "ok",
                {
                    "qualified_status": "not_confirmed",
                    "qualified_confidence": 0.9,
                    "qualified_evidence_indices": [],
                    "visit_intent_status": "not_confirmed",
                    "visit_intent_confidence": 0.9,
                    "visit_intent_evidence_indices": [],
                    "first_response_status": "not_applicable",
                    "first_response_confidence": 1,
                    "reason": "Sin conversación comercial.",
                },
            ),
        ]
        result = analyze_conversation_context([])
        self.assertEqual(result["qualified_status"], "not_confirmed")
        self.assertEqual(extract_mock.call_count, 2)

    @patch("lead_intelligence.contextual_analysis.LLMService.extract_structured_data")
    def test_later_agent_message_cannot_prove_first_response_quality(
        self, extract_mock
    ):
        extract_mock.return_value = (
            True,
            "ok",
            {
                "qualified_status": "not_confirmed",
                "qualified_confidence": 0.9,
                "qualified_evidence_indices": [],
                "visit_intent_status": "not_confirmed",
                "visit_intent_confidence": 0.9,
                "visit_intent_evidence_indices": [],
                "first_response_status": "adequate",
                "first_response_confidence": 0.9,
                "first_response_agent_indices": [3],
                "reason": "Prueba",
            },
        )
        messages = [
            {
                "sender": "lead",
                "text": "¿Cuál es el precio?",
                "timestamp": datetime(
                    2026, 7, 25, tzinfo=datetime_timezone.utc
                ),
            },
            {
                "sender": "agent",
                "text": "Hola, ¿cómo estás?",
                "timestamp": datetime(
                    2026, 7, 25, 1, tzinfo=datetime_timezone.utc
                ),
            },
            {
                "sender": "lead",
                "text": "Pregunté el precio",
                "timestamp": datetime(
                    2026, 7, 25, 2, tzinfo=datetime_timezone.utc
                ),
            },
            {
                "sender": "agent",
                "text": "Cuesta 120000",
                "timestamp": datetime(
                    2026, 7, 25, 3, tzinfo=datetime_timezone.utc
                ),
            },
        ]
        result = analyze_conversation_context(messages)
        self.assertEqual(result["first_response_status"], "ambiguous")
        self.assertEqual(result["first_response_evidence"], [])

    def test_utc_timestamp_is_converted_to_lima_calendar_date(self):
        timestamp = datetime(2026, 7, 28, 2, tzinfo=datetime_timezone.utc)
        self.assertEqual(lima_date(timestamp), date(2026, 7, 27))

    def test_d1_d3_and_d7_windows_use_lima_dates(self):
        cohort = date(2026, 7, 27)
        at_d1 = datetime(2026, 7, 29, 4, tzinfo=datetime_timezone.utc)
        at_d3 = at_d1 + timedelta(days=2)
        at_d7 = at_d1 + timedelta(days=6)
        self.assertTrue(milestone_within_days(cohort, at_d1, 1))
        self.assertFalse(milestone_within_days(cohort, at_d3, 1))
        self.assertTrue(milestone_within_days(cohort, at_d3, 3))
        self.assertTrue(milestone_within_days(cohort, at_d7, 7))
        self.assertFalse(
            milestone_within_days(
                cohort, datetime(2026, 7, 27, 3, tzinfo=datetime_timezone.utc), 7
            )
        )


class ConversationHashVersionTests(SimpleTestCase):
    def test_bot_sender_uses_new_parser_fingerprint(self):
        from .contextual_analysis import conversation_hash

        lead_only = [{"sender": "lead", "text": "Hola"}]
        with_bot = lead_only + [{"sender": "bot", "text": "Hola, te ayudo"}]
        with_agent = lead_only + [{"sender": "agent", "text": "Hola, te ayudo"}]
        self.assertNotEqual(conversation_hash(with_bot), conversation_hash(with_agent))
        self.assertEqual(conversation_hash(lead_only), conversation_hash(lead_only))

class ConversationReviewTests(SimpleTestCase):
    def test_correct_review_copies_current_ai_value(self):
        assessment = Mock(
            source_lead_id=99,
            history_hash="a" * 64,
            analysis_version="context-v2",
            qualified_status="confirmed",
        )
        assessment_query = Mock()
        assessment_query.filter.return_value.first.return_value = assessment
        review_query = Mock()
        saved_review = Mock()
        review_query.update_or_create.return_value = (saved_review, True)

        with (
            patch.object(
                LeadConversationAssessment.objects,
                "using",
                return_value=assessment_query,
            ),
            patch.object(
                LeadConversationReview.objects,
                "using",
                return_value=review_query,
            ),
        ):
            review = save_conversation_review(
                source_lead_id=assessment.source_lead_id,
                history_hash=assessment.history_hash,
                analysis_version=assessment.analysis_version,
                stage="qualified",
                verdict="correct",
                human_value="",
            )

        self.assertIs(review, saved_review)
        defaults = review_query.update_or_create.call_args.kwargs["defaults"]
        self.assertEqual(defaults["ai_value"], "confirmed")
        self.assertEqual(defaults["human_value"], "confirmed")
        self.assertEqual(defaults["verdict"], "correct")


class CohortTemplateTests(SimpleTestCase):
    def test_result_and_conversation_templates_compile(self):
        self.assertIsNotNone(
            get_template("lead_intelligence/lead_results.html")
        )
        self.assertIsNotNone(
            get_template("lead_intelligence/lead_conversation.html")
        )
        self.assertIsNotNone(
            get_template(
                "lead_intelligence/attention_quality_dashboard.html"
            )
        )
        self.assertIsNotNone(
            get_template(
                "lead_intelligence/analysis_quality_dashboard.html"
            )
        )

    def test_daily_page_has_one_calendar_and_no_legacy_metrics(self):
        template_path = (
            Path(__file__).parent
            / "templates"
            / "lead_intelligence"
            / "cohort_dashboard.html"
        )
        content = template_path.read_text(encoding="utf-8")
        self.assertEqual(content.count('type="date"'), 1)
        self.assertNotIn("Activo " + "48 h", content)
        self.assertNotIn("Calificación " + "provisional", content)
        self.assertNotIn("Comparación diaria", content)
        self.assertEqual(content.count("|unlocalize"), 5)

    def test_overview_chart_script_matches_base_template_contract(self):
        template_path = (
            Path(__file__).parent
            / "templates"
            / "lead_intelligence"
            / "overview_dashboard.html"
        )
        content = template_path.read_text(encoding="utf-8")
        extra_js = content.split("{% block extra_js %}", 1)[1].split(
            "{% endblock %}", 1
        )[0]
        self.assertNotIn("<script", extra_js)
        self.assertIn('id="incomingLeadsChart"', content)
        self.assertIn("drawIncomingLeadsChart", extra_js)
        self.assertIn("ctx.setLineDash([7, 5])", extra_js)
        self.assertIn("movingAverages", extra_js)
        self.assertIn("ctx.arc(xAt(index), yAt(value), 3.5", extra_js)
        self.assertIn("Prom. móvil 5 días", extra_js)
        self.assertIn("showChartTooltip", extra_js)
        self.assertIn("canvas.addEventListener('mousemove'", extra_js)
        self.assertIn("canvas.addEventListener('click'", extra_js)


class ManagementApiTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch("lead_intelligence.views.get_management_dashboard")
    def test_summary_api_serializes_cohort_dates(self, dashboard_mock):
        dashboard_mock.return_value = {
            "generated_at": Mock(isoformat=Mock(return_value="2026-07-24T08:00:00")),
            "overview": {"total_leads": 60},
            "incoming_leads": [{"date": "2026-07-24", "count": 60}],
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


class EvaluationChannelsTests(SimpleTestCase):
    """Tests del pipeline de evaluación incremental (canal programada + tiempo real)."""

    def _structural(self, **overrides):
        data = {
            "messages": [{"sender": "lead", "text": "hola"}],
            "contacted": False,
            "bidirectional": False,
            "qualified": False,
            "visit_intent": False,
        }
        data.update(overrides)
        return data

    def test_min_stage_entered_acepta_cualquier_lead(self):
        from .management.commands.analyze_lead_conversations import Command

        self.assertTrue(
            Command._min_stage_ok("entered", self._structural(contacted=False))
        )

    def test_min_stage_contacted_requiere_respuesta_agente(self):
        from .management.commands.analyze_lead_conversations import Command

        self.assertTrue(
            Command._min_stage_ok("contacted", self._structural(contacted=True))
        )
        self.assertFalse(
            Command._min_stage_ok("contacted", self._structural(contacted=False))
        )

    def test_min_stage_bidirectional_requiere_etapa_avanzada(self):
        from .management.commands.analyze_lead_conversations import Command

        self.assertTrue(
            Command._min_stage_ok(
                "bidirectional", self._structural(bidirectional=True)
            )
        )
        self.assertTrue(
            Command._min_stage_ok(
                "bidirectional", self._structural(qualified=True)
            )
        )
        self.assertTrue(
            Command._min_stage_ok(
                "bidirectional", self._structural(visit_intent=True)
            )
        )
        # Un lead solo-contactado NO pasa el filtro de tiempo real (≥bidireccional).
        self.assertFalse(
            Command._min_stage_ok(
                "bidirectional", self._structural(contacted=True)
            )
        )

    def test_assessment_summary_incluye_decisiones(self):
        from .management.commands.analyze_lead_conversations import Command

        summary = Command._assessment_summary(
            {
                "qualified_status": "confirmed",
                "visit_intent_status": "not_confirmed",
                "first_response_status": "adequate",
            }
        )
        self.assertIn("calificación=confirmed", summary)
        self.assertIn("visita=not_confirmed", summary)
        self.assertIn("primeraRespuesta=adequate", summary)

    def test_assessment_summary_vacio_sin_decisiones(self):
        from .management.commands.analyze_lead_conversations import Command

        self.assertEqual(Command._assessment_summary({}), "evaluado")


class AnalysisProgressHistoricalApiTests(SimpleTestCase):
    """Modo histórico de analysis_progress_api (detalle por lead del periodo)."""

    def setUp(self):
        self.factory = RequestFactory()

    @patch("lead_intelligence.models.AnalysisRun.objects")
    @patch("lead_intelligence.models.AnalysisRunStep.objects")
    def test_historical_returns_steps_with_run_type(self, step_objects_mock, run_objects_mock):
        from lead_intelligence.views import analysis_progress_api

        run = Mock(
            pk=1,
            run_type="daily",
            get_run_type_display=Mock(return_value="Diario"),
            started_at=datetime(2026, 8, 10, 9, 0, tzinfo=datetime_timezone.utc),
            status="completed",
            leads_analyzed=3,
            leads_skipped=1,
            leads_failed=0,
            error_summary="",
        )
        step = Mock(
            run_id=1,
            lead_id=123,
            status="analyzed",
            message="calificación=confirmed · visita=confirmed",
            created_at=datetime(2026, 8, 10, 9, 5, tzinfo=datetime_timezone.utc),
        )

        run_qs = Mock()
        run_qs.filter.return_value = run_qs
        # order_by devuelve una lista real para que [:] funcione en el slice.
        run_qs.order_by.return_value = [run]

        step_qs = Mock()
        step_qs.filter.return_value = step_qs
        step_qs.order_by.return_value = [step]

        run_objects_mock.using.return_value = run_qs
        step_objects_mock.using.return_value = step_qs

        request = self.factory.get(
            "/analisis-crm/calidad-motor/progreso/?hist=1&from=2026-08-10&to=2026-08-10"
        )
        request.user = Mock(is_authenticated=False, is_superuser=False)
        request.current_user = Mock()
        request.current_user.intelligence_profile = Mock(
            level=5, allowed_domains=["gerencia"]
        )

        response = analysis_progress_api(request)

        self.assertIsInstance(response, JsonResponse)
        data = json.loads(response.content.decode("utf-8"))
        self.assertTrue(data["historical"])
        self.assertEqual(data["runs"][0]["run_type"], "daily")
        self.assertEqual(data["steps"][0]["run_type"], "daily")
        self.assertEqual(data["steps"][0]["lead_id"], 123)
        self.assertIn("calificación=confirmed", data["steps"][0]["message"])


class EvaluacionAutomaticaApiTests(SimpleTestCase):
    """Endpoint que dispara la evaluación incremental (canales del cron)."""

    URL = "/analisis-crm/api/evaluacion-automatica/"

    def test_ruta_resuelve(self):
        url = reverse("analisis_crm:evaluacion_automatica")
        self.assertTrue(url.endswith("/analisis-crm/api/evaluacion-automatica/"))

    @patch.dict("os.environ", {"ANALYTICS_BRIDGE_API_KEY": "clave-test"})
    def test_sin_api_key_es_403(self):
        from django.test import Client

        resp = Client().post(self.URL, data=b"{}", content_type="application/json")
        self.assertEqual(resp.status_code, 403)

    @patch.dict("os.environ", {"ANALYTICS_BRIDGE_API_KEY": "clave-test"})
    def test_stages_invalido_es_400(self):
        from django.test import Client

        resp = Client().post(
            self.URL,
            data=b'{"stages":"xx"}',
            content_type="application/json",
            HTTP_X_ANALYTICS_API_KEY="clave-test",
        )
        self.assertEqual(resp.status_code, 400)

    @patch.dict("os.environ", {"ANALYTICS_BRIDGE_API_KEY": "clave-test"})
    @patch(
        "lead_intelligence.analytics_api._has_fresh_running_run",
        return_value=False,
    )
    @patch("threading.Thread")
    def test_api_key_valida_dispara_202(self, thread_cls, _run):
        from django.test import Client

        resp = Client().post(
            self.URL,
            data=b'{"stages":"entered","lookback_hours":24,"workers":2}',
            content_type="application/json",
            HTTP_X_ANALYTICS_API_KEY="clave-test",
        )
        self.assertEqual(resp.status_code, 202)
        self.assertEqual(resp.json().get("status"), "started")
        self.assertTrue(thread_cls.called)

    @patch.dict("os.environ", {"ANALYTICS_BRIDGE_API_KEY": "clave-test"})
    @patch(
        "lead_intelligence.analytics_api._has_fresh_running_run",
        return_value=True,
    )
    def test_ya_en_curso_omite(self, _run):
        from django.test import Client

        resp = Client().post(
            self.URL,
            data=b'{"stages":"entered","lookback_hours":24}',
            content_type="application/json",
            HTTP_X_ANALYTICS_API_KEY="clave-test",
        )
        self.assertEqual(resp.status_code, 202)
        self.assertEqual(resp.json().get("status"), "already_running")


class VisitIntentApiTests(SimpleTestCase):
    """Endpoint de intención de visita para el CRM (sin BD)."""

    URL = "/analisis-crm/api/visit-intent/"

    def test_ruta_resuelve(self):
        url = reverse("analisis_crm:visit_intent_api")
        self.assertTrue(url.endswith("/analisis-crm/api/visit-intent/"))

    @patch.dict("os.environ", {"ANALYTICS_BRIDGE_API_KEY": "clave-test"})
    def test_sin_api_key_es_403(self):
        from django.test import Client

        resp = Client().get(
            self.URL + "?from=2026-08-01&to=2026-08-13"
        )
        self.assertEqual(resp.status_code, 403)

    @patch.dict("os.environ", {"ANALYTICS_BRIDGE_API_KEY": "clave-test"})
    @patch(
        "lead_intelligence.analytics_api.get_visit_intent_leads",
        return_value=[
            {
                "lead_id": 3384,
                "contact_name": "Elia Flores",
                "phone": "+51994607186",
                "agent_id": 3,
                "agent_name": "Carlos Torres",
                "status_name": "Interesado en vender",
                "entered_at": "2026-08-13T13:43:58-05:00",
                "visit_intent_status": "confirmed",
                "visit_intent_confidence": 0.85,
                "visit_intent_at": "2026-08-13T14:02:11-05:00",
                "visit_intent_evidence": [
                    {
                        "message_index": 4,
                        "sender": "lead",
                        "text": "Sí, quisiera visitarlo mañana",
                        "timestamp": "2026-08-13T14:02:11-05:00",
                    }
                ],
                "property_id": 99,
                "property_code": "PROP000099",
                "property_title": "Terreno ideal",
                "visit_registered": False,
            }
        ],
    )
    def test_con_api_key_devuelve_payload(self, _service):
        from django.test import Client

        resp = Client().get(
            self.URL + "?from=2026-08-01&to=2026-08-13",
            HTTP_X_ANALYTICS_API_KEY="clave-test",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["items"][0]["lead_id"], 3384)
        self.assertEqual(data["items"][0]["visit_intent_status"], "confirmed")
        self.assertTrue(data["items"][0]["visit_intent_evidence"])
        _service.assert_called_once()
