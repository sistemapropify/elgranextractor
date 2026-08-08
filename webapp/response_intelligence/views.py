"""Vistas del dashboard del motor de respuestas IA (calidad-motor-ia).

Hermano de ``analisis_crm``: vive en Prometeo (BD ``default``) y el CRM solo se
consulta con SELECT. Reutiliza el patrón de ``lead_intelligence``.
"""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from lead_intelligence.views import management_access_required

from .curation import CurationService
from .models import BotResponseDraft, BotResponseEvaluation, CuratedExample
from .services import get_ai_cost_summary_for_drafts, get_response_dashboard


@management_access_required
def response_dashboard(request):
    """Dashboard de calidad del motor IA: cola de revisión + KPIs + gate."""
    context = get_response_dashboard()
    context["ai_cost"] = get_ai_cost_summary_for_drafts()
    context["title"] = "Calidad del motor IA de respuestas"
    context["active_tab"] = "engine_ai"
    return render(
        request,
        "response_intelligence/response_dashboard.html",
        context,
    )


@management_access_required
@require_POST
def evaluate_draft(request):
    """Guarda la revisión humana de un draft (BotResponseEvaluation)."""
    draft = get_object_or_404(
        BotResponseDraft.objects.using("default"), pk=request.POST.get("draft_id")
    )
    try:
        verdict = request.POST["verdict"]
        if verdict not in BotResponseEvaluation.Verdict.values:
            raise ValueError("Veredicto inválido")
        BotResponseEvaluation.objects.using("default").update_or_create(
            draft=draft,
            defaults={
                "verdict": verdict,
                "hallucination_flag": request.POST.get("hallucination") == "1",
                "tone_flag": request.POST.get("tone") == "1",
                "would_send": request.POST.get("would_send") == "1",
                "notes": request.POST.get("notes", "").strip(),
                "reviewed_by": getattr(request, "current_user", None),
            },
        )
        messages.success(request, "Evaluación guardada.")
    except (ValueError, KeyError) as exc:
        messages.error(request, f"Error al evaluar: {exc}")
    return redirect("response_intelligence:dashboard")


@management_access_required
@require_POST
def promote_draft(request):
    """Promueve un draft bien evaluado a ejemplo few-shot (cierra el loop)."""
    draft = get_object_or_404(
        BotResponseDraft.objects.using("default"), pk=request.POST.get("draft_id")
    )
    try:
        example = CurationService.promote_to_curated_from_draft(
            draft,
            approved_by=getattr(request, "current_user", None),
        )
        messages.success(
            request,
            f"Ejemplo curado #{example.pk} creado para '{example.intent_category}' "
            "(queda pendiente de aprobación).",
        )
    except Exception as exc:  # noqa: BLE001
        messages.error(request, f"Error al promover: {exc}")
    return redirect("response_intelligence:dashboard")
