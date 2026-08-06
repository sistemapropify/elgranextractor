import inspect
import re
from types import SimpleNamespace

from django.template.loader import get_template
from django.test import SimpleTestCase
from django.urls import reverse

from .property_dashboard import (
    PORTFOLIO_FIELD,
    _load_lead_rows,
    _load_visit_pairs,
    _portfolio_value,
    _property_card,
    aggregate_property_metrics,
)


def metric_card(property_id):
    return {
        "property_id": property_id,
        "code": f"PROP{property_id:06d}",
        "portfolio": True,
        "lead_count": 0,
        "contacted": 0,
        "bidirectional": 0,
        "qualified": 0,
        "visit_intent": 0,
        "visit_registered": 0,
        "unattended": 0,
    }


class PropertyDashboardTests(SimpleTestCase):
    def test_property_portfolio_field_uses_real_collection_name(self):
        self.assertEqual(PORTFOLIO_FIELD, "is_propify_portfolio")
        self.assertIs(_portfolio_value(True), True)
        self.assertIs(_portfolio_value("1"), True)
        self.assertIs(_portfolio_value(False), False)
        self.assertIs(_portfolio_value("false"), False)
        self.assertIsNone(_portfolio_value(None))

    def test_property_card_maps_collection_fields(self):
        document = SimpleNamespace(
            source_id="259",
            field_values={
                "code": "PROP000259",
                "title": "Terreno La Herrería",
                "district_name": "Cercado",
                "property_type_name": "Terreno",
                "operation_type_name": "Venta",
                "property_status_name": "Disponible",
                "responsible_name": "Carlos Torres",
                "price": 223000,
                "currency_name": "Dólares",
                "media_preview_url": "https://example.test/property.jpg",
                "is_propify_portfolio": True,
            },
        )

        card = _property_card(document)

        self.assertEqual(card["property_id"], 259)
        self.assertEqual(card["code"], "PROP000259")
        self.assertEqual(card["portfolio_key"], "own")
        self.assertEqual(card["district"], "Cercado")
        self.assertEqual(card["price_display"], "US$ 223,000")

    def test_metrics_deduplicate_property_lead_links_and_match_exact_visit_pair(self):
        cards = [metric_card(10), metric_card(20)]
        rows = [
            {
                "property_id": 10,
                "id": 7,
                "contacted": True,
                "bidirectional": True,
                "qualified": True,
                "visit_intent": True,
                "unattended": False,
            },
            {
                "property_id": 10,
                "id": 7,
                "contacted": True,
                "bidirectional": True,
                "qualified": True,
                "visit_intent": True,
                "unattended": False,
            },
            {
                "property_id": 20,
                "id": 7,
                "contacted": True,
                "bidirectional": False,
                "qualified": False,
                "visit_intent": False,
                "unattended": True,
            },
        ]

        aggregate_property_metrics(cards, rows, {(10, 7)})

        self.assertEqual(cards[0]["lead_count"], 1)
        self.assertEqual(cards[0]["qualified"], 1)
        self.assertEqual(cards[0]["visit_registered"], 1)
        self.assertEqual(cards[1]["lead_count"], 1)
        self.assertEqual(cards[1]["visit_registered"], 0)
        self.assertEqual(cards[1]["unattended"], 1)

    def test_crm_queries_are_select_only_and_visits_require_both_ids(self):
        forbidden = re.compile(
            r"\b(?:INSERT|UPDATE|DELETE|MERGE|ALTER|DROP|CREATE|TRUNCATE)\b",
            re.IGNORECASE,
        )
        lead_source = inspect.getsource(_load_lead_rows)
        visit_source = inspect.getsource(_load_visit_pairs)

        self.assertNotRegex(lead_source, forbidden)
        self.assertNotRegex(visit_source, forbidden)
        self.assertIn("e.property_id", visit_source)
        self.assertIn("e.lead_id", visit_source)
        self.assertIn("event_type", visit_source)
        self.assertIn("e.lead_id IS NOT NULL", visit_source)

    def test_dashboard_route_and_template_compile(self):
        self.assertEqual(
            reverse("analisis_crm:property_performance"),
            "/analisis-crm/propiedades/",
        )
        self.assertIsNotNone(
            get_template(
                "lead_intelligence/property_performance_dashboard.html"
            )
        )
