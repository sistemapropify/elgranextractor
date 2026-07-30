from datetime import date, timedelta
from functools import wraps

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from intelligence.permissions import get_user_profile

from .services import (
    LEAD_RESULT_STAGES,
    get_analysis_quality_dashboard,
    get_attention_quality_dashboard,
    get_lead_conversation,
    get_lead_results,
    get_management_dashboard,
    normalized_period,
    save_conversation_review,
)


def _parameters(request):
    date_from, date_to = normalized_period(
        request.GET.get("from"), request.GET.get("to")
    )
    try:
        cohort_raw = request.GET.get("cohort", "").strip()
        cohort_date = date.fromisoformat(cohort_raw) if cohort_raw else None
    except ValueError:
        cohort_date = None
    return date_from, date_to, cohort_date


def management_access_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        django_user = getattr(request, "user", None)
        if getattr(django_user, "is_superuser", False):
            return view_func(request, *args, **kwargs)

        profile = get_user_profile(request)
        domains = set(getattr(profile, "allowed_domains", []) or [])
        if profile and profile.level >= 3 and (
            "gerencia" in domains or profile.level >= 5
        ):
            return view_func(request, *args, **kwargs)

        if request.path.startswith("/analisis-crm/api/"):
            return JsonResponse(
                {"detail": "Acceso reservado para gerencia y supervisión."},
                status=403,
            )
        return HttpResponseForbidden(
            "Acceso reservado para gerencia y supervisión."
        )

    return wrapped


@management_access_required
def management_dashboard(request):
    date_from, date_to, _ = _parameters(request)
    context = get_management_dashboard(date_from, date_to, None)
    context["title"] = "Inteligencia de Leads"
    context["active_tab"] = "overview"
    return render(request, "lead_intelligence/overview_dashboard.html", context)


@management_access_required
def cohorts_dashboard(request):
    today = timezone.localdate()
    try:
        cohort_date = date.fromisoformat(request.GET.get("cohort", "").strip())
    except (TypeError, ValueError):
        cohort_date = today
    if cohort_date > today:
        cohort_date = today
    context = get_management_dashboard(cohort_date, cohort_date, cohort_date)
    context["previous_day"] = cohort_date - timedelta(days=1)
    context["next_day"] = (
        cohort_date + timedelta(days=1) if cohort_date < today else None
    )
    context["today"] = today
    context["title"] = "Cohortes de Leads"
    context["active_tab"] = "cohorts"
    return render(request, "lead_intelligence/cohort_dashboard.html", context)


@management_access_required
def attention_quality_dashboard(request):
    date_from, date_to, _ = _parameters(request)
    context = get_attention_quality_dashboard(
        date_from,
        date_to,
        request.GET.get("agent"),
    )
    context["title"] = "Calidad de atención"
    context["active_tab"] = "attention"
    return render(
        request,
        "lead_intelligence/attention_quality_dashboard.html",
        context,
    )


@management_access_required
def analysis_quality_dashboard(request):
    date_from, date_to, _ = _parameters(request)
    context = get_analysis_quality_dashboard(date_from, date_to)
    context["title"] = "Calidad del motor IA"
    context["active_tab"] = "engine"
    return render(
        request,
        "lead_intelligence/analysis_quality_dashboard.html",
        context,
    )


@management_access_required
@require_POST
def conversation_review(request):
    try:
        lead_id = int(request.POST.get("lead_id", ""))
        reviewer = (
            request.user
            if getattr(request.user, "is_authenticated", False)
            else None
        )
        save_conversation_review(
            source_lead_id=lead_id,
            history_hash=request.POST.get("history_hash", ""),
            analysis_version=request.POST.get("analysis_version", ""),
            stage=request.POST.get("stage", ""),
            verdict=request.POST.get("verdict", ""),
            human_value=request.POST.get("human_value", ""),
            notes=request.POST.get("notes", ""),
            reviewed_by=reviewer,
        )
        messages.success(request, "Revisión humana guardada.")
    except (TypeError, ValueError) as exc:
        messages.error(request, str(exc))

    next_url = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = "/analisis-crm/calidad-motor/"
    return redirect(next_url)


@management_access_required
def lead_results(request):
    cohort_raw = request.GET.get("cohort", "").strip()
    try:
        cohort_date = date.fromisoformat(cohort_raw) if cohort_raw else None
    except ValueError:
        cohort_date = None
    if cohort_date:
        date_from = date_to = min(cohort_date, timezone.localdate())
        origin = "cohorts"
    else:
        date_from, date_to, _ = _parameters(request)
        origin = "overview"
    stage = request.GET.get("stage", "entered")
    result = get_lead_results(date_from, date_to, stage)
    page_obj = Paginator(result.pop("leads"), 24).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    return render(
        request,
        "lead_intelligence/lead_results.html",
        {
            **result,
            "page_obj": page_obj,
            "date_from": date_from,
            "date_to": date_to,
            "cohort_date": cohort_date,
            "origin": origin,
            "query_without_page": query.urlencode(),
            "current_query": request.GET.urlencode(),
            "stage_options": LEAD_RESULT_STAGES,
            "title": f"{result['stage_label']} · Leads",
        },
    )


@management_access_required
def lead_conversation(request, lead_id):
    lead = get_lead_conversation(lead_id)
    if lead is None:
        raise Http404("Lead no encontrado")
    return render(
        request,
        "lead_intelligence/lead_conversation.html",
        {
            "lead": lead,
            "back_query": request.GET.urlencode(),
            "title": f"Conversación · {lead['display_name']}",
        },
    )


@management_access_required
@require_GET
def management_summary_api(request):
    date_from, date_to, cohort_date = _parameters(request)
    data = get_management_dashboard(date_from, date_to, cohort_date)
    return JsonResponse(
        {
            "generated_at": data["generated_at"].isoformat(),
            "period": {"from": str(date_from), "to": str(date_to)},
            "cohort_date": str(cohort_date) if cohort_date else None,
            "overview": data["overview"],
            "incoming_leads": data["incoming_leads"],
            "selected_cohort": data["selected_cohort"],
            "cohorts": [
                {**row, "cohort_date": str(row["cohort_date"])}
                for row in data["cohorts"]
            ],
            "data_quality": data["data_quality"],
        }
    )
