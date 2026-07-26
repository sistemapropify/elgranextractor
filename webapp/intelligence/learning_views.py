"""Vistas de observabilidad del aprendizaje operativo PIL."""

from datetime import timedelta
import math

from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q, Sum
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import AIConsumptionLog, SystemEvent, SystemTrace
from .permissions import has_permission


def _latency_series(rows, hours, now=None):
    """Agrupa latencias en intervalos continuos sin depender del motor SQL."""
    rows = list(rows)
    now_local = timezone.localtime(now or timezone.now())
    bucket_hours = 1 if hours <= 48 else (6 if hours <= 168 else 24)

    if bucket_hours == 24:
        end = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        end = now_local.replace(
            hour=(now_local.hour // bucket_hours) * bucket_hours,
            minute=0,
            second=0,
            microsecond=0,
        )
    start_target = now_local - timedelta(hours=hours)
    if bucket_hours == 24:
        start = start_target.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        start = start_target.replace(
            hour=(start_target.hour // bucket_hours) * bucket_hours,
            minute=0,
            second=0,
            microsecond=0,
        )

    buckets = {}
    cursor = start
    while cursor <= end:
        buckets[cursor] = []
        cursor += timedelta(hours=bucket_hours)

    for started_at, latency_ms in rows:
        if started_at is None or latency_ms is None:
            continue
        local_started = timezone.localtime(started_at)
        if bucket_hours == 24:
            key = local_started.replace(
                hour=0, minute=0, second=0, microsecond=0,
            )
        else:
            key = local_started.replace(
                hour=(local_started.hour // bucket_hours) * bucket_hours,
                minute=0,
                second=0,
                microsecond=0,
            )
        if key in buckets:
            buckets[key].append(float(latency_ms))

    labels = []
    average = []
    p95 = []
    counts = []
    bucket_timestamps = []
    for bucket, values in buckets.items():
        bucket_timestamps.append(bucket.isoformat())
        labels.append(
            bucket.strftime('%d/%m')
            if bucket_hours == 24
            else bucket.strftime('%d/%m %H:00')
        )
        counts.append(len(values))
        if not values:
            average.append(None)
            p95.append(None)
            continue
        ordered = sorted(values)
        average.append(round(sum(ordered) / len(ordered)))
        p95_index = max(0, math.ceil(len(ordered) * 0.95) - 1)
        p95.append(round(ordered[p95_index]))

    queries = []
    for started_at, latency_ms in sorted(
        rows,
        key=lambda row: row[0] or timezone.now(),
    ):
        if started_at is None or latency_ms is None:
            continue
        local_started = timezone.localtime(started_at)
        queries.append({
            'timestamp': local_started.isoformat(),
            'label': local_started.strftime('%d/%m %H:%M:%S'),
            'latency': round(float(latency_ms)),
        })

    return {
        'labels': labels,
        'bucket_timestamps': bucket_timestamps,
        'average': average,
        'p95': p95,
        'counts': counts,
        'queries': queries,
        'bucket_hours': bucket_hours,
    }


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
    latency_series = _latency_series(
        traces.values_list('started_at', 'latency_ms'),
        hours,
    )
    consumption_logs = AIConsumptionLog.objects.filter(created_at__gte=since)
    consumption_totals = consumption_logs.aggregate(
        calls=Count('id'),
        prompt_tokens=Sum('prompt_tokens'),
        completion_tokens=Sum('completion_tokens'),
        total_tokens=Sum('total_tokens'),
        estimated_cost_usd=Sum('estimated_cost_usd'),
    )
    tokenized_calls = consumption_logs.filter(total_tokens__gt=0).count()
    ai_usage = {
        'calls': consumption_totals['calls'] or 0,
        'prompt_tokens': consumption_totals['prompt_tokens'] or 0,
        'completion_tokens': consumption_totals['completion_tokens'] or 0,
        'total_tokens': consumption_totals['total_tokens'] or 0,
        'estimated_cost_usd': float(
            consumption_totals['estimated_cost_usd'] or 0
        ),
        'tokenized_calls': tokenized_calls,
        'coverage_pct': round(
            tokenized_calls / (consumption_totals['calls'] or 1) * 100,
            1,
        ),
    }
    ai_usage_by_caller = list(
        consumption_logs
        .order_by()
        .values('caller_app')
        .annotate(
            calls=Count('id'),
            tokens=Sum('total_tokens'),
            cost=Sum('estimated_cost_usd'),
        )
        .order_by('-tokens', '-calls')[:8]
    )
    ai_usage_by_model = list(
        consumption_logs
        .order_by()
        .values('model_name')
        .annotate(
            calls=Count('id'),
            tokens=Sum('total_tokens'),
            cost=Sum('estimated_cost_usd'),
        )
        .order_by('-tokens', '-calls')[:8]
    )

    status_rows = list(
        traces.values('status').annotate(total=Count('id')).order_by('-total')
    )
    orchestration_rows = list(
        traces.exclude(orchestration_mode='')
        .values('orchestration_mode')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    recent = list(traces.select_related('conversation')[:20])
    recent_trace_ids = [trace.trace_id for trace in recent]
    usage_by_trace = {
        row['trace_id']: row
        for row in (
            AIConsumptionLog.objects
            .filter(trace_id__in=recent_trace_ids)
            .order_by()
            .values('trace_id')
            .annotate(
                calls=Count('id'),
                tokenized_calls=Count(
                    'id',
                    filter=Q(total_tokens__gt=0),
                ),
                tokens=Sum('total_tokens'),
                cost=Sum('estimated_cost_usd'),
            )
        )
    }
    dashboard_now = timezone.now()
    for trace in recent:
        trace.elapsed_latency_ms = None
        trace.has_elapsed_latency = False
        trace.is_stale_started = False
        if trace.status == 'started' and trace.started_at:
            trace.has_elapsed_latency = True
            trace.elapsed_latency_ms = max(
                0,
                round((dashboard_now - trace.started_at).total_seconds() * 1000),
            )
            trace.is_stale_started = trace.elapsed_latency_ms >= 120000
        trace_usage = usage_by_trace.get(trace.trace_id) or {}
        trace.ai_calls = trace_usage.get('calls', 0)
        trace.ai_tokenized_calls = trace_usage.get('tokenized_calls', 0)
        trace.ai_tokens = trace_usage.get('tokens', 0) or 0
        trace.ai_cost_usd = float(trace_usage.get('cost', 0) or 0)
        trace.has_ai_usage = trace.ai_tokenized_calls > 0

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
        'latency_series': latency_series,
        'ai_usage': ai_usage,
        'ai_usage_by_caller': ai_usage_by_caller,
        'ai_usage_by_model': ai_usage_by_model,
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
