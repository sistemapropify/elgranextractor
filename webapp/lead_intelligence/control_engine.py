"""Operational obligations: deterministic timing, immutable evidence and audit."""
import hashlib
import json
import os
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import AnalysisRun, LeadDiagnosis, RecommendedAction, ActionOutcome, LeadControlPolicy, LeadControlState, LeadObligation, LeadControlEvent
from .remarketing_engine import as_time, timeline
from .conversation_analysis import normalize_text
from .control_calendar import calendar_for, add_minutes

KINDS = {'first_response': 'Dar primera respuesta humana', 'reply': 'Responder al cliente', 'assignment': 'Asignar responsable', 'visit': 'Coordinar visita solicitada', 'commitment': 'Cumplir compromiso', 'followup': 'Retomar seguimiento', 'postvisit': 'Registrar resultado de visita', 'data': 'Verificar datos del lead'}


def active_since():
    """Control starts at an explicit cutover; historic CRM debt is not an alert."""
    raw = os.environ.get('LEAD_CONTROL_ACTIVE_SINCE', '').strip()
    parsed = parse_datetime(raw)
    if parsed is None:
        return None
    return timezone.make_aware(parsed, timezone.get_current_timezone()) if timezone.is_naive(parsed) else parsed


def policy():
    return LeadControlPolicy.objects.get_or_create(pk=1, defaults={'weekdays': [0, 1, 2, 3, 4, 5]})[0]


def audit(state, kind, payload, obligation=None, actor='system'):
    return LeadControlEvent.objects.create(lead=state, kind=kind, payload=payload, obligation=obligation, actor=actor)


def create_obligation(state, kind, start, key, settings, evidence=None, fixed_due=None):
    event_key = hashlib.sha256(f'{state.source_lead_id}:{kind}:{key}'.encode()).hexdigest()
    existing = LeadObligation.objects.filter(event_key=event_key).first()
    if existing:
        return existing
    calendar = calendar_for(settings)
    if fixed_due:
        due = fixed_due
        supervisor, manager = add_minutes(due, 15, calendar), add_minutes(due, 60, calendar)
    elif kind in ('first_response', 'reply', 'visit'):
        prefix = 'first' if kind == 'first_response' else kind
        due = add_minutes(start, getattr(settings, f'{prefix}_minutes'), calendar)
        supervisor = add_minutes(start, getattr(settings, f'{prefix}_supervisor'), calendar)
        manager = add_minutes(start, getattr(settings, f'{prefix}_manager'), calendar)
    elif kind == 'assignment':
        due = supervisor = add_minutes(start, settings.assignment_minutes, calendar)
        manager = add_minutes(due, 10, calendar)
    else:
        due = add_minutes(start, 120, calendar)
        supervisor, manager = due, add_minutes(due, 60, calendar)
    with transaction.atomic():
        run = AnalysisRun.objects.create(run_type='incremental', status='completed', started_at=timezone.now(), completed_at=timezone.now(), leads_total=1, leads_analyzed=1, rules_version=f'control-{settings.revision}')
        diagnosis = LeadDiagnosis.objects.create(run=run, source_lead_id=state.source_lead_id, diagnosis_code=f'control_{kind}', severity='high', reason=KINDS[kind], evidence=evidence or {}, detected_at=start)
        action = RecommendedAction.objects.create(diagnosis=diagnosis, source_lead_id=state.source_lead_id, source_assigned_user_id=state.owner_id, action_type=kind, priority='high', title=KINDS[kind], reason=KINDS[kind], due_at=due)
        obligation = LeadObligation.objects.create(lead=state, action=action, event_key=event_key, kind=kind, started_at=start, original_due_at=due, supervisor_at=supervisor, manager_at=manager, calendar=calendar)
        audit(state, 'created', {'kind': kind, 'due_at': due.isoformat(), 'owner_id': state.owner_id}, obligation)
        return obligation


