from datetime import datetime, timezone
from unittest.mock import patch

from django.template.loader import get_template
from django.test import SimpleTestCase

from .services import LEAD_RESULT_STAGES
from .visit_resolution import (
    VISIT_RESOLUTION_SQL,
    apply_visit_resolutions,
    resolve_visits_for_leads,
)


class AppointmentResolutionTests(SimpleTestCase):
    def test_sql_recognizes_visit_and_capture_event_types(self):
        self.assertIn("'visita'", VISIT_RESOLUTION_SQL)
        self.assertIn("'captacion'", VISIT_RESOLUTION_SQL)
        self.assertIn("'captación'", VISIT_RESOLUTION_SQL)
        self.assertIn("AS event_kind", VISIT_RESOLUTION_SQL)

    @patch(
        "lead_intelligence.visit_resolution.resolve_appointments_for_leads"
    )
    def test_visit_contract_does_not_mix_capture_appointments(self, resolver):
        resolver.return_value = [
            {"event_id": 1, "event_kind": "visit"},
            {"event_id": 2, "event_kind": "capture"},
        ]

        rows = resolve_visits_for_leads([100], persist=False)

        self.assertEqual([row["event_id"] for row in rows], [1])

    @patch(
        "lead_intelligence.visit_resolution.resolve_appointments_for_leads"
    )
    def test_apply_separates_visits_captures_and_commercial_total(self, resolver):
        first_capture = datetime(2026, 8, 24, 22, 24, tzinfo=timezone.utc)
        first_visit = datetime(2026, 8, 25, 15, 0, tzinfo=timezone.utc)
        resolver.return_value = [
            {
                "resolved_lead_id": 3585,
                "event_kind": "capture",
                "event_created_at": first_capture,
            },
            {
                "resolved_lead_id": 3585,
                "event_kind": "visit",
                "event_created_at": first_visit,
            },
            {
                "resolved_lead_id": 4000,
                "event_kind": "capture",
                "event_created_at": first_visit,
            },
        ]

        rows = apply_visit_resolutions(
            [{"id": 3585}, {"id": 4000}],
            persist=False,
        )

        self.assertEqual(rows[0]["first_capture_at"], first_capture)
        self.assertEqual(rows[0]["first_visit_at"], first_visit)
        self.assertEqual(rows[0]["first_appointment_at"], first_capture)
        self.assertIsNone(rows[1]["first_visit_at"])
        self.assertEqual(rows[1]["first_capture_at"], first_visit)
        self.assertEqual(rows[1]["first_appointment_at"], first_visit)

    def test_dashboard_exposes_clickable_capture_and_appointment_stages(self):
        self.assertEqual(
            LEAD_RESULT_STAGES["capture_registered"],
            "Cita de captación registrada",
        )
        self.assertEqual(
            LEAD_RESULT_STAGES["appointment_registered"],
            "Cita comercial registrada",
        )
        self.assertIsNotNone(
            get_template("lead_intelligence/overview_dashboard.html")
        )
        self.assertIsNotNone(
            get_template("lead_intelligence/cohort_dashboard.html")
        )
