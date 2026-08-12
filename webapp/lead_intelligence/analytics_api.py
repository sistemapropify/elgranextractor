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
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .property_dashboard import get_property_dashboard
from .services import get_attention_quality_dashboard, get_hourly_agent_matrix
from .views import _parameters, analytics_access_required


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