@transaction.atomic
def resolve(obligation, at, evidence, actor='system', dismissed=False):
    action = RecommendedAction.objects.select_for_update().get(pk=obligation.action_id)
    if action.status != 'pending':
        return False
    action.status = 'dismissed' if dismissed else 'completed'
    action.completed_at = at
    action.save(update_fields=['status', 'completed_at'])
    LeadDiagnosis.objects.filter(pk=action.diagnosis_id).update(is_active=False, resolved_at=at)
    obligation.resolved_evidence = evidence
    obligation.save(update_fields=['resolved_evidence'])
    obligation.notices.filter(status__in=['pending', 'unroutable', 'failed']).update(status='cancelled')
    audit(obligation.lead, 'dismissed' if dismissed else 'completed', evidence, obligation, actor)
    return True


def observe(snapshot, settings=None, now=None):
    settings, now = settings or policy(), now or timezone.now()
    lead_id = int(snapshot['lead_id'])
    if lead_id <= 0:
        raise ValueError('Lead inválido.')
    with transaction.atomic():
        state, _ = LeadControlState.objects.get_or_create(source_lead_id=lead_id)
        state = LeadControlState.objects.select_for_update().get(pk=state.pk)
        observed = as_time(snapshot.get('observed_at') or now)
        if observed > now or (state.observed_at and observed < state.observed_at):
            return state
        old_owner, old_crm = state.owner_id, state.crm_agent_id
        crm_owner = snapshot.get('agent_id')
        crm_owner = int(crm_owner) if crm_owner is not None else None
        if state.observed_at is None or old_crm != crm_owner:
            state.crm_agent_id = state.owner_id = crm_owner
            state.assignment_since = None if crm_owner else observed
        if not state.entered_at and snapshot.get('entered_at'):
            state.entered_at = as_time(snapshot['entered_at'])
            if state.entered_at > observed:
                raise ValueError('Fecha de ingreso futura.')
        if state.owner_id is None and state.assignment_since is None:
            state.assignment_since = state.entered_at or observed
        state.name = str(snapshot.get('nombre') or f'Lead {lead_id}')[:200]
        state.property_title = str(snapshot.get('propiedad') or '')[:300]
        state.status_name = str(snapshot.get('status_name') or '')[:100]
        state.observed_at, state.snapshot = observed, json.loads(json.dumps(snapshot, default=str))
        state.quality, state.last_error = 'valid', ''
        allowed = {normalize_text(v) for v in settings.active_statuses}
        closed = {normalize_text(v) for v in settings.closed_statuses}
        status_name = normalize_text(state.status_name)
        if status_name in closed:
            if state.active:
                state.closed_at = observed
                audit(state, 'crm_closed', {'at': observed.isoformat(), 'status': state.status_name})
            state.active = False
        elif status_name not in allowed:
            state.quality, state.last_error = 'unknown', 'Estado CRM sin clasificar en reglas de control.'
        else:
            state.active = True
        try:
            messages = timeline(snapshot)
            if any(m['timestamp'] > observed for m in messages):
                raise ValueError('Fechas futuras en el historial.')
        except (TypeError, ValueError, KeyError):
            messages = []
            state.quality, state.last_error = 'unknown', 'Conversación no verificable; revisar origen y fechas.'
        state.save()
        if old_owner != state.owner_id:
            change_owner(state, state.owner_id, 'Cambio observado en CRM', previous=old_owner)
        cutoff = active_since()
        if cutoff and (state.entered_at is None or state.entered_at < cutoff):
            # A backlog scan may observe an old CRM lead today.  That must not
            # turn historical debt into a current alert.  Close any obligations
            # created by earlier faulty sweeps and stop before creating more.
            for obligation in state.obligations.filter(action__status='pending').select_related('action'):
                resolve(obligation, now, {'type': 'before_control_cutover', 'lead_entered_at': state.entered_at.isoformat() if state.entered_at else None}, dismissed=True)
            return state
        if not state.active:
            for obligation in state.obligations.filter(action__status='pending').select_related('action'):
                resolve(obligation, now, {'type': 'crm_closed', 'status': state.status_name}, dismissed=True)
            return state
        if state.owner_id is None:
            create_obligation(state, 'assignment', state.assignment_since, state.assignment_since.isoformat(), settings)
        else:
            for item in state.obligations.filter(kind='assignment', action__status='pending'):
                resolve(item, observed, {'type': 'assignment', 'owner_id': state.owner_id})
        if state.quality != 'valid':
            if not state.obligations.filter(kind='data', action__status='pending').exists():
                create_obligation(state, 'data', observed, observed.isoformat(), settings, {'reason': state.last_error})
            return state
        for item in state.obligations.filter(kind='data', action__status='pending'):
            resolve(item, observed, {'type': 'source_recovered'})
        historical_human = any(m['sender'] == 'agent' for m in messages if state.closed_at and m['timestamp'] <= state.closed_at)
        if state.closed_at:
            messages = [m for m in messages if m['timestamp'] > state.closed_at]
        waiting = None
        responded_before = historical_human
        current_response = None
        last_human = None
        entry_key = hashlib.sha256(f'{state.source_lead_id}:first_response:entry:{state.entered_at.isoformat()}'.encode()).hexdigest() if state.entered_at else ''
        entry_items = state.obligations.filter(event_key=entry_key)
        if state.closed_at:
            entry_items = entry_items.filter(started_at__gt=state.closed_at)
        entry_item = entry_items.order_by('started_at').first()
        for message in messages:
            if message['sender'] == 'lead':
                if waiting is None:
                    waiting = message
                    kind = 'reply' if responded_before else 'first_response'
                    current_response = entry_item if entry_item and not responded_before else create_obligation(state, kind, message['timestamp'], message.get('id') or message['timestamp'].isoformat(), settings, {'message': message['text'][:500]})
            elif message['sender'] == 'agent':
                responded_before, last_human = True, message
                if entry_item:
                    resolve(entry_item, message['timestamp'], {'type': 'human_message', 'at': message['timestamp'].isoformat(), 'message_id': str(message.get('id') or '')})
                if waiting is not None:
                    resolve(current_response, message['timestamp'], {'type': 'human_message', 'message_id': str(message.get('id') or ''), 'at': message['timestamp'].isoformat()})
                    waiting = None
            # Bot neither closes the pending human turn nor resets its start.
        if not any(m['sender'] in ('lead', 'agent') for m in messages) and state.entered_at:
            if state.closed_at:
                create_obligation(state, 'followup', observed, f'reopen:{state.closed_at.isoformat()}', settings, {'type': 'crm_reopened'})
            else:
                create_obligation(state, 'first_response', state.entered_at, f'entry:{state.entered_at.isoformat()}', settings, {'type': 'crm_entry'})
        if waiting:
            for item in state.obligations.filter(kind='followup', action__status='pending'):
                resolve(item, waiting['timestamp'], {'type': 'customer_replied'}, dismissed=True)
        elif last_human:
            for item in state.obligations.filter(kind='followup', action__status='pending', started_at__lt=last_human['timestamp']):
                resolve(item, last_human['timestamp'], {'type': 'human_followup', 'at': last_human['timestamp'].isoformat()})
            due = add_minutes(last_human['timestamp']+timedelta(hours=settings.followup_hours), 0, calendar_for(settings))
            # Every active, contacted lead has a next step. Explicit commitments take precedence.
            if not state.obligations.filter(action__status='pending', kind__in=['commitment', 'visit', 'followup']).exists():
                create_obligation(state, 'followup', last_human['timestamp'], last_human.get('id') or last_human['timestamp'].isoformat(), settings, fixed_due=due)
        if snapshot.get('visit_intent_at'):
            at = as_time(snapshot['visit_intent_at'])
            if at <= observed and (not state.closed_at or at > state.closed_at):
                item = create_obligation(state, 'visit', at, at.isoformat(), settings, snapshot.get('visit_evidence') or {})
                if snapshot.get('visit_registered_at'):
                    registered = as_time(snapshot['visit_registered_at'])
                    if at <= registered <= now:
                        resolve(item, registered, {'type': 'visit_registered', 'at': registered.isoformat()})
        if snapshot.get('visit_completed_at'):
            at = as_time(snapshot['visit_completed_at'])
            if at <= observed and (not state.closed_at or at > state.closed_at):
                create_obligation(state, 'postvisit', at, at.isoformat(), settings)
        return state


