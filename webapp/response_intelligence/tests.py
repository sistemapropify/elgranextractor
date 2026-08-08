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


def _example(pk, category, client="", agent=""):
    return SimpleNamespace(
        pk=pk,
        intent_category=category,
        client_message=client or "¿cuánto cuesta?",
        agent_response=agent or "El precio es US$ 100,000.",
    )


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
        SimpleNamespace(category="prohibicion", rule_text="Nunca negociar precio"),
        SimpleNamespace(category="tono", rule_text="Responder en español"),
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

    @mock.patch.object(PromptAssemblyService, "select_few_shot", return_value=[])
    @mock.patch.object(
        PromptAssemblyService,
        "fetch_live_property_data",
        return_value={"success": False},
    )
    def test_assemble_armar_prompt(self, _fetch, _few_shot):
        result = PromptAssemblyService.assemble("¿cuánto cuesta?")
        self.assertIn("¿cuánto cuesta?", result["user_prompt"])
        self.assertEqual(result["property_data_used"], [])


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
