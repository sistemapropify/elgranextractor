"""Agregación para el dashboard del motor de respuestas IA (calidad-motor-ia).

Todo se lee de la BD ``default``. El CRM solo se consulta con SELECT.
"""

from datetime import datetime, time as dtime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

from django.db.models import Count, Q, Sum
from django.utils import timezone

from lead_intelligence.services import (
    get_lead_conversation,
    get_lead_conversation_by_identity,
)

from response_intelligence.models import (
    BotResponseDraft,
    BotResponseEvaluation,
    CuratedExample,
)

from response_intelligence.shadow_context import (
    assign_drafts_to_lead_messages,
    draft_context,
    find_trigger_index,
    source_position,
)

def _safe_pct(part, total):
    return round(part / total * 100) if total else 0


def _find_trigger_message(messages, client_message, stored_position=None):
    """Locate the exact lead message that triggered a draft."""
    index = find_trigger_index(messages, client_message, stored_position=stored_position)
    return (index, messages[index]) if index is not None else (None, None)


def _build_shadow_context(draft, conversation, shadow_drafts=None):
    """Attach a comparison payload for the dashboard."""

    if not conversation:
        return {
            "available": False,
            "trigger_index": None,
            "trigger_message": None,
            "human_reply": None,
            "human_replies": [],
            "excerpt": [],
            "shadow_messages": [],
            "thread": {},
        }

    messages = conversation.get("messages") or []
    trigger_index, trigger_message = _find_trigger_message(
        messages, draft.client_message,
        stored_position=source_position(draft),
    )
    if trigger_index is None:
        trigger_index = next(
            (index for index, item in enumerate(messages) if item.get("sender") == "lead"),
            None,
        )
        trigger_message = messages[trigger_index] if trigger_index is not None else None

    human_replies = []
    if trigger_index is not None:
        human_replies = [
            message
            for message in messages[trigger_index + 1 :]
            if message.get("sender") == "agent"
        ]

    excerpt = []
    if trigger_index is not None:
        start = max(0, trigger_index - 2)
        end = min(len(messages), trigger_index + 6)
        excerpt = messages[start:end]
    else:
        excerpt = messages[:8]

    assigned_drafts = assign_drafts_to_lead_messages(
        messages, shadow_drafts or [draft]
    )
    shadow_messages = []
    for index, message in enumerate(messages):
        if message.get("sender") != "lead":
            continue
        shadow_messages.append(message)
        matching_draft = assigned_drafts.get(index)
        if matching_draft:
            shadow_messages.append(
                {
                    "sender": "agent",
                    "text": getattr(matching_draft, "generated_response", "") or "",
                    "timestamp": getattr(matching_draft, "created_at", None),
                    "shadow": True,
                    "draft_id": getattr(matching_draft, "pk", None),
                }
            )

    return {
        "available": True,
        "trigger_index": trigger_index,
        "trigger_message": trigger_message,
        "human_reply": human_replies[0] if human_replies else None,
        "human_replies": human_replies[:3],
        "excerpt": excerpt,
        "shadow_messages": shadow_messages,
        "thread": conversation,
    }


def _local_day_start_utc(day):
    """Inicio del día (Perú) convertido a UTC, para filtrar created_at.

    ``created_at`` se almacena en UTC (USE_TZ=True); los días del filtro se
    interpretan en la zona local de la app (America/Lima).
    """
    tz = ZoneInfo("America/Lima")
    local = datetime.combine(day, dtime.min, tzinfo=tz)
    return local.astimezone(dt_timezone.utc)


