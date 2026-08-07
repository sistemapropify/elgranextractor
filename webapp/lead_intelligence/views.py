from datetime import date, timedelta
from functools import wraps

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from intelligence.permissions import get_user_profile

from .contextual_analysis import ANALYSIS_VERSION
from .models import AnalysisRun
from .property_dashboard import get_property_dashboard
from .services import (
    LEAD_RESULT_STAGES,
    get_analysis_quality_dashboard,
    get_attention_quality_dashboard,
    get_hourly_agent_matrix,
    get_lead_conversation,
    get_lead_results,
    get_management_dashboard,
    normalized_period,
    save_conversation_review,
)


def _parameters(request):
    # El botón "Ejecutar evaluación IA" hace POST con las fechas en el body;
    # los GET solo llevan fechas en la querystring. Se lee POST primero y se
    # cae a GET, para que las fechas filtradas siempre se respeten.
    date_from_raw = request.POST.get("from") or request.GET.get("from")
    date_to_raw = request.POST.get("to") or request.GET.get("to")
    date_from, date_to = normalized_period(date_from_raw, date_to_raw)
    try:
        cohort_raw = (
            request.POST.get("cohort")
            or request.GET.get("cohort")
            or ""
        ).strip()
        cohort_date = date.fromisoformat(cohort_raw) if cohort_raw else None
    except ValueError:
        cohort_date = None
    return date_from, date_to, cohort_date


RUN_STALE_MINUTES = 10


def _stale_cutoff():
    return timezone.now() - timedelta(minutes=RUN_STALE_MINUTES)


def _has_fresh_running_run(*, clean_stale=False):
    """True si hay una ejecución en curso con latido reciente.

    Con ``clean_stale=True`` además marca como fallidas las ejecuciones cuyo
    último latido es antiguo (quedaron en ``running`` por una interrupción,
    p. ej. reinicio del servidor o timeout de la petición), para que el botón
    "Ejecutar evaluación IA" no quede bloqueado para siempre.
    """
    qs = AnalysisRun.objects.using("default").filter(
        status=AnalysisRun.Status.RUNNING,
        rules_version=ANALYSIS_VERSION,
    )
    cutoff = _stale_cutoff()
    if clean_stale:
        stale_ids = list(
            qs.filter(heartbeat_at__lt=cutoff).values_list("pk", flat=True)
        )
        if stale_ids:
            AnalysisRun.objects.using("default").filter(pk__in=stale_ids).update(
                status=AnalysisRun.Status.FAILED,
                completed_at=timezone.now(),
                error_summary=(
                    "Ejecución interrumpida (latido vencido); marcada como "
                    "fallida para permitir relanzar."
                ),
            )
    return qs.filter(heartbeat_at__gte=cutoff).exists()


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
    context["hourly_matrix"] = get_hourly_agent_matrix(
        cohort_date, cohort_date
    )
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
    context["analysis_running"] = _has_fresh_running_run()
    context["title"] = "Calidad del motor IA"
    context["active_tab"] = "engine"
    return render(
        request,
        "lead_intelligence/analysis_quality_dashboard.html",
        context,
    )


@management_access_required
def analysis_progress_api(request):
    """API en vivo del progreso de la evaluación (terminal + contadores)."""
    from django.http import JsonResponse

    from lead_intelligence.models import AnalysisRun, AnalysisRunStep

    from datetime import date as date_cls

    run_id = request.GET.get("run_id", "").strip()
    from_raw = request.GET.get("from", "").strip()
    to_raw = request.GET.get("to", "").strip()

    def _parse_period(value):
        try:
            return date_cls.fromisoformat(value)
        except (TypeError, ValueError):
            return None

    period_from = _parse_period(from_raw)
    period_to = _parse_period(to_raw)

    if run_id:
        run = AnalysisRun.objects.using("default").filter(pk=run_id).first()
    else:
        # 1) Ejecución en curso (siempre visible en vivo).
        run = (
            AnalysisRun.objects.using("default")
            .filter(status=AnalysisRun.Status.RUNNING)
            .order_by("-started_at")
            .first()
        )
        # 2) Sin ejecución en curso: run del periodo filtrado (coherente con KPIs).
        if run is None and period_from and period_to:
            run = (
                AnalysisRun.objects.using("default")
                .filter(
                    date_from=period_from,
                    date_to=period_to,
                )
                .order_by("-started_at")
                .first()
            )
        # 3) Sin periodo filtrado: último run global.
        if run is None and not (period_from and period_to):
            run = (
                AnalysisRun.objects.using("default")
                .order_by("-started_at")
                .first()
            )
    if run is None:
        return JsonResponse({"run": None})

    processed = run.leads_analyzed + run.leads_skipped + run.leads_failed
    steps = list(
        AnalysisRunStep.objects.using("default")
        .filter(run=run)
        .order_by("created_at", "id")[:400]
    )
    return JsonResponse(
        {
            "run": {
                "id": run.pk,
                "status": run.status,
                "status_label": run.get_status_display(),
                "leads_total": run.leads_total,
                "leads_analyzed": run.leads_analyzed,
                "leads_skipped": run.leads_skipped,
                "leads_failed": run.leads_failed,
                "processed": processed,
                "progress_pct": (
                    round(processed / run.leads_total * 100)
                    if run.leads_total
                    else 0
                ),
                "started_at": (
                    run.started_at.isoformat() if run.started_at else None
                ),
                "completed_at": (
                    run.completed_at.isoformat() if run.completed_at else None
                ),
                "heartbeat_at": (
                    run.heartbeat_at.isoformat() if run.heartbeat_at else None
                ),
                "error_summary": run.error_summary,
            },
            "steps": [
                {
                    "status": step.status,
                    "lead_id": step.lead_id,
                    "message": step.message,
                    "created_at": step.created_at.isoformat(),
                }
                for step in steps
            ],
        }
    )


