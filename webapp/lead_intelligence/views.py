from datetime import date
from functools import wraps

from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from intelligence.permissions import get_user_profile

from .services import get_management_dashboard, normalized_period


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
    return render(request, "lead_intelligence/overview_dashboard.html", context)


@management_access_required
def cohorts_dashboard(request):
    date_from, date_to, cohort_date = _parameters(request)
    if cohort_date is None or not (date_from <= cohort_date <= date_to):
        cohort_date = date_to
    context = get_management_dashboard(date_from, date_to, cohort_date)
    context["title"] = "Cohortes de Leads"
    return render(request, "lead_intelligence/cohort_dashboard.html", context)


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
            "selected_cohort": data["selected_cohort"],
            "cohorts": [
                {**row, "cohort_date": str(row["cohort_date"])}
                for row in data["cohorts"]
            ],
            "data_quality": data["data_quality"],
            "qualification_ready": data["qualification_ready"],
        }
    )
