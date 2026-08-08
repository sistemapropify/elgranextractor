"""Curación de ejemplos few-shot a partir de evaluaciones de lead_intelligence.

Solo lee el CRM (SELECT) y escribe en la BD ``default`` (``propiextractor``).
"""

from django.utils import timezone

from lead_intelligence.models import LeadConversationAssessment

from .models import CuratedExample


class CurationService:
    """Servicio para construir el banco de ejemplos few-shot del motor IA."""

    INTENT_KEYWORDS = {
        "precio": [
            "precio", "costo", "cuanto", "cuánto", "vale", "cuesta", "soles",
            "dolares", "dólares", "usd", "s/", "tarifa",
        ],
        "ubicacion": [
            "ubicacion", "ubicación", "direccion", "dirección", "donde", "dónde",
            "zona", "distrito", "maps", "mapa", "cerca", "referencia",
        ],
        "visita": [
            "visitar", "visita", "ver", "agendar", "coordinar", "reunir",
            "reunión", "conocer", "mostrar", "muestra",
        ],
        "financiamiento": [
            "financiamiento", "credito", "crédito", "cuota", "inicial", "banco",
            "financiar", "leasing", "hipoteca",
        ],
        "objecion_precio": [
            "caro", "muy alto", "bajar", "rebaja", "descuento", "negociar",
            "presupuesto", "regatear", "no alcanza",
        ],
        "disponibilidad": [
            "disponible", "disponibilidad", "sigue", "vendido", "reservado",
            "aún", "aun disponible", "en venta",
        ],
    }
    DEFAULT_CATEGORY = "otro"

    @staticmethod
    def _average_score(assessment) -> float:
        values = [
            assessment.relevance_score,
            assessment.coverage_score,
            assessment.directness_score,
            assessment.personalization_score,
        ]
        values = [float(v) for v in values if v is not None]
        return (sum(values) / len(values) * 100) if values else 0.0

    @classmethod
    def _detect_category(cls, text: str) -> str:
        lowered = (text or "").lower()
        for category, keywords in cls.INTENT_KEYWORDS.items():
            if any(keyword in lowered for keyword in keywords):
                return category
        return cls.DEFAULT_CATEGORY

    @classmethod
    def suggest_candidates(cls, min_score: int = 80, limit: int = 200) -> list:
        """Propone evaluaciones ``adequate`` con score alto como candidatos few-shot.

        Devuelve una lista de dicts:
        ``{"assessment_id", "lead_id", "score", "category", "analyzed_at"}``.
        Excluye leads que ya tienen un CuratedExample para no repetir.
        """
        already_curated = set(
            CuratedExample.objects.using("default")
            .values_list("source_lead_id", flat=True)
        )
        assessments = (
            LeadConversationAssessment.objects.using("default")
            .filter(first_response_status="adequate")
            .order_by("-analyzed_at")[: limit * 6]
        )
        candidates = []
        for assessment in assessments:
            if assessment.source_lead_id in already_curated:
                continue
            score = cls._average_score(assessment)
            if score < min_score:
                continue
            candidates.append(
                {
                    "assessment_id": assessment.pk,
                    "lead_id": assessment.source_lead_id,
                    "score": round(score, 1),
                    "category": cls._detect_category(assessment.reason or ""),
                    "analyzed_at": assessment.analyzed_at,
                }
            )
            if len(candidates) >= limit:
                break
        return candidates

    @staticmethod
    def _extract_pair(messages) -> tuple:
        """Devuelve (client_message, agent_response) del primer bloque útil."""
        if not messages:
            return "", ""
        ordered = sorted(
            messages,
            key=lambda m: (m.get("timestamp") or "", m.get("position") or 0),
        )
        client_message = ""
        agent_response = ""
        lead_seen = False
        for message in ordered:
            text = str(message.get("text") or "").strip()
            sender = str(message.get("sender") or "").lower()
            if sender == "lead":
                lead_seen = True
                if not client_message:
                    client_message = text
            elif sender == "agent" and lead_seen and not agent_response:
                agent_response = text
            if client_message and agent_response:
                break
        return client_message, agent_response

    @classmethod
    def promote_to_curated(
        cls,
        assessment_id: int,
        intent_category: str = "",
        approved_by=None,
    ) -> CuratedExample:
        """Crea (o actualiza) un CuratedExample desde una evaluación aprobada.

        Extrae el par cliente/agente desde la conversación del lead (SELECT al CRM)
        y copia los scores al momento de curar. Queda ``approved=False`` hasta la
        revisión humana.
        """
        from lead_intelligence.services import get_lead_conversation

        assessment = LeadConversationAssessment.objects.using("default").get(
            pk=assessment_id
        )
        conversation = get_lead_conversation(assessment.source_lead_id)
        client_message, agent_response = cls._extract_pair(
            (conversation or {}).get("messages") or []
        )
        category = intent_category or cls._detect_category(assessment.reason or "")
        scores = {
            "relevance": float(assessment.relevance_score or 0),
            "coverage": float(assessment.coverage_score or 0),
            "directness": float(assessment.directness_score or 0),
            "personalization": float(assessment.personalization_score or 0),
        }
        example, _created = CuratedExample.objects.using("default").update_or_create(
            source_lead_id=assessment.source_lead_id,
            source_assessment=assessment,
            intent_category=category,
            defaults={
                "client_message": client_message,
                "agent_response": agent_response,
                "quality_scores": scores,
                "approved": False,
                "approved_by": approved_by,
                "approved_at": None,
            },
        )
        return example

    @classmethod
    def approve_example(cls, example_id: int, approved_by=None) -> CuratedExample:
        """Aprueba un ejemplo curado (lo habilita para few-shot)."""
        example = CuratedExample.objects.using("default").get(pk=example_id)
        example.approved = True
        example.active = True
        example.approved_by = approved_by
        example.approved_at = timezone.now()
        example.save(using="default")
        return example

    @classmethod
    def toggle_active(cls, example_id: int, active: bool) -> CuratedExample:
        """Activa/desactiva un ejemplo sin borrarlo (versionado)."""
        example = CuratedExample.objects.using("default").get(pk=example_id)
        example.active = bool(active)
        example.save(using="default", update_fields=["active", "updated_at"])
        return example
