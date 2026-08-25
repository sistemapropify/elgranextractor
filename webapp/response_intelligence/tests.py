"""Tests unitarios del motor de respuestas IA (sin base de datos).

Se ejecutan con el runner sin BD (usar los settings locales de prueba):
    py manage.py test response_intelligence --settings=test_settings --testrunner=nodb_runner.NoDbTestRunner --no-input
NO crean ni tocan ninguna base de datos en Azure (SimpleTestCase + ORM mockeado).
"""

import os
import unittest
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from intelligence.services.llm import LLMService

from .curation import CurationService
from .models import CuratedExample
from .prompt_assembly import PromptAssemblyService
from .shadow import maybe_generate_shadow_draft, shadow_mode_enabled


class _FakeQS:
    """Fake queryset: soporta filter/order_by/slice/iteración."""

    def __init__(self, data):
        self.data = list(data)

    def filter(self, **kwargs):
        result = self.data
        for key, value in kwargs.items():
            result = [x for x in result if getattr(x, key, None) == value]
        return _FakeQS(result)

    def order_by(self, *args):
        return self

    def __iter__(self):
        return iter(self.data)

    def __len__(self):
        return len(self.data)

    def __bool__(self):
        return bool(self.data)

    def __getitem__(self, item):
        if isinstance(item, slice):
            return _FakeQS(self.data[item])
        return self.data[item]


class _FakeManager:
    """Fake manager: .using(db) es no-op y devuelve el queryset fake."""

    def __init__(self, items):
        self._items = list(items)

    def using(self, db):
        return self

    def filter(self, **kwargs):
        return _FakeQS(self._items).filter(**kwargs)

    def order_by(self, *args):
        return _FakeQS(self._items)


def _example(pk, category, client="", agent="", **extra):
    """Fake de CuratedExample con los campos que el ORM usa en los filtros."""
    data = dict(
        pk=pk,
        intent_category=category,
        client_message=client or "¿cuánto cuesta?",
        agent_response=agent or "El precio es US$ 100,000.",
        approved=True,
        active=True,
        updated_at=1,
    )
    data.update(extra)
    return SimpleNamespace(**data)


class CurationServiceTests(SimpleTestCase):
    def test_detect_category_precio(self):
        self.assertEqual(CurationService._detect_category("me interesa el precio"), "precio")

    def test_detect_category_ubicacion(self):
        self.assertEqual(CurationService._detect_category("¿en qué distrito queda?"), "ubicacion")

    def test_detect_category_objecion_precio(self):
        self.assertEqual(CurationService._detect_category("está muy caro, ¿bajarían?"), "objecion_precio")

    def test_detect_category_default_otro(self):
        self.assertEqual(CurationService._detect_category("hola buenas noches"), "otro")

    def test_extract_pair(self):
        messages = [
            {"sender": "lead", "text": "¿cuánto cuesta?", "timestamp": 1},
            {"sender": "agent", "text": "US$ 100,000", "timestamp": 2},
            {"sender": "lead", "text": "¿y área?", "timestamp": 3},
        ]
        client, agent = CurationService._extract_pair(messages)
        self.assertEqual(client, "¿cuánto cuesta?")
        self.assertEqual(agent, "US$ 100,000")


