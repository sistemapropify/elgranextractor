"""Vistas de observabilidad del aprendizaje operativo PIL."""

from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import SystemEvent, SystemTrace
from .permissions import has_permission


def _agentic_quality_metrics(events):
    """Agrega eventos N2/N3A sin depender de consultas JSON del motor SQL."""
    metrics = {
        'semantic_total': 0,
        'semantic_completed': 0,
        'semantic_failed': 0,
        'semantic_disagreements': 0,
        'advisory_total': 0,
        'advisory_applied': 0,
        'advisory_clarify': 0,
        'advisory_block': 0,
        'advisory_replan': 0,
    }
    for event in events:
        payload = event.payload or {}
        if event.event_type == 'evaluation.semantic.completed':
            metrics['semantic_total'] += 1
            if payload.get('status') == 'completed':
                metrics['semantic_completed'] += 1
            else:
                metrics['semantic_failed'] += 1
            if payload.get('disagrees_with_deterministic') is True:
                metrics['semantic_disagreements'] += 1
        elif event.event_type == 'evaluation.advisory.decided':
            metrics['advisory_total'] += 1
            if payload.get('authority_applied') is True:
                metrics['advisory_applied'] += 1
                key = f"advisory_{str(payload.get('action') or '').lower()}"
                if key in metrics:
                    metrics[key] += 1

    metrics['semantic_disagreement_pct'] = round(
        metrics['semantic_disagreements'] / metrics['semantic_completed'] * 100,
        1,
    ) if metrics['semantic_completed'] else 0
    metrics['advisory_application_pct'] = round(
        metrics['advisory_applied'] / metrics['advisory_total'] * 100,
        1,
    ) if metrics['advisory_total'] else 0
    return metrics


@has_permission(required_levels=[4, 5])
def learning_dashboard(request):
    hours = min(max(int(request.GET.get('hours', 24)), 1), 720)
    since = timezone.now() - timedelta(hours=hours)
    traces = SystemTrace.objects.filter(started_at__gte=since)

    total = traces.count()
    finalized = traces.exclude(status='started').count()
    completed = traces.filter(
        status__in=['completed', 'completed_degraded', 'completed_empty']
    ).count()
    degraded = traces.filter(status='completed_degraded').count()
    failed = traces.filter(status__in=['failed', 'timeout']).count()
    empty = traces.filter(status='completed_empty').count()
    needs_review = traces.filter(status='needs_review').count()
    ungrounded = traces.filter(grounded=False).count()
    internal_failures = SystemEvent.objects.filter(
        trace__in=traces, outcome='error'
    ).count()
    fallback_activations = SystemEvent.objects.filter(
        trace__in=traces, event_type='fallback.activated'
    ).count()
    quality_events = list(
        SystemEvent.objects.filter(
            trace__in=traces,
            event_type__in=[
                'evaluation.semantic.completed',
                'evaluation.advisory.decided',
            ],
        ).only('event_type', 'payload')
    )
    quality_metrics = _agentic_quality_metrics(quality_events)
    avg_latency = traces.aggregate(value=Avg('latency_ms'))['value'] or 0

    status_rows = list(
        traces.values('status').annotate(total=Count('id')).order_by('-total')
    )
    orchestration_rows = list(
        traces.exclude(orchestration_mode='')
        .values('orchestration_mode')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    recent = traces.select_related('conversation')[:20]

    context = {
        'hours': hours,
        'total': total,
        'finalized': finalized,
        'coverage_pct': round((finalized / total * 100), 1) if total else 0,
        'completed': completed,
        'failed': failed,
        'degraded': degraded,
        'empty': empty,
        'needs_review': needs_review,
        'ungrounded': ungrounded,
        'internal_failures': internal_failures,
        'fallback_activations': fallback_activations,
        'avg_latency': round(avg_latency),
        'status_rows': status_rows,
        'orchestration_rows': orchestration_rows,
        'recent_traces': recent,
        'mutation_enabled': False,
        **quality_metrics,
    }
    return render(request, 'intelligence/learning/dashboard.html', context)


@has_permission(required_levels=[4, 5])
def learning_traces(request):
    traces = SystemTrace.objects.select_related('conversation')
    status = request.GET.get('status', '').strip()
    mode = request.GET.get('mode', '').strip()
    search = request.GET.get('q', '').strip()

    if status:
        traces = traces.filter(status=status)
    if mode:
        traces = traces.filter(orchestration_mode=mode)
    if search:
        traces = traces.filter(
            Q(trace_id__icontains=search)
            | Q(query_redacted__icontains=search)
            | Q(request_kind__icontains=search)
        )

    page = Paginator(traces, 50).get_page(request.GET.get('page'))
    return render(request, 'intelligence/learning/traces_list.html', {
        'page_obj': page,
        'selected_status': status,
        'selected_mode': mode,
        'query': search,
        'status_choices': SystemTrace.STATUS_CHOICES,
    })


@has_permission(required_levels=[4, 5])
def learning_trace_detail(request, trace_id):
    trace = get_object_or_404(
        SystemTrace.objects.select_related('conversation'),
        trace_id=trace_id,
    )
    events = trace.events.all()
    return render(request, 'intelligence/learning/trace_detail.html', {
        'trace': trace,
        'events': events,
        'execution_events': events.filter(event_type='execution.agent.completed'),
        'requirement_events': events.filter(
            event_type__in=['requirement.satisfied', 'requirement.unsatisfied']
        ),
        'audit_event': events.filter(event_type='audit.completed').last(),
        'deterministic_event': events.filter(
            event_type='evaluation.completed'
        ).last(),
        'semantic_event': events.filter(
            event_type='evaluation.semantic.completed'
        ).last(),
        'advisory_event': events.filter(
            event_type='evaluation.advisory.decided'
        ).last(),
    })