@transaction.atomic
def change_owner(state, owner_id, reason, actor='system', previous='current'):
    previous = state.owner_id if previous == 'current' else previous
    state.owner_id = owner_id
    state.save(update_fields=['owner_id'])
    actions = RecommendedAction.objects.filter(control__lead=state, status='pending')
    actions.update(source_assigned_user_id=owner_id)
    from .models import LeadControlNotice
    LeadControlNotice.objects.filter(obligation__lead=state, level='agent', status__in=['pending', 'failed']).update(status='cancelled')
    audit(state, 'owner_changed', {'from': previous, 'to': owner_id, 'reason': reason, 'scope': 'control_only'}, actor=actor)


def intervene(obligation_id, operation, actor, source_user_id, data, manager=False, now=None, access=None):
    now = now or timezone.now()
    with transaction.atomic():
        lead_pk = LeadObligation.objects.values_list('lead_id', flat=True).get(pk=obligation_id)
        LeadControlState.objects.select_for_update().get(pk=lead_pk)
        if access is not None and not access.states().filter(pk=lead_pk).exists():
            from django.http import Http404
            raise Http404('Lead fuera de tu cartera.')
        item = LeadObligation.objects.select_for_update().get(pk=obligation_id)
        if item.action.status != 'pending':
            raise ValueError('El pendiente ya está cerrado.')
        if operation == 'ack':
            if item.acknowledged_at is None:
                item.acknowledged_at = now
                item.save(update_fields=['acknowledged_at'])
                audit(item.lead, 'acknowledged', {}, item, actor)
            return item
        notes = str(data.get('notes') or '').strip()
        if not notes or len(notes) > 3000:
            raise ValueError('Registra el motivo o resultado.')
        if operation == 'rescue':
            audit(item.lead, 'rescue_requested', {'notes': notes}, item, actor)
            return item
        if operation == 'dismiss':
            if not manager:
                raise ValueError('Solo supervisión puede registrar una excepción.')
            resolve(item, now, {'type': 'exception', 'notes': notes}, actor, dismissed=True)
            return item
        if operation == 'reschedule':
            if item.kind not in ('commitment', 'followup', 'postvisit'):
                raise ValueError('No se puede ampliar el plazo de respuesta ni de asignación.')
            due = as_time(data.get('next_contact_at'))
            if due <= now:
                raise ValueError('La próxima fecha debe ser futura.')
            original = item.action.due_at
            item.action.due_at = due
            item.action.save(update_fields=['due_at'])
            item.supervisor_at = add_minutes(due, 15, item.calendar)
            item.manager_at = add_minutes(due, 60, item.calendar)
            item.save(update_fields=['supervisor_at', 'manager_at'])
            audit(item.lead, 'rescheduled', {'from': original.isoformat(), 'to': due.isoformat(), 'notes': notes}, item, actor)
            return item
        if operation != 'complete':
            raise ValueError('Operación inválida.')
        reference = str(data.get('evidence_reference') or '').strip()
        evidence_type = data.get('evidence_type')
        if evidence_type not in ('call', 'message', 'visit', 'document') or not reference or len(reference) > 500:
            raise ValueError('Registra el tipo y la referencia de evidencia.')
        if item.kind == 'assignment':
            raise ValueError('Asigna un responsable para resolver este pendiente.')
        next_at = as_time(data.get('next_contact_at'))
        if next_at <= now:
            raise ValueError('Registra una próxima acción futura.')
        evidence = {'type': evidence_type, 'reference': reference, 'notes': notes, 'source': 'user_recorded'}
        resolve(item, now, evidence, actor)
        ActionOutcome.objects.create(action=item.action, outcome_code=evidence_type, notes=notes, next_contact_at=next_at, source_user_id=source_user_id or 0)
        create_obligation(item.lead, 'commitment', now, f'after:{item.pk}', policy(), evidence={'source': 'user_recorded', 'actor': actor}, fixed_due=next_at)
        return item