class PromptAssemblyTests(SimpleTestCase):
    def test_keyword_overlap(self):
        score = PromptAssemblyService._keyword_overlap(
            "¿cuánto cuesta el precio?", "el precio es bueno"
        )
        self.assertGreaterEqual(score, 1)

    @mock.patch("response_intelligence.prompt_assembly.BusinessRule.objects", new_callable=lambda: _FakeManager([
        SimpleNamespace(category="prohibicion", rule_text="Nunca negociar precio", active=True),
        SimpleNamespace(category="tono", rule_text="Responder en español", active=True),
    ]))
    def test_build_system_prompt_incluye_reglas(self, _objects):
        prompt = PromptAssemblyService.build_system_prompt()
        self.assertIn("PROHIBIDO", prompt)
        self.assertIn("Nunca negociar precio", prompt)
        self.assertIn("TONO Y ESTILO", prompt)

    @mock.patch("response_intelligence.prompt_assembly.CuratedExample.objects", new_callable=lambda: _FakeManager([
        _example(1, "precio"),
        _example(2, "precio"),
        _example(3, "ubicacion"),
    ]))
    def test_select_few_shot_prioriza_categoria(self, _objects):
        selected = PromptAssemblyService.select_few_shot(
            "¿cuánto cuesta?", intent_category="precio", k=2
        )
        self.assertTrue(selected)
        self.assertTrue(all(e.intent_category == "precio" for e in selected))

    @mock.patch.object(
        PromptAssemblyService, "build_system_prompt", return_value="SISTEMA"
    )
    @mock.patch.object(PromptAssemblyService, "select_few_shot", return_value=[])
    @mock.patch.object(
        PromptAssemblyService,
        "fetch_live_property_data",
        return_value={"success": False},
    )
    def test_assemble_armar_prompt(self, _fetch, _few_shot, _sys):
        result = PromptAssemblyService.assemble("¿cuánto cuesta?")
        self.assertIn("¿cuánto cuesta?", result["user_prompt"])
        self.assertEqual(result["property_data_used"], [])


    def test_detecta_area_de_terreno_en_repregunta(self):
        fields = PromptAssemblyService.requested_property_fields(
            "Cuanto tiene de terreno?"
        )
        self.assertEqual(fields, ["land_area"])

    def test_respuesta_de_area_no_repite_datos_no_solicitados(self):
        data = {
            "price": {"amount": 500000, "currency": "USD"},
            "facts": {
                "land_area": 190,
                "built_area": 360,
                "bedrooms": 6,
                "bathrooms": 5,
            },
        }

        response = PromptAssemblyService.strict_property_reply(
            data, ["land_area"]
        )

        self.assertEqual(response, "Tiene 190 m² de terreno.")
        self.assertNotIn("500", response)
        self.assertNotIn("dormitorios", response)
        self.assertNotIn("baños", response)

    @mock.patch.object(
        PromptAssemblyService, "build_system_prompt", return_value="SISTEMA"
    )
    @mock.patch.object(PromptAssemblyService, "select_few_shot", return_value=[])
    @mock.patch.object(
        PromptAssemblyService,
        "fetch_live_property_data",
        return_value={
            "success": True,
            "data": {
                "code": "PROP000096",
                "title": "Casa en Cabaña María",
                "property_type": "casa",
                "location": "Cercado",
                "price": {"amount": 500000, "currency": "USD"},
                "facts": {
                    "land_area": 190,
                    "built_area": 360,
                    "bedrooms": 6,
                    "bathrooms": 5,
                },
            },
        },
    )
    @mock.patch(
        "response_intelligence.prompt_assembly.memory_bridge.resolve_memory",
        return_value=(None, None, {}),
    )
    def test_repregunta_consulta_propiedad_activa_y_crea_respuesta_estricta(
        self, _memory, fetch, _few_shot, _system
    ):
        result = PromptAssemblyService.assemble(
            "Cuanto tiene de terreno?",
            property_code="PROP000096",
            conversation_messages=[
                {
                    "role": "user",
                    "content": "Más información de PROP000096",
                },
            ],
        )

        fetch.assert_called_once_with("PROP000096")
        self.assertEqual(result["requested_fields"], ["land_area"])
        self.assertEqual(
            result["strict_response"], "Tiene 190 m² de terreno."
        )
        self.assertIn("- land_area: 190", result["user_prompt"])
        self.assertNotIn("- bedrooms:", result["user_prompt"])


from response_intelligence.guardrails import (  # noqa: E402
    block_summary,
    is_escalation,
    mentions_discount,
    mentions_property_data,
    validate_generated_response,
)


