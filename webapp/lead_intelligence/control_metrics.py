from collections import defaultdict
from datetime import timedelta
from django.utils import timezone
from .control_calendar import business_seconds


def metrics(obligations, now=None, stale_minutes=15):
    now = now or timezone.now()
    result = dict(total=0, open=0, overdue=0, escalated=0, acknowledged=0, eligible=0, on_time=0, unknown=0, waiting_first=0, unassigned=0)
    agents = defaultdict(lambda: {'due': 0, 'on_time': 0, 'open': 0, 'overdue': 0})
    response_times = []
    for item in obligations:
        action = item.action
        result['total'] += 1
        pending = action.status == 'pending'
        fresh = bool(item.lead.observed_at and item.lead.observed_at >= now-timedelta(minutes=stale_minutes))
        verifiable = item.lead.quality == 'valid' and (not pending or fresh)
        result['unknown'] += not verifiable
        overdue = pending and verifiable and action.due_at < now
        result['open'] += pending
        result['overdue'] += overdue
        result['escalated'] += pending and verifiable and now >= item.manager_at
        result['acknowledged'] += pending and bool(item.acknowledged_at)
        result['waiting_first'] += pending and item.kind == 'first_response'
        result['unassigned'] += pending and item.kind == 'assignment'
        group = agents[action.source_assigned_user_id]
        group['open'] += pending
        group['overdue'] += overdue
        # Include unanswered obligations whose ORIGINAL deadline has elapsed.
        # Exceptions are reported separately; reprogramming never erases lateness.
        if item.kind in ('first_response', 'reply') and action.status == 'completed' and action.completed_at and item.resolved_evidence.get('type') == 'human_message':
            response_times.append(business_seconds(item.started_at, action.completed_at, item.calendar)/60)
        if item.original_due_at <= now and action.status != 'dismissed' and verifiable:
            result['eligible'] += 1
            group['due'] += 1
            on_time = action.status == 'completed' and action.completed_at and action.completed_at <= item.original_due_at
            result['on_time'] += bool(on_time)
            group['on_time'] += bool(on_time)
    result['compliance'] = round(result['on_time']/result['eligible']*100, 1) if result['eligible'] else None
    response_times.sort()
    def percentile(fraction):
        if not response_times:
            return None
        position = (len(response_times)-1)*fraction
        lower, upper = int(position), min(int(position)+1, len(response_times)-1)
        return round(response_times[lower]+(response_times[upper]-response_times[lower])*(position-lower), 1)
    result.update(response_count=len(response_times), p50_minutes=percentile(.5), p90_minutes=percentile(.9))
    result['agents'] = [{'agent_id': key, **value, 'compliance': round(100*value['on_time']/value['due'], 1) if value['due'] else None} for key, value in agents.items()]
    return result
