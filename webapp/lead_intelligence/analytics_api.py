# analytics_api.py
#
# Endpoints JSON de analítica de leads para consumo externo (ej. el backend
# DRF del CRM, vía su proxy server-to-server con X-Analytics-API-Key).
# Separado de views.py a propósito: ese archivo es el que se sigue
# extendiendo activamente con el motor IA/dashboards, así que las vistas
# nuevas de este puente viven acá para no aumentar su superficie de cambio.
#
# Reusa de views.py: analytics_access_required (sesión gerencia O API key,
# ya existía ahí junto a management_access_required, que extiende) y
# _parameters (parseo de from/to/cohort compartido por todos los dashboards).
import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .property_dashboard import get_property_dashboard
from .services import get_attention_quality_dashboard, get_hourly_agent_matrix
from .views import (
    _has_fresh_running_run,
    _parameters,
    analytics_access_required,
)


@analytics_access_required
@require_GET
def hourly_agent_matrix_api(request):
    date_from, date_to, _ = _parameters(request)
    data = get_hourly_agent_matrix(date_from, date_to)
    return JsonResponse(data)


@analytics_access_required
@require_GET
def attention_quality_api(request):
    date_from, date_to, _ = _parameters(request)
    data = get_attention_quality_dashboard(
        date_from, date_to, request.GET.get("agent")
    )
    flagged = [
        {
            "lead_id": item["lead_id"],
            "display_name": item["display_name"],
            "agent_name": item["agent_name"],
            "issues": item.get("issues", []),
            "attention_overdue": bool(item.get("attention_overdue")),
            "quality_status": item.get("quality_status"),
        }
        for item in data["flagged_leads"]
    ]
    return JsonResponse(
        {
            "generated_at": data["generated_at"].isoformat(),
            "date_from": str(data["date_from"]),
            "date_to": str(data["date_to"]),
            "analysis_version": data["analysis_version"],
            "selected_agent_id": data["selected_agent_id"],
            "agent_options": [
                {"agent_id": agent_id, "agent_name": agent_name}
                for agent_id, agent_name in data["agent_options"]
            ],
            "agent_rows": data["agent_rows"],
            "overall": data["overall"],
            "flagged": flagged,
        }
    )


@analytics_access_required
@require_GET
def property_dashboard_api(request):
    date_from, date_to, _ = _parameters(request)
    data = get_property_dashboard(date_from, date_to, request.GET)
    return JsonResponse(
        {
            "generated_at": data["generated_at"].isoformat(),
            "date_from": str(data["date_from"]),
            "date_to": str(data["date_to"]),
            "filters": data["filters"],
            "filter_options": data["filter_options"],
            "cards": data["cards"],
            "summary": data["summary"],
            "portfolio_comparison": data["portfolio_comparison"],
            "collection_found": data["collection_found"],
        }
    )


@csrf_exempt
@analytics_access_required
@require_POST
def evaluacion_automatica(request):
    """Dispara una evaluación incremental de leads (canales programada/tiempo real).

    Es el disparador que usa el cron de GitHub Actions (header
    ``X-Analytics-API-Key``, mismo mecanismo que los endpoints de analítica del
    puente externo del CRM). Cuerpo JSON opcional:
        {"stages": "entered"|"contacted"|"bidirectional",
         "lookback_hours": 24,
         "workers": 2}
    Responde 202 al instante; la evaluación corre en un hilo en segundo plano y
    su progreso se ve en "Ejecuciones del analizador" (AnalysisRun/Steps).
    """
    from django.core.management import call_command

    from .management.commands.analyze_lead_conversations import reset_cancel

    try:
        payload = json.loads(request.body or b"{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        payload = {}

    stages = str(payload.get("stages") or "entered")
    if stages not in ("entered", "contacted", "bidirectional"):
        return JsonResponse(
            {"status": "error", "detail": "stages inválido"},
            status=400,
        )
    try:
        lookback_hours = int(payload.get("lookback_hours") or 0)
        workers = int(payload.get("workers") or 2)
    except (TypeError, ValueError):
        return JsonResponse(
            {"status": "error", "detail": "lookback_hours/workers deben ser enteros"},
            status=400,
        )
    if workers < 1 or workers > 8:
        return JsonResponse(
            {"status": "error", "detail": "workers debe estar entre 1 y 8"},
            status=400,
        )

    # Evita superponer evaluaciones (el cron corre cada 15 min y la programada
    # puede tardar más de una pasada): si ya hay un run activo, se omite.
    if _has_fresh_running_run(clean_stale=True):
        return JsonResponse(
            {
                "status": "already_running",
                "stages": stages,
                "lookback_hours": lookback_hours,
            },
            status=202,
        )

    reset_cancel()

    def _ejecutar():
        from io import StringIO

        from django.db import close_old_connections

        close_old_connections()
        try:
            buf = StringIO()
            call_command(
                "analyze_lead_conversations",
                stages=stages,
                lookback_hours=lookback_hours,
                workers=workers,
                stdout=buf,
                stderr=buf,
            )
        finally:
            close_old_connections()

    from threading import Thread

    Thread(target=_ejecutar, daemon=True).start()
    return JsonResponse(
        {"status": "started", "stages": stages, "lookback_hours": lookback_hours},
        status=202,
    )
