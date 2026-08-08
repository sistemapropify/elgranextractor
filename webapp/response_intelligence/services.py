"""Agregación para el dashboard del motor de respuestas IA (calidad-motor-ia).

Todo se lee de la BD ``default``. El CRM solo se consulta con SELECT.
"""

from django.db.models import Count, Q, Sum

from response_intelligence.models import (
    BotResponseDraft,
    BotResponseEvaluation,
    CuratedExample,
)


def _safe_pct(part, total):
    return round(part / total * 100) if total else 0


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

    kpis = {
        "total_drafts": len(drafts),
        "pending": len(pending),
        "reviewed": total_evals,
        "would_send_pct": _safe_pct(would_send, total_evals),
        "hallucination_pct": _safe_pct(hallucination, total_evals),
        "tone_pct": _safe_pct(tone, total_evals),
        "incorrect_pct": _safe_pct(incorrect, total_evals),
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

    return {
        "drafts": drafts,
        "evaluated": evaluated,
        "pending": pending,
        "kpis": kpis,
        "by_category": by_category,
        "curated": curated,
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
