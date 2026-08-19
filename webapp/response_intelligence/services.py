"""Agregación para el dashboard del motor de respuestas IA (calidad-motor-ia).

Todo se lee de la BD ``default``. El CRM solo se consulta con SELECT.
"""

from django.db.models import Count, Q, Sum

from lead_intelligence.conversation_analysis import normalize_text
from lead_intelligence.services import (
    get_lead_conversation,
    get_lead_conversation_by_identity,
)

from response_intelligence.models import (
    BotResponseDraft,
    BotResponseEvaluation,
    CuratedExample,
)


def _safe_pct(part, total):
    return round(part / total * 100) if total else 0


def _find_trigger_message(messages, client_message):
    """Locate the lead message that triggered a draft, if possible."""

    target = normalize_text(client_message)
    if not target:
        return None, None
    for index, message in enumerate(messages or []):
        if message.get("sender") != "lead":
            continue
        if normalize_text(message.get("text")) == target:
            return index, message
    return None, None


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
        messages, draft.client_message
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

    draft_by_message = {}
    for item in shadow_drafts or [draft]:
        key = normalize_text(getattr(item, "client_message", ""))
        if key and key not in draft_by_message:
            draft_by_message[key] = item

    shadow_messages = []
    for message in messages:
        if message.get("sender") != "lead":
            continue
        shadow_messages.append(message)
        matching_draft = draft_by_message.get(normalize_text(message.get("text")))
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


def get_response_dashboard(limit: int = 150):
    """Datos del dashboard: cola de revisión, KPIs y distribución por categoría."""
    drafts = list(
        BotResponseDraft.objects.using("default").order_by("-created_at")[:limit]
    )
    draft_ids = [d.pk for d in drafts]
    evaluated = {
        ev.draft_id: ev
        for ev in BotResponseEvaluation.objects.using("default").filter(
            draft_id__in=draft_ids
        )
    }
    pending = [d for d in drafts if d.pk not in evaluated]

    evals = BotResponseEvaluation.objects.using("default").all()
    total_evals = evals.count()
    would_send = evals.filter(would_send=True).count()
    hallucination = evals.filter(hallucination_flag=True).count()
    tone = evals.filter(tone_flag=True).count()
    incorrect = evals.filter(verdict=BotResponseEvaluation.Verdict.INCORRECT).count()

    # Guardrails automáticos (spec §7): agregados sobre todos los drafts.
    drafts_qs = BotResponseDraft.objects.using("default")
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
            BotResponseDraft.objects.using("default")
            .filter(intent_category__in=CuratedExample.IntentCategory.values)
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
    drafts_by_lead = {}
    for item in drafts:
        if item.source_lead_id:
            drafts_by_lead.setdefault(item.source_lead_id, []).append(item)
    for draft in pending:
        lead_id = draft.source_lead_id
        prompt_snapshot = draft.prompt_snapshot or {}
        prompt_context = prompt_snapshot.get("context") or {}
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
        draft.shadow_context = _build_shadow_context(
            draft,
            conversation,
            shadow_drafts=drafts_by_lead.get(lead_id, [draft]) if lead_id else [draft],
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


def get_ai_cost_summary_for_drafts():
    """Costo IA total/promedio de los drafts (trace_id='bot_draft:*')."""
    from intelligence.models import AIConsumptionLog

    qs = (
        AIConsumptionLog.objects.using("default")
        .filter(success=True, trace_id__startswith="bot_draft:")
        .aggregate(total=Sum("estimated_cost_usd"), calls=Count("id"))
    )
    total = float(qs["total"] or 0)
    calls = int(qs["calls"] or 0)
    return {
        "total_usd": total,
        "calls": calls,
        "avg_usd": (total / calls) if calls else 0.0,
    }
