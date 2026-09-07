import hmac
import json
import uuid
from datetime import timedelta
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Case, When, Value, IntegerField
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .models import LeadControlState, LeadObligation, LeadControlMember, LeadControlNotice, LeadControlDigest
from .control_access import control_required
from .control_engine import observe, policy, intervene, create_obligation, change_owner, resolve, KINDS
from .control_forms import PolicyForm, MemberForm
from .control_metrics import metrics
from .control_notifications import enabled
from .control_digest import scope_key
from .control_source import source_snapshot
from .remarketing_engine import LIMA
from .remarketing_gateway import config
from .control_runtime import runtime_status


def local_datetime(value):
    parsed = parse_datetime(value or '')
    if not parsed:
        raise ValueError('Fecha inválida.')
    return timezone.make_aware(parsed, LIMA) if timezone.is_naive(parsed) else parsed


@control_required
@require_POST
def sync_lead(request):
    """A manager can inspect one real lead without enabling any transport."""
    if not request.control_access.configures:
        return HttpResponseForbidden()
    settings = policy()
    if not settings.active_statuses or not settings.closed_statuses:
        messages.error(request, 'Primero clasifica los estados activos y cerrados en Reglas.')
        return redirect('analisis_crm:control_rules')
    try:
        lead_id = int(request.POST.get('lead_id', ''))
        if not 0 < lead_id < 2**63:
            raise ValueError()
    except (ValueError, TypeError):
        return HttpResponse('Indica un ID de lead válido.', status=400)
    try:
        snapshot = source_snapshot(lead_id)
        if len(json.dumps(snapshot, default=str)) > 2_000_000:
            return HttpResponse('Este historial requiere sincronización por el proceso de cartera.', status=413)
        state = observe(snapshot, settings)
    except Exception:
        messages.error(request, 'No se pudo consultar ese lead. Comprueba el ID y la conexión con el CRM.')
        return redirect('analisis_crm:control_board')
    from .control_engine import audit
    audit(state, 'manual_sync', {}, actor=request.control_access.actor)
    return redirect('analisis_crm:control_lead', lead_id=lead_id)


@control_required
@require_GET
def board(request):
    access, now = request.control_access, timezone.now()
    states = access.states()
    settings = policy()
    stale_before = now-timedelta(minutes=settings.stale_minutes)
    fresh = Q(lead__quality='valid', lead__observed_at__gte=stale_before)
    all_items = LeadObligation.objects.filter(lead__in=states).select_related('lead', 'action')
    items = all_items.filter(action__status='pending')
    category = request.GET.get('category', '')
    if category in KINDS:
        items = items.filter(kind=category)
    if request.GET.get('overdue') == '1':
        items = items.filter(fresh, action__due_at__lt=now)
    if request.GET.get('escalated') == '1':
        items = items.filter(fresh, manager_at__lte=now)
    items = items.annotate(control_rank=Case(When(fresh & Q(manager_at__lte=now), then=Value(0)), When(kind__in=['visit', 'commitment'], action__due_at__lte=now+timedelta(minutes=30), then=Value(1)), When(kind__in=['first_response', 'reply'], then=Value(2)), When(action__due_at__lt=now, then=Value(3)), default=Value(4), output_field=IntegerField()))
    page = Paginator(items.order_by('control_rank', 'action__due_at'), 50).get_page(request.GET.get('page'))
    stale = states.filter(Q(observed_at__lt=stale_before) | Q(observed_at__isnull=True) | ~Q(quality='valid')).count()
    scope_notices = LeadControlNotice.objects.filter(obligation__lead__in=states)
    if not access.manages:
        scope_notices = scope_notices.filter(recipient=access.member)
    stats = metrics(all_items.filter(Q(started_at__gte=now-timedelta(days=30)) | Q(action__status='pending')), now, settings.stale_minutes)
    active_states = states.filter(active=True)
    with_action = active_states.filter(obligations__action__status='pending').distinct().count()
    digest = None
    if access.member and access.manages:
        current_scope = scope_key(access.member)
        digest = next((record for record in LeadControlDigest.objects.filter(recipient=access.member)[:30] if record.payload.get('scope_key') == current_scope), None)
    owner_names = dict(LeadControlMember.objects.filter(active=True, source_user_id__isnull=False).values_list('source_user_id', 'name'))
    for item in page:
        if item.lead.crm_agent_id == item.action.source_assigned_user_id and item.lead.snapshot.get('agente'):
            owner_names.setdefault(item.action.source_assigned_user_id, item.lead.snapshot['agente'])
        item.owner_name = owner_names.get(item.action.source_assigned_user_id, item.action.source_assigned_user_id or 'Sin asignar')
        item.source_fresh = item.lead.quality == 'valid' and item.lead.observed_at and item.lead.observed_at >= stale_before
    for agent in stats['agents']:
        agent['name'] = owner_names.get(agent['agent_id'], agent['agent_id'] or 'Sin asignar')
    return render(request, 'lead_intelligence/control_board.html', {'page': page, 'states': Paginator(states.order_by('-updated_at'), 50).get_page(request.GET.get('leads_page')), 'stats': stats, 'stale': stale, 'with_action': with_action, 'active_count': active_states.count(), 'access': access, 'kinds': KINDS, 'category': category, 'now': now, 'notices': scope_notices.select_related('obligation__lead', 'recipient').order_by('-created_at')[:100], 'transport': {'email': enabled('LEAD_CONTROL_EMAIL_ENABLED'), 'push': enabled('LEAD_CONTROL_PUSH_ENABLED')}, 'digest': digest, 'runtime': runtime_status(), 'policy_ready': bool(settings.active_statuses and settings.closed_statuses)})


