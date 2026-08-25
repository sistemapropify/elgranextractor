from datetime import datetime, time
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase

from n8n_bridge.services.initial_property_config import (
    office_schedule_state,
    schedule_state,
)
from n8n_bridge.services.initial_property_detector import (
    extract_property_identity,
    title_is_consistent,
)
from n8n_bridge.services.initial_property_renderer import render_initial_response
from n8n_bridge.services.initial_property_validator import validate_property_payload


class InitialPropertyDetectorTests(SimpleTestCase):
    def test_extracts_and_normalizes_property_code(self):
        result = extract_property_identity(
            "¡Hola! Más info sobre la casa de Urb. Colonial II (prop 261)"
        )
        self.assertEqual(result["codes"], ["PROP000261"])
        self.assertIn("Colonial II", result["title_hint"])

    def test_rejects_multiple_distinct_codes(self):
        result = extract_property_identity("PROP000261 y PROP000155")
        self.assertEqual(result["codes"], ["PROP000155", "PROP000261"])

    def test_title_consistency_uses_meaningful_tokens(self):
        self.assertTrue(title_is_consistent("casa de Urb. Colonial II", "Casa en Urbanización Colonial II"))
        self.assertFalse(title_is_consistent("casa de Bello Horizonte", "Casa en Urbanización Colonial II"))


class InitialPropertyRendererTests(SimpleTestCase):
    def _data(self, property_type="casa"):
        features = [{"field": "land_area", "value": 300, "source": "property_specs.land_area"}] if property_type == "terreno" else [
            {"field": "bedrooms", "value": 3, "source": "property_specs.bedrooms"},
            {"field": "built_area", "value": 120, "source": "property_specs.built_area"},
        ]
        return {
            "property_type": property_type,
            "location": "Urb. Colonial II, Paucarpata",
            "price": {"amount": "299000", "currency": "USD"},
            "features": features,
        }

    def test_house_template_contains_only_approved_general_data(self):
        text = render_initial_response(self._data())
        self.assertIn("3 dormitorios y 120 m² de área construida", text)
        self.assertIn("US$ 299,000", text)
        self.assertIn("Apenas uno de nuestros asesores", text)

    def test_land_template_uses_land_area(self):
        data = self._data("terreno")
        valid, _ = validate_property_payload(data)
        self.assertTrue(valid)
        self.assertIn("área de 300 m²", render_initial_response(data))

    def test_advisor_message_changes_at_office_boundaries(self):
        config = SimpleNamespace(
            timezone_name="America/Lima",
            office_start_time=time(9, 0),
            office_end_time=time(18, 0),
            advisor_message_in_hours=(
                "Un asesor podrá indicarle el estado de {property_reference}."
            ),
            advisor_message_out_of_hours=(
                "Un asesor podrá indicarle el estado de {property_reference} "
                "en horario de atención."
            ),
            message_templates=None,
        )
        tz = ZoneInfo("America/Lima")
        daytime = render_initial_response(
            self._data(),
            config,
            now=datetime(2026, 8, 24, 9, 0, tzinfo=tz),
        )
        nighttime = render_initial_response(
            self._data(),
            config,
            now=datetime(2026, 8, 24, 18, 0, tzinfo=tz),
        )
        self.assertIn("estado de la casa.", daytime)
        self.assertNotIn("horario de atención.", daytime)
        self.assertIn("estado de la casa en horario de atención.", nighttime)


class ScheduleGuardTests(SimpleTestCase):
    def test_initial_window_is_start_inclusive_end_exclusive(self):
        config = SimpleNamespace(
            timezone_name="America/Lima",
            start_time=time(0, 0),
            end_time=time(5, 0),
        )
        tz = ZoneInfo("America/Lima")
        self.assertTrue(schedule_state(config, datetime(2026, 8, 5, 0, 0, tzinfo=tz))["inside"])
        self.assertFalse(schedule_state(config, datetime(2026, 8, 5, 5, 0, tzinfo=tz))["inside"])

    def test_office_window_is_start_inclusive_end_exclusive(self):
        config = SimpleNamespace(
            timezone_name="America/Lima",
            office_start_time=time(9, 0),
            office_end_time=time(18, 0),
        )
        tz = ZoneInfo("America/Lima")
        self.assertTrue(
            office_schedule_state(config, datetime(2026, 8, 5, 9, 0, tzinfo=tz))["inside"]
        )
        self.assertFalse(
            office_schedule_state(config, datetime(2026, 8, 5, 18, 0, tzinfo=tz))["inside"]
        )


class EndpointContractTests(SimpleTestCase):
    @patch("n8n_bridge.property_bot_views.process_initial_message")
    @patch.dict("os.environ", {"N8N_BRIDGE_API_KEY": "secret"})
    def test_endpoint_returns_one_shot_contract(self, process):
        process.return_value = {
            "success": True,
            "action": "respond_once",
            "reply_text": "respuesta",
            "reason_code": "ANSWER_SENT",
        }
        response = self.client.post(
            "/api/n8n/property-bot/v1/initial-response/",
            data={
                "message_id": "wamid-1",
                "external_conversation_id": "thread-1",
                "phone": "+51999999999",
                "text": "Más info (PROP000261)",
            },
            content_type="application/json",
            HTTP_X_N8N_API_KEY="secret",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["action"], "respond_once")