@management_access_required
def property_performance_dashboard(request):
    date_from, date_to, _ = _parameters(request)
    context = get_property_dashboard(date_from, date_to, request.GET)
    page_obj = Paginator(context.pop("cards"), 18).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    context.update(
        {
            "page_obj": page_obj,
            "query_without_page": query.urlencode(),
            "title": "Rendimiento por propiedades",
            "active_tab": "properties",
        }
    )
    return render(
        request,
        "lead_intelligence/property_performance_dashboard.html",
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
@require_POST
def run_analysis(request):
    """Dispara el análisis IA (DeepSeek) de conversaciones de leads.

    Con un broker Celery real la ejecución se encola en segundo plano; con el
    broker memory:// actual se ejecuta el comando de forma síncrona para que el
    botón funcione siempre. El comando es incremental y registra su progreso en
    ``AnalysisRun`` (modelo ``lead_intelligence.AnalysisRun``).
    """
    from io import StringIO

    from django.core.management import call_command

    from colas.celery import app as celery_app

    from .tasks import analizar_conversaciones_lead
    from .management.commands.analyze_lead_conversations import reset_cancel

    date_from, date_to, _ = _parameters(request)
    force = request.POST.get("force") == "1"
    period = f"{date_from.isoformat()} → {date_to.isoformat()}"
    back_url = (
        f"{reverse('analisis_crm:analysis_quality')}"
        f"?from={date_from.isoformat()}&to={date_to.isoformat()}"
    )

    already_running = _has_fresh_running_run(clean_stale=True)
    if already_running:
        messages.error(
            request,
            "Ya hay una ejecución del analizador en curso. "
            "Usa “Detener ejecución” o espera a que termine antes de lanzar otra.",
        )
        return redirect(back_url)

    # Limpiar cualquier señal de cancelación previa antes de iniciar.
    reset_cancel()

    broker = str(getattr(celery_app.conf, "broker_url", "") or "")
    async_capable = not broker.startswith("memory")
    if async_capable:
        analizar_conversaciones_lead.delay(
            date_from=date_from.isoformat(),
            date_to=date_to.isoformat(),
            force=force,
        )
        messages.success(
            request,
            f"Análisis IA encolado para el periodo {period}. "
            "Consulta el progreso en “Ejecuciones del analizador”.",
        )
    else:
        # Broker memory:// (sin worker distribuible): ejecutamos el análisis en
        # un hilo en segundo plano para que el botón responda al instante y el
        # progreso se vea en "Ejecuciones del analizador" (latido cada 10 leads).
        from threading import Thread

        def _ejecutar_analisis():
            from django.db import close_old_connections

            close_old_connections()
            try:
                buf = StringIO()
                call_command(
                    "analyze_lead_conversations",
                    date_from=date_from.isoformat(),
                    date_to=date_to.isoformat(),
                    force=force,
                    stdout=buf,
                    stderr=buf,
                )
            finally:
                close_old_connections()

        Thread(target=_ejecutar_analisis, daemon=True).start()
        messages.success(
            request,
            f"Análisis IA iniciado en segundo plano para el periodo {period}. "
            "Consulta el progreso en “Ejecuciones del analizador”.",
        )

    return redirect(back_url)


@management_access_required
@require_POST
def cancel_analysis(request):
    """Detiene cooperativamente la ejecución de análisis en curso.

    Marca las corridas activas como fallidas y activa la señal de cancelación
    para que el comando deje de llamar a DeepSeek (corta el gasto de tokens).
    """
    from .management.commands.analyze_lead_conversations import request_cancel

    request_cancel()
    updated = AnalysisRun.objects.using("default").filter(
        status=AnalysisRun.Status.RUNNING,
        rules_version=ANALYSIS_VERSION,
    ).update(
        status=AnalysisRun.Status.FAILED,
        completed_at=timezone.now(),
        error_summary="Cancelada por el usuario desde el dashboard.",
    )
    messages.success(
        request,
        f"Ejecución en curso detenida ({updated} corrida marcada como cancelada). "
        "El botón ya puede volver a ejecutarse.",
    )
    date_from_raw = request.POST.get("from", "").strip()
    date_to_raw = request.POST.get("to", "").strip()
    back_url = reverse("analisis_crm:analysis_quality")
    try:
        date_from = date.fromisoformat(date_from_raw) if date_from_raw else None
        date_to = date.fromisoformat(date_to_raw) if date_to_raw else None
    except ValueError:
        date_from = date_to = None
    if date_from and date_to:
        back_url += f"?from={date_from.isoformat()}&to={date_to.isoformat()}"
    return redirect(back_url)


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