class GuardrailsTests(SimpleTestCase):
    """Guardrails deterministas (spec §7) — puros, sin BD."""

    def test_escalamiento_abogado(self):
        self.assertTrue(is_escalation("necesito hablar con un abogado"))

    def test_escalamiento_denuncia(self):
        self.assertTrue(is_escalation("voy a poner una denuncia"))

    def test_no_escalamiento_normal(self):
        self.assertFalse(is_escalation("¿cuál es el precio?"))

    def test_mentions_price_without_currency(self):
        self.assertTrue(mentions_property_data("El precio es 120,000 soles"))

    def test_mentions_area_m2(self):
        self.assertTrue(mentions_property_data("Tiene 85 m2 de área"))

    def test_mentions_location(self):
        self.assertTrue(mentions_property_data("Está en la Av. Ejército"))

    def test_mentions_property_data_false_para_saludo(self):
        self.assertFalse(mentions_property_data("Hola, gracias por tu mensaje"))

    def test_discount_porcentaje(self):
        self.assertTrue(mentions_discount("Te puedo hacer un 5% de descuento"))

    def test_discount_verbo_rebaja(self):
        self.assertTrue(mentions_discount("podría bajar el precio"))

    def test_no_discount_normal(self):
        self.assertFalse(mentions_discount("El precio es S/ 120,000"))

    def test_validate_hallucination_sin_datos(self):
        result = validate_generated_response(
            "El precio es S/ 100,000 y tiene 80 m2", []
        )
        self.assertTrue(result["hallucination"])
        self.assertTrue(result["blocked"])
        self.assertIn("Alucinación", result["reasons"][0])

    def test_validate_con_datos_no_alucina(self):
        result = validate_generated_response(
            "El precio es S/ 100,000", [{"code": "PROP000261"}]
        )
        self.assertFalse(result["hallucination"])
        self.assertFalse(result["blocked"])

    def test_validate_negocia_precio_bloquea(self):
        result = validate_generated_response(
            "Puedo ofrecerte 10% de descuento", [{"code": "PROP000261"}]
        )
        self.assertTrue(result["discount"])
        self.assertTrue(result["blocked"])

    def test_block_summary(self):
        result = validate_generated_response("El precio es S/ 100,000", [])
        self.assertIn("Alucinación", block_summary(result))
        self.assertEqual(block_summary({"blocked": False}), "")


class ShadowContextTests(SimpleTestCase):
    def test_build_shadow_context_includes_human_followup(self):
        from types import SimpleNamespace

        from .services import _build_shadow_context

        draft = SimpleNamespace(client_message="Hola, quiero más info")
        conversation = {
            "messages": [
                {"sender": "lead", "text": "Hola, quiero más info", "timestamp": 1},
                {"sender": "agent", "text": "Claro, te comparto los detalles", "timestamp": 2},
                {"sender": "lead", "text": "Perfecto, gracias", "timestamp": 3},
            ],
            "timeline_events": [],
            "total_messages": 3,
        }

        context = _build_shadow_context(draft, conversation)

        self.assertTrue(context["available"])
        self.assertEqual(context["trigger_index"], 0)
        self.assertEqual(context["human_reply"]["text"], "Claro, te comparto los detalles")
        self.assertEqual(context["thread"]["total_messages"], 3)