def get_response_dashboard(limit: int = 150, date_from=None, date_to=None):
    """Datos del dashboard: cola de revisión, KPIs y distribución por categoría.

    ``date_from``/``date_to`` son ``datetime.date`` en hora local (Perú) e
    inclusivos (``date_to`` incluye todo su día). Sin fechas, se devuelve todo
    el historial (capado por ``limit``); la vista decide el default "hoy".
    """
    base_qs = BotResponseDraft.objects.using("default")
    if date_from is not None:
        base_qs = base_qs.filter(created_at__gte=_local_day_start_utc(date_from))
    if date_to is not None:
        base_qs = base_qs.filter(
            created_at__lt=_local_day_start_utc(date_to + timedelta(days=1))
        )
    drafts = list(base_qs.order_by("-created_at")[:limit])
    draft_ids = [d.pk for d in drafts]
    evaluated = {
        ev.draft_id: ev
        for ev in BotResponseEvaluation.objects.using("default").filter(
            draft_id__in=draft_ids
        )
    }
    pending = [d for d in drafts if d.pk not in evaluated]

    eval_range = {}
    if date_from is not None:
        eval_range["draft__created_at__gte"] = _local_day_start_utc(date_from)
    if date_to is not None:
        eval_range["draft__created_at__lt"] = _local_day_start_utc(
            date_to + timedelta(days=1)
        )
    evals = BotResponseEvaluation.objects.using("default").filter(**eval_range)
    total_evals = evals.count()
    would_send = evals.filter(would_send=True).count()
    hallucination = evals.filter(hallucination_flag=True).count()
    tone = evals.filter(tone_flag=True).count()
    incorrect = evals.filter(verdict=BotResponseEvaluation.Verdict.INCORRECT).count()

    # Guardrails automáticos (spec §7): agregados sobre el rango seleccionado.
    drafts_qs = base_qs
    total_drafts_all = drafts_qs.count()
    auto_escalations = drafts_qs.filter(auto_escalation=True).count()
    auto_hallucinations = drafts_qs.filter(auto_hallucination=True).count()
    auto_discounts = drafts_qs.filter(auto_discount=True).count()
    auto_blocked = drafts_qs.exclude(blocked_reason="").count()

    kpis = {
        "total_drafts": len(drafts),
        "pending": len(pending),
        "reviewed": total_evals,
        "would_send_pct": _safe_pct(would_send, total_evals),
        "hallucination_pct": _safe_pct(hallucination, total_evals),
        "tone_pct": _safe_pct(tone, total_evals),
        "incorrect_pct": _safe_pct(incorrect, total_evals),
        "total_drafts_all": total_drafts_all,
        "auto_escalations": auto_escalations,
        "auto_hallucinations": auto_hallucinations,
        "auto_discounts": auto_discounts,
        "auto_blocked": auto_blocked,
        "auto_escalation_pct": _safe_pct(auto_escalations, total_drafts_all),
        "auto_hallucination_pct": _safe_pct(auto_hallucinations, total_drafts_all),
        "auto_discount_pct": _safe_pct(auto_discounts, total_drafts_all),
    }

    by_category = {
        item["intent_category"]: item["total"]
        for item in (
            base_qs.filter(intent_category__in=CuratedExample.IntentCategory.values)
            .values("intent_category")
            .annotate(total=Count("id"))
            .order_by("-total")
        )
    }

    curated = {
        "total": CuratedExample.objects.using("default").count(),
        "approved": CuratedExample.objects.using("default")
        .filter(approved=True, active=True)
        .count(),
    }
    curated_examples = list(
        CuratedExample.objects.using("default").order_by(
            "-approved", "-created_at"
        )[:60]
    )

    conversation_cache = {}
    # La tarjeta debe mostrar el hilo sombra completo, no solo los drafts que
    # caben en el filtro de fecha/paginación actual.
    related_drafts = list(
        BotResponseDraft.objects.using("default")
        .filter(mode=BotResponseDraft.Mode.SHADOW_LIVE)
        .order_by("-created_at", "-id")[:2000]
    )
    related_drafts.reverse()

    for draft in pending:
        lead_id = draft.source_lead_id
        prompt_context = draft_context(draft)
        thread_id = prompt_context.get("thread_id")
        phone = prompt_context.get("phone")
        cache_key = ("lead", lead_id) if lead_id else ("identity", thread_id, phone)
        if cache_key not in conversation_cache:
            if lead_id:
                conversation_cache[cache_key] = get_lead_conversation(lead_id)
            else:
                conversation_cache[cache_key] = get_lead_conversation_by_identity(
                    thread_id=thread_id,
                    phone=phone,
                )
        conversation = conversation_cache.get(cache_key)

        phone_digits = "".join(ch for ch in str(phone or "") if ch.isdigit())[-9:]
        comparison_drafts = []
        for item in related_drafts:
            item_context = draft_context(item)
            item_phone = "".join(
                ch for ch in str(item_context.get("phone") or "") if ch.isdigit()
            )[-9:]
            same_lead = bool(lead_id and item.source_lead_id == lead_id)
            same_thread = bool(
                thread_id and str(item_context.get("thread_id") or "") == str(thread_id)
            )
            same_phone = bool(phone_digits and item_phone == phone_digits)
            if same_lead or same_thread or same_phone:
                comparison_drafts.append(item)

        draft.shadow_context = _build_shadow_context(
            draft,
            conversation,
            shadow_drafts=comparison_drafts or [draft],
        )

    return {
        "drafts": drafts,
        "evaluated": evaluated,
        "pending": pending,
        "kpis": kpis,
        "by_category": by_category,
        "curated": curated,
        "curated_examples": curated_examples,
    }


def get_ai_cost_summary_for_drafts(date_from=None, date_to=None):
    """Costo IA total/promedio de los drafts (trace_id='bot_draft:*').

    Acepta el mismo rango de fechas que el dashboard para que el KPI coincida
    con la cola visible; sin fechas agrega todo el historial.
    """
    from intelligence.models import AIConsumptionLog

    qs = AIConsumptionLog.objects.using("default").filter(
        success=True, trace_id__startswith="bot_draft:"
    )
    if date_from is not None:
        qs = qs.filter(created_at__gte=_local_day_start_utc(date_from))
    if date_to is not None:
        qs = qs.filter(
            created_at__lt=_local_day_start_utc(date_to + timedelta(days=1))
        )
    agg = qs.aggregate(total=Sum("estimated_cost_usd"), calls=Count("id"))
    total = float(agg["total"] or 0)
    calls = int(agg["calls"] or 0)
    return {
        "total_usd": total,
        "calls": calls,
        "avg_usd": (total / calls) if calls else 0.0,
    }
