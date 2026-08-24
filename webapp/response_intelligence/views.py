"""Vistas del dashboard del motor de respuestas IA (calidad-motor-ia).

Hermano de ``analisis_crm``: vive en Prometeo (BD ``default``) y el CRM solo se
consulta con SELECT. Reutiliza el patrón de ``lead_intelligence``.
"""

from datetime import datetime

from django.contrib import messages
from django.db import OperationalError, close_old_connections
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from lead_intelligence.views import management_access_required

from .curation import CurationService
from .models import (
    BotResponseDraft,
    BotResponseEvaluation,
    BusinessRule,
    CuratedExample,
)
from .services import get_ai_cost_summary_for_drafts, get_response_dashboard


def _load_dashboard_context(date_from=None, date_to=None):
    """Carga lecturas del dashboard y recupera una desconexión ODBC transitoria."""
    for attempt in range(2):
        try:
            context = get_response_dashboard(date_from=date_from, date_to=date_to)
            context["ai_cost"] = get_ai_cost_summary_for_drafts(
                date_from=date_from, date_to=date_to
            )
            return context
        except OperationalError:
            close_old_connections()
            if attempt:
                raise


def _parse_date_param(raw):
    """Parsea ?desde=YYYY-MM-DD a datetime.date; None si vacío o inválido."""
    if not raw:
        return None
    try:
        return datetime.strptime(str(raw).strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def _resolve_date_range(request):
    """Resuelve el rango de fechas del dashboard (hora local de Perú).

    - Sin parámetros → SOLO HOY (default: la página carga rápido).
    - ?desde=YYYY-MM-DD&hasta=YYYY-MM-DD → rango seleccionado (inclusivo).
    - ?rango=todo → todo el historial (sin filtro de fechas).
    """
    today = timezone.localdate()
    if request.GET.get("rango") == "todo":
        return None, None, "Todo el historial"
    desde = _parse_date_param(request.GET.get("desde"))
    hasta = _parse_date_param(request.GET.get("hasta"))
    if desde or hasta:
        desde = desde or today
        hasta = hasta or today
        if desde > hasta:
            desde, hasta = hasta, desde
        label = f"del {desde:%d/%m/%Y} al {hasta:%d/%m/%Y}"
        return desde, hasta, label
    return today, today, "Hoy"

@management_access_required
def response_dashboard(request):
    """Dashboard de calidad del motor IA: cola de revisión + KPIs + gate."""
    from .shadow import shadow_mode_enabled

    date_from, date_to, filter_label = _resolve_date_range(request)
    context = _load_dashboard_context(date_from=date_from, date_to=date_to)
    context["date_from_iso"] = date_from.isoformat() if date_from else ""
    context["date_to_iso"] = date_to.isoformat() if date_to else ""
    context["filter_label"] = filter_label
    context["shadow_enabled"] = shadow_mode_enabled()
    context["title"] = "Calidad del motor IA de respuestas"
    context["active_tab"] = "engine_ai"
    # Reglas de negocio activas + todas (para gestionarlas desde el dashboard).
    context["business_rules"] = list(
        BusinessRule.objects.using("default").order_by("category", "id")
    )
    context["business_rule_categories"] = BusinessRule.Category.choices
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


@management_access_required
@require_POST
def approve_example(request):
    """Aprueba un ejemplo curado (lo habilita para few-shot en producción)."""
    example = get_object_or_404(
        CuratedExample.objects.using("default"),
        pk=request.POST.get("example_id"),
    )
    try:
        CurationService.approve_example(
            example.pk, approved_by=getattr(request, "current_user", None)
        )
        messages.success(request, f"Ejemplo #{example.pk} aprobado y activado.")
    except Exception as exc:  # noqa: BLE001
        messages.error(request, f"Error al aprobar: {exc}")
    return redirect("response_intelligence:dashboard")


@management_access_required
@require_POST
def toggle_example(request):
    """Activa/desactiva un ejemplo sin borrarlo (versionado)."""
    example = get_object_or_404(
        CuratedExample.objects.using("default"),
        pk=request.POST.get("example_id"),
    )
    active = request.POST.get("active") == "1"
    try:
        CurationService.toggle_active(example.pk, active)
        messages.success(
            request,
            f"Ejemplo #{example.pk} {'activado' if active else 'desactivado'}.",
        )
    except Exception as exc:  # noqa: BLE001
        messages.error(request, f"Error al cambiar estado: {exc}")
    return redirect("response_intelligence:dashboard")


@management_access_required
@require_POST
def suggest_candidates(request):
    """Propone candidatos few-shot desde evaluaciones 'adequate' de lead_intelligence.

    Ejecuta CurationService.suggest_candidates y crea un CuratedExample
    (approved=False) por cada candidato, para aprobación humana.
    """
    try:
        candidates = CurationService.suggest_candidates(
            min_score=80, limit=50
        )
        if not candidates:
            messages.info(request, "No hay candidatos nuevos para curar.")
            return redirect("response_intelligence:dashboard")
        created = 0
        for candidate in candidates:
            try:
                CurationService.promote_to_curated(
                    candidate["assessment_id"],
                    intent_category=candidate["category"],
                )
                created += 1
            except Exception:  # noqa: BLE001
                continue
        messages.success(
            request, f"{created} candidatos few-shot creados (pendientes de aprobación)."
        )
    except Exception as exc:  # noqa: BLE001
        messages.error(request, f"Error al sugerir candidatos: {exc}")
    return redirect("response_intelligence:dashboard")


@management_access_required
@require_POST
def toggle_shadow(request):
    """Activa/desactiva el shadow_live en vivo (switch persistente en BD default).

    No envía nada a WhatsApp: solo hace que el respondedor nocturno genere un
    borrador IA por cada mensaje real para auditar en el dashboard.
    """
    from .models import MotorAIControl

    try:
        control, _created = MotorAIControl.objects.using("default").get_or_create(
            pk=1,
            defaults={"shadow_live_enabled": True},
        )
        control.shadow_live_enabled = not control.shadow_live_enabled
        control.updated_by = getattr(request, "current_user", None)
        control.save(using="default")
        estado = "ACTIVADO" if control.shadow_live_enabled else "DESACTIVADO"
        messages.success(
            request,
            f"Shadow en vivo {estado}. El motor generará borradores "
            f"{'para auditar' if control.shadow_live_enabled else 'solo si la variable de entorno lo permite'}.",
        )
    except Exception as exc:  # noqa: BLE001
        messages.error(request, f"Error al cambiar el switch: {exc}")
    return redirect("response_intelligence:dashboard")


# --------------------------------------------------------------------------- #
# Reglas de negocio del motor (se inyectan al prompt del sistema)
# --------------------------------------------------------------------------- #
@management_access_required
@require_POST
def create_rule(request):
    """Crea una regla de negocio que se inyecta al prompt del sistema."""
    rule_text = request.POST.get("rule_text", "").strip()
    category = request.POST.get("category", "")
    try:
        if not rule_text:
            raise ValueError("El texto de la regla no puede estar vacío")
        if category not in BusinessRule.Category.values:
            raise ValueError("Categoría inválida")
        rule = BusinessRule.objects.using("default").create(
            rule_text=rule_text,
            category=category,
            active=True,
        )
        messages.success(
            request,
            f"Regla #{rule.pk} creada en '{rule.get_category_display()}'. "
            "Aplica al prompt de los próximos drafts.",
        )
    except Exception as exc:  # noqa: BLE001
        messages.error(request, f"Error al crear la regla: {exc}")
    return redirect("response_intelligence:dashboard")


@management_access_required
@require_POST
def edit_rule(request):
    """Edita el texto y/o la categoría de una regla de negocio existente."""
    rule = _get_rule_or_redirect(request, request.POST.get("rule_id"))
    if rule is None:
        return redirect("response_intelligence:dashboard")
    rule_text = request.POST.get("rule_text", "").strip()
    category = request.POST.get("category", "")
    try:
        if not rule_text:
            raise ValueError("El texto de la regla no puede estar vacío")
        if category not in BusinessRule.Category.values:
            raise ValueError("Categoría inválida")
        rule.rule_text = rule_text
        rule.category = category
        rule.save(using="default")
        messages.success(
            request,
            f"Regla #{rule.pk} actualizada (aplica al prompt de los próximos drafts).",
        )
    except Exception as exc:  # noqa: BLE001
        messages.error(request, f"Error al actualizar la regla: {exc}")
    return redirect("response_intelligence:dashboard")


def _get_rule_or_redirect(request, rule_id):
    """Resuelve una regla o redirige con mensaje (evita 404 crudo si el id
    ya no existe, llegó vacío o la página estaba desactualizada)."""
    try:
        rule_id = int(rule_id)
    except (TypeError, ValueError):
        messages.error(request, "Regla inválida: falta el identificador.")
        return None
    rule = BusinessRule.objects.using("default").filter(pk=rule_id).first()
    if rule is None:
        messages.error(
            request,
            f"La regla #{rule_id} ya no existe (fue eliminada o la página "
            "estaba desactualizada). Recarga la página.",
        )
        return None
    return rule


@management_access_required
@require_POST
def toggle_rule(request):
    """Activa/desactiva una regla de negocio."""
    rule = _get_rule_or_redirect(request, request.POST.get("rule_id"))
    if rule is None:
        return redirect("response_intelligence:dashboard")
    try:
        rule.active = not rule.active
        rule.save(using="default")
        messages.success(
            request,
            f"Regla #{rule.pk} {'activada' if rule.active else 'desactivada'} "
            "(deja de inyectarse al prompt).",
        )
    except Exception as exc:  # noqa: BLE001
        messages.error(request, f"Error al cambiar la regla: {exc}")
    return redirect("response_intelligence:dashboard")


@management_access_required
@require_POST
def delete_rule(request):
    """Elimina una regla de negocio (no se inyectará más al prompt)."""
    rule = _get_rule_or_redirect(request, request.POST.get("rule_id"))
    if rule is None:
        return redirect("response_intelligence:dashboard")
    try:
        pk = rule.pk
        rule.delete(using="default")
        messages.success(request, f"Regla #{pk} eliminada.")
    except Exception as exc:  # noqa: BLE001
        messages.error(request, f"Error al eliminar la regla: {exc}")
    return redirect("response_intelligence:dashboard")