class ShadowConversationStateTests(SimpleTestCase):
    def test_active_property_changes_when_new_code_appears(self):
        from .shadow_context import property_code_as_of

        messages = [
            {"sender": "lead", "text": "Info PROP000270", "position": 0},
            {"sender": "agent", "text": "Respuesta humana", "position": 1},
            {"sender": "lead", "text": "Ahora info PROP000253", "position": 2},
            {"sender": "lead", "text": "¿Es esquina?", "position": 3},
        ]

        self.assertEqual(property_code_as_of(messages, 0), "PROP000270")
        self.assertEqual(property_code_as_of(messages, 2), "PROP000253")
        self.assertEqual(property_code_as_of(messages, 3), "PROP000253")

    def test_repeated_texts_keep_distinct_shadow_answers(self):
        from .services import _build_shadow_context

        conversation = {
            "messages": [
                {"sender": "lead", "text": "Más información", "timestamp": 1, "position": 4},
                {"sender": "agent", "text": "Respuesta humana uno", "timestamp": 2, "position": 5},
                {"sender": "lead", "text": "Más información", "timestamp": 3, "position": 9},
            ]
        }
        first = SimpleNamespace(
            pk=1,
            client_message="Más información",
            generated_response="Respuesta sombra uno",
            created_at=1,
            prompt_snapshot={"context": {"source_position": 4}},
        )
        second = SimpleNamespace(
            pk=2,
            client_message="Más información",
            generated_response="Respuesta sombra dos",
            created_at=2,
            prompt_snapshot={"context": {"source_position": 9}},
        )

        context = _build_shadow_context(second, conversation, [first, second])
        shadow_answers = [
            item["text"] for item in context["shadow_messages"] if item.get("shadow")
        ]
        self.assertEqual(
            shadow_answers, ["Respuesta sombra uno", "Respuesta sombra dos"]
        )
        self.assertEqual(context["trigger_index"], 2)

    def test_shadow_history_excludes_human_answers(self):
        from .shadow_context import shadow_history_before

        messages = [
            {"sender": "lead", "text": "Info PROP000099", "position": 0},
            {"sender": "agent", "text": "DATO DEL HUMANO", "position": 1},
            {"sender": "lead", "text": "¿Tiene medidas?", "position": 2},
        ]
        prior = SimpleNamespace(
            pk=1,
            client_message="Info PROP000099",
            generated_response="RESPUESTA SOMBRA",
            created_at=1,
            prompt_snapshot={"context": {"source_position": 0}},
        )

        history = shadow_history_before(messages, 2, [prior])
        rendered = " ".join(item["content"] for item in history)
        self.assertIn("RESPUESTA SOMBRA", rendered)
        self.assertNotIn("DATO DEL HUMANO", rendered)

class ShadowTests(SimpleTestCase):
    def test_shadow_mode_apagado_por_defecto(self):
        with mock.patch.dict(os.environ, {"RESPONSE_INTELLIGENCE_SHADOW": "0"}, clear=False):
            self.assertFalse(shadow_mode_enabled())

    def test_shadow_mode_encendido(self):
        with mock.patch.dict(os.environ, {"RESPONSE_INTELLIGENCE_SHADOW": "1"}, clear=False):
            self.assertTrue(shadow_mode_enabled())

    def test_maybe_generate_desactivado_retorna_none(self):
        with mock.patch.dict(os.environ, {"RESPONSE_INTELLIGENCE_SHADOW": "0"}, clear=False):
            self.assertIsNone(maybe_generate_shadow_draft(client_message="hola"))


    def test_codigo_prop_usa_plantilla_y_no_llm(self):
        objects = mock.Mock()
        objects.using.return_value = objects
        stored = SimpleNamespace(pk=105, trace_id="", save=mock.Mock())
        objects.create.return_value = stored
        decision = {
            "success": True,
            "reason_code": "ANSWER_READY",
            "property_code": "PROP000262",
            "data": {
                "code": "PROP000262",
                "title": "HOTEL EQUIPADO EN VENTA RIVERO - CERCADO",
                "property_type": "hotel",
                "location": "Arequipa",
                "price": {"amount": 650000, "currency": "USD"},
                "features": [{"field": "built_area", "value": 468}],
            },
            "reply_text": "PLANTILLA VERIFICADA",
            "evidence": {},
        }
        with mock.patch(
            "response_intelligence.shadow.shadow_mode_enabled",
            return_value=True,
        ), mock.patch(
            "response_intelligence.models.BotResponseDraft.objects",
            objects,
        ), mock.patch(
            "n8n_bridge.services.initial_property_config.get_bot_configuration"
        ), mock.patch(
            "n8n_bridge.services.initial_property_decision."
            "decide_initial_property_response",
            return_value=decision,
        ), mock.patch.object(LLMService, "generate_response") as generate:
            result = maybe_generate_shadow_draft(
                client_message="Más info del hotel (PROP000262)"
            )
        self.assertIs(result, stored)
        generate.assert_not_called()
        self.assertEqual(objects.create.call_args.kwargs["generated_response"], "PLANTILLA VERIFICADA")
        self.assertEqual(objects.create.call_args.kwargs["model_version"], "deterministic-template-v1")