@control_required
@require_GET
def lead_detail(request, lead_id):
    state = get_object_or_404(request.control_access.states(), source_lead_id=lead_id)
    raw = state.snapshot.get('messages') or []
    try:
        conversation = json.loads(raw) if isinstance(raw, str) else raw
    except (ValueError, TypeError):
        conversation = []
    if not isinstance(conversation, list):
        conversation = []
    owners = LeadControlMember.objects.filter(active=True, source_user_id__isnull=False)
    if not request.control_access.configures:
        owners = owners.filter(supervisor=request.control_access.member)
    return render(request, 'lead_intelligence/control_lead.html', {'lead': state, 'obligations': state.obligations.select_related('action').order_by('-started_at')[:100], 'events': state.events.all()[:150], 'conversation': conversation, 'owners': owners, 'access': request.control_access, 'now': timezone.now()})


@control_required
@require_POST
def obligation_action(request, obligation_id):
    item = get_object_or_404(LeadObligation.objects.filter(lead__in=request.control_access.states()), pk=obligation_id)
    data = request.POST.dict()
    try:
        if data.get('next_contact_at'):
            data['next_contact_at'] = local_datetime(data['next_contact_at'])
        intervene(item.pk, data.get('operation'), request.control_access.actor, request.control_access.member.source_user_id if request.control_access.member else None, data, manager=request.control_access.manages, access=request.control_access)
    except (ValueError, TypeError) as exc:
        return HttpResponse(str(exc), status=400)
    return redirect('analisis_crm:control_lead', lead_id=item.lead.source_lead_id)


@control_required
@require_POST
def add_commitment(request, lead_id):
    with transaction.atomic():
        state = get_object_or_404(request.control_access.states().select_for_update(), source_lead_id=lead_id)
        if not state.active:
            return HttpResponse('El lead está cerrado.', status=409)
        try:
            due = local_datetime(request.POST.get('due_at'))
            note = str(request.POST.get('notes') or '').strip()
            if due <= timezone.now() or not note:
                raise ValueError('Registra una fecha futura y el compromiso acordado.')
            kind = request.POST.get('kind', 'commitment')
            if kind not in ('commitment', 'postvisit', 'followup'):
                raise ValueError('Tipo inválido.')
            create_obligation(state, kind, timezone.now(), uuid.uuid4().hex, policy(), {'source': 'user_recorded', 'notes': note, 'actor': request.control_access.actor}, fixed_due=due)
        except ValueError as exc:
            return HttpResponse(str(exc), status=400)
    return redirect('analisis_crm:control_lead', lead_id=lead_id)


@control_required
@require_POST
def assign(request, lead_id):
    if not request.control_access.manages:
        return HttpResponseForbidden()
    targets = LeadControlMember.objects.filter(active=True, source_user_id__isnull=False)
    if not request.control_access.configures:
        targets = targets.filter(supervisor=request.control_access.member)
    try:
        target_id = int(request.POST.get('member_id', ''))
    except (ValueError, TypeError):
        return HttpResponse('Selecciona un responsable válido.', status=400)
    target = get_object_or_404(targets, pk=target_id)
    note = str(request.POST.get('notes') or '').strip()
    if not note:
        return HttpResponse('Indica el motivo de la delegación.', status=400)
    with transaction.atomic():
        state = get_object_or_404(request.control_access.states().select_for_update(), source_lead_id=lead_id)
        change_owner(state, target.source_user_id, note, request.control_access.actor)
        for item in state.obligations.filter(kind='assignment', action__status='pending'):
            resolve(item, timezone.now(), {'type': 'control_assignment', 'owner_id': target.source_user_id}, request.control_access.actor)
    return redirect('analisis_crm:control_board')


@control_required
@require_http_methods(['GET', 'POST'])
def rules(request):
    if not request.control_access.configures:
        return HttpResponseForbidden()
    instance = policy()
    form = PolicyForm(request.POST or None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        saved = form.save(commit=False)
        saved.revision += 1
        saved.save()
        messages.success(request, 'Reglas guardadas. Los pendientes existentes conservan su plazo original.')
        return redirect('analisis_crm:control_rules')
    return render(request, 'lead_intelligence/control_config.html', {'form': form, 'title': 'Reglas de atención', 'access': request.control_access})


@control_required
@require_http_methods(['GET', 'POST'])
def directory(request, member_id=None):
    if not request.control_access.configures:
        return HttpResponseForbidden()
    member = get_object_or_404(LeadControlMember, pk=member_id) if member_id else None
    form = MemberForm(request.POST or None, instance=member)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('analisis_crm:control_directory')
    return render(request, 'lead_intelligence/control_config.html', {'form': form, 'title': 'Directorio y responsables', 'members': LeadControlMember.objects.select_related('supervisor'), 'access': request.control_access})


@csrf_exempt
@require_POST
def ingest(request):
    token = config('LEAD_CONTROL_INGEST_TOKEN')
    if not token or not hmac.compare_digest(request.headers.get('Authorization', '').encode(), f'Bearer {token}'.encode()):
        return HttpResponseForbidden()
    if len(request.body) > 2_000_000:
        return JsonResponse({'error': 'Snapshot demasiado grande.'}, status=413)
    try:
        payload = json.loads(request.body)
        if not isinstance(payload, dict) or not payload.get('observed_at'):
            raise ValueError('Falta observed_at.')
        state = observe(payload)
        return JsonResponse({'ok': True, 'lead_id': state.source_lead_id, 'quality': state.quality})
    except (ValueError, TypeError, KeyError):
        return JsonResponse({'error': 'Snapshot inválido.'}, status=400)
