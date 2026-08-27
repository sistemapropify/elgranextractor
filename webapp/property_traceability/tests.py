import json
from types import SimpleNamespace

from django.test import RequestFactory, TestCase

from .constants import STAGES
from .external_sources import (
    PROPIFY_MEDIA_BASE_URL,
    enrich_document_row,
    enrich_media_row,
    resolve_propifai_media_url,
    summarize_evidence,
)
from .models import StageRequirement, WorkflowEvent
from .services import ensure_workflow, gate_state, transition
from .views import _fact_card, update_requirement


class WorkflowRulesTests(TestCase):
    def setUp(self):
        self.workflow = ensure_workflow(1001)

    def test_initializes_complete_stage_matrix(self):
        self.assertEqual(self.workflow.stages.count(), len(STAGES))
        self.assertEqual(self.workflow.current_stage, "draft")
        self.assertEqual(self.workflow.stages.get(stage_key="captation").status, "completed")
        self.assertEqual(self.workflow.stages.get(stage_key="draft").status, "in_progress")
        self.assertEqual(self.workflow.stages.get(stage_key="publication").status, "disabled")

    def test_legal_review_is_blocked_until_documents_are_approved(self):
        allowed, missing = gate_state(self.workflow, "legal_review")
        self.assertFalse(allowed)
        self.assertIn("mandatory_documents_complete", missing)
        StageRequirement.objects.filter(
            stage__workflow=self.workflow,
            stage__stage_key="documentation",
            is_mandatory=True,
        ).update(status="approved")
        allowed, missing = gate_state(self.workflow, "legal_review")
        self.assertTrue(allowed)
        self.assertEqual(missing, [])

    def test_publication_requires_all_mandatory_gates(self):
        allowed, missing = gate_state(self.workflow, "publication")
        self.assertFalse(allowed)
        self.assertIn("brokerage_contract_signed", missing)
        self.assertIn("marketing_material_approved", missing)

    def test_backward_transition_requires_reason(self):
        transition(self.workflow, "documentation")
        with self.assertRaisesMessage(ValueError, "motivo es obligatorio"):
            transition(self.workflow, "draft")
        transition(self.workflow, "draft", reason="Documentación observada")
        self.assertEqual(self.workflow.current_stage, "draft")
        self.assertTrue(WorkflowEvent.objects.filter(event_type="stage_transition", reason="Documentación observada").exists())

    def test_requirement_update_records_audit_event(self):
        requirement = StageRequirement.objects.get(
            stage__workflow=self.workflow,
            stage__stage_key="documentation",
            code="owner_dni",
        )
        request = RequestFactory().post(
            "/requirement/",
            data=json.dumps({"status": "approved"}),
            content_type="application/json",
        )
        response = update_requirement(request, self.workflow.property_id, requirement.id)
        self.assertEqual(response.status_code, 200)
        requirement.refresh_from_db()
        self.assertEqual(requirement.status, "approved")
        self.assertTrue(WorkflowEvent.objects.filter(
            workflow=self.workflow,
            event_type="requirement_updated",
            metadata__requirement="owner_dni",
        ).exists())

    def test_visit_is_visible_even_without_previous_documents(self):
        prop = SimpleNamespace(wp_post_id=None, wp_last_sync=None)
        facts = summarize_evidence(prop, {
            "documents": [],
            "media": [],
            "events": [{"event_type": "Visita", "start_time": None, "created_at": None}],
            "proposals": [],
        })
        documentation = _fact_card(next(item for item in STAGES if item.key == "documentation"), facts)
        visits = _fact_card(next(item for item in STAGES if item.key == "visits"), facts)
        self.assertEqual(documentation["status"], "pending")
        self.assertEqual(visits["status"], "completed")

    def test_documentation_counts_only_three_required_documents(self):
        prop = SimpleNamespace(wp_post_id=None, wp_last_sync=None)
        definition = next(item for item in STAGES if item.key == "documentation")
        documents = [
            {"document_code": "107", "file": "dni.pdf", "created_at": None},
            {"document_code": "110", "file": "partida.pdf", "created_at": None},
            {"document_code": "111", "file": "parametros.pdf", "created_at": None},
        ]
        card = _fact_card(definition, summarize_evidence(prop, {
            "documents": documents, "media": [], "events": [], "proposals": [],
        }))
        self.assertEqual(card["done"], 2)
        self.assertEqual(card["total"], 3)
        self.assertEqual(card["progress"], 67)
        self.assertEqual(card["status"], "in_progress")

    def test_documentation_reaches_100_with_all_three_files(self):
        prop = SimpleNamespace(wp_post_id=None, wp_last_sync=None)
        definition = next(item for item in STAGES if item.key == "documentation")
        documents = [
            {"document_code": code, "file_url": f"https://example.test/{code}.pdf", "created_at": None}
            for code in ("107", "110", "106")
        ]
        card = _fact_card(definition, summarize_evidence(prop, {
            "documents": documents, "media": [], "events": [], "proposals": [],
        }))
        self.assertEqual(card["done"], 3)
        self.assertEqual(card["progress"], 100)
        self.assertEqual(card["status"], "completed")

    def test_relative_blob_paths_are_resolved_for_media_and_documents(self):
        expected = f"{PROPIFY_MEDIA_BASE_URL}/properties/Casa%20Cayma/foto%201.jpg"
        relative = r"/media/properties/Casa Cayma\foto 1.jpg"
        self.assertEqual(resolve_propifai_media_url(relative), expected)
        self.assertEqual(enrich_media_row({"file": relative})["resolved_url"], expected)
        self.assertEqual(enrich_document_row({"file": relative})["file_url"], expected)

    def test_absolute_blob_url_is_preserved(self):
        absolute = "https://propifymedia01.blob.core.windows.net/media/PF-100/video.mp4"
        self.assertEqual(resolve_propifai_media_url(absolute), absolute)

    def test_unknown_non_video_media_is_available_as_image(self):
        prop = SimpleNamespace(code="PF-100", wp_post_id=None, wp_last_sync=None, video_url=None)
        media = enrich_media_row({"id": 1, "file": "PF-100/gallery-item", "media_type": "gallery"})
        facts = summarize_evidence(prop, {"documents": [], "media": [media], "events": [], "proposals": []})
        self.assertEqual(facts["images"], [media])