class GenerateCommandTests(SimpleTestCase):
    def test_property_code_from_messages(self):
        from .management.commands.generate_draft_responses import Command

        messages = [
            {"sender": "lead", "text": "hola, me interesa la PROP000261"},
            {"sender": "agent", "text": "claro"},
        ]
        self.assertEqual(Command._property_code_from_messages(messages), "PROP000261")

    def test_property_code_no_encontrado(self):
        from .management.commands.generate_draft_responses import Command

        self.assertEqual(Command._property_code_from_messages([{"text": "hola"}]), "")


class LLMGenerateResponseTests(SimpleTestCase):
    @mock.patch.object(LLMService, "_call_deepseek_api", return_value=(True, "OK", {"content": "Hola, con gusto."}))
    def test_generate_response_ok(self, _call):
        ok, message, text = LLMService.generate_response("sys", "user")
        self.assertTrue(ok)
        self.assertEqual(text, "Hola, con gusto.")

    def test_generate_response_vincula_trace_id(self):
        from intelligence.learning.trace_context import current_trace_id

        captured = {}

        def side_effect(**kwargs):
            captured["trace"] = current_trace_id()
            return True, "OK", {"content": "ok"}

        with mock.patch.object(LLMService, "_call_deepseek_api", side_effect=side_effect):
            ok, _msg, _text = LLMService.generate_response(
                "sys", "user", trace_id="bot_draft:42"
            )
        self.assertTrue(ok)
        self.assertEqual(captured["trace"], "bot_draft:42")


class MemoryBridgePromptTests(SimpleTestCase):
    """PromptAssemblyService.assemble con memoria conversacional (sin BD)."""

    @staticmethod
    def _ctx(messages=None, summary=""):
        return {
            "messages": messages or [],
            "summary": summary,
            "user_id": "u-1",
            "session_id": "sess-1",
        }

    def test_extract_property_identity_es_dict(self):
        from n8n_bridge.services.initial_property_detector import (
            extract_property_identity,
        )

        detected = extract_property_identity(
            "¡Hola! Más info sobre el depa (PROP000265)"
        )
        self.assertIsInstance(detected, dict)
        self.assertIn("PROP000265", detected["codes"])

    def test_resuelve_property_desde_contexto_de_memoria(self):
        """Repregunta sin código: resuelve el property desde la memoria."""
        ctx = self._ctx(
            messages=[
                {"role": "user", "content": "¿Cuánto cuesta PROP000265?"},
                {"role": "assistant", "content": "El depa cuesta 120k"},
            ],
            summary="Cliente busca departamento.",
        )
        with mock.patch(
            "response_intelligence.prompt_assembly.memory_bridge.resolve_memory",
            return_value=(
                SimpleNamespace(id="user"),
                SimpleNamespace(id="conv"),
                ctx,
            ),
        ), mock.patch.object(
            PromptAssemblyService, "build_system_prompt", return_value="SISTEMA"
        ), mock.patch.object(
            PromptAssemblyService, "select_few_shot", return_value=[]
        ), mock.patch.object(
            PromptAssemblyService,
            "fetch_live_property_data",
            return_value={"success": False},
        ) as fetch:
            result = PromptAssemblyService.assemble(
                "¿cuál es el método de pago?", lead_id=5, phone="999"
            )
        fetch.assert_called_once_with("PROP000265")
        self.assertIn("Contexto de la conversación", result["user_prompt"])
        self.assertIn("PROP000265", result["user_prompt"])
        self.assertEqual(result["memory"]["conversation_id"], "conv")

    def test_resuelve_property_desde_mensaje_actual(self):
        with mock.patch(
            "response_intelligence.prompt_assembly.memory_bridge.resolve_memory",
            return_value=(None, None, {}),
        ), mock.patch.object(
            PromptAssemblyService, "build_system_prompt", return_value="SISTEMA"
        ), mock.patch.object(
            PromptAssemblyService, "select_few_shot", return_value=[]
        ), mock.patch.object(
            PromptAssemblyService,
            "fetch_live_property_data",
            return_value={"success": False},
        ) as fetch:
            PromptAssemblyService.assemble(
                "Quiero info de la casa PROP000270", phone="999"
            )
        fetch.assert_called_once_with("PROP000270")

    def test_sin_memoria_no_rompe_ni_inyecta_contexto(self):
        with mock.patch(
            "response_intelligence.prompt_assembly.memory_bridge.resolve_memory",
            return_value=(None, None, {}),
        ), mock.patch.object(
            PromptAssemblyService, "build_system_prompt", return_value="SISTEMA"
        ), mock.patch.object(
            PromptAssemblyService, "select_few_shot", return_value=[]
        ), mock.patch.object(
            PromptAssemblyService,
            "fetch_live_property_data",
            return_value={"success": False},
        ):
            result = PromptAssemblyService.assemble("hola")
        self.assertNotIn("Contexto de la conversación", result["user_prompt"])
        self.assertIsNone(result["memory"]["conversation_id"])

    def test_property_code_from_context_puro(self):
        from response_intelligence import memory_bridge

        ctx = self._ctx(
            messages=[{"role": "user", "content": "¿precio de PROP 265?"}]
        )
        self.assertEqual(memory_bridge.property_code_from_context(ctx), "PROP000265")
        self.assertEqual(memory_bridge._normalize_code("prop 7"), "PROP000007")


    def test_current_code_overrides_stale_property_and_uses_shadow_history(self):
        ctx = self._ctx(
            messages=[
                {"role": "user", "content": "Info PROP000270"},
                {"role": "assistant", "content": "RESPUESTA HUMANA ANTIGUA"},
            ]
        )
        shadow_history = [
            {"role": "user", "content": "Info PROP000270"},
            {"role": "assistant", "content": "RESPUESTA SOMBRA ANTERIOR"},
        ]
        with mock.patch(
            "response_intelligence.prompt_assembly.memory_bridge.resolve_memory",
            return_value=(None, None, ctx),
        ), mock.patch.object(
            PromptAssemblyService, "build_system_prompt", return_value="SISTEMA"
        ), mock.patch.object(
            PromptAssemblyService, "select_few_shot", return_value=[]
        ), mock.patch.object(
            PromptAssemblyService,
            "fetch_live_property_data",
            return_value={"success": False},
        ) as fetch:
            result = PromptAssemblyService.assemble(
                "Ahora quiero PROP000253",
                property_code="PROP000270",
                conversation_messages=shadow_history,
            )

        fetch.assert_called_once_with("PROP000253")
        self.assertIn("RESPUESTA SOMBRA ANTERIOR", result["user_prompt"])
        self.assertNotIn("RESPUESTA HUMANA ANTIGUA", result["user_prompt"])


class DashboardConnectionRecoveryTests(SimpleTestCase):
    @mock.patch("response_intelligence.views.close_old_connections")
    @mock.patch("response_intelligence.views.get_ai_cost_summary_for_drafts")
    @mock.patch("response_intelligence.views.get_response_dashboard")
    def test_retries_once_after_transient_operational_error(
        self, dashboard, cost, close_connections
    ):
        from django.db import OperationalError
        from .views import _load_dashboard_context

        dashboard.side_effect = [OperationalError("08S01"), {"kpis": {}}]
        cost.return_value = {"total_usd": 0, "calls": 0, "avg_usd": 0}
        context = _load_dashboard_context()
        self.assertEqual(context["kpis"], {})
        self.assertEqual(dashboard.call_count, 2)
        close_connections.assert_called_once_with()

    @mock.patch("response_intelligence.views.close_old_connections")
    @mock.patch("response_intelligence.views.get_response_dashboard")
    def test_reraises_when_second_attempt_also_fails(
        self, dashboard, close_connections
    ):
        from django.db import OperationalError
        from .views import _load_dashboard_context

        dashboard.side_effect = OperationalError("08S01")
        with self.assertRaises(OperationalError):
            _load_dashboard_context()
        self.assertEqual(dashboard.call_count, 2)
        self.assertEqual(close_connections.call_count, 2)