"""Propitools-compatible views over the same operational obligations as the web."""
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from datetime import timedelta
from zoneinfo import ZoneInfo
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .propify_auth import PropifyBearerAuthentication
from .models import MobileNotificationDevice
from lead_intelligence.models import LeadControlMember, LeadObligation, LeadControlNotice
from lead_intelligence.control_access import ControlAccess
from lead_intelligence.control_engine import intervene, policy, KINDS, active_since


def access_for_mobile(principal):
    mobile = principal.mobile_user
    identity = mobile.propify_user_id
    members = list(LeadControlMember.objects.filter(active=True).filter(Q(identity_type='propify', identity_id=identity) | Q(mobile_identity_id=identity))) if identity else []
    member = members[0] if len(members) == 1 else None
    # Existing explicit supervisor grant remains effective; never infer from username.
    return ControlAccess(member=member, admin=mobile.can_view_crm_alerts, actor=f'propify:{identity}')


def serialize(item, owners=None, stale_before=None):
    state, action = item.lead, item.action
    owners = owners if owners is not None else dict(LeadControlMember.objects.filter(active=True, source_user_id__isnull=False).values_list('source_user_id', 'name'))
    now = timezone.now()
    stale_before = stale_before or now-timedelta(minutes=policy().stale_minutes)
    fresh = bool(state.quality == 'valid' and state.observed_at and state.observed_at >= stale_before)
    fallback = (state.snapshot or {}).get('agent_name') if state.owner_id == action.source_assigned_user_id else None
    return {'id': item.pk, 'lead_id': state.source_lead_id, 'agent_name': owners.get(action.source_assigned_user_id, fallback or str(action.source_assigned_user_id or 'Sin asignar')), 'contact_name': state.name, 'phone': '', 'property_code': '', 'property_title': state.property_title, 'evidence': [{'text': action.title}], 'status': 'closed' if action.status != 'pending' else ('follow_up' if item.acknowledged_at else 'pending'), 'detected_at': item.started_at.isoformat(), 'responded_at': action.completed_at.isoformat() if action.completed_at else None, 'response_seconds': int((action.completed_at-item.started_at).total_seconds()) if action.completed_at else None, 'kind': item.kind, 'due_at': action.due_at.isoformat(), 'overdue': fresh and action.status == 'pending' and action.due_at < now, 'escalated': fresh and action.status == 'pending' and item.manager_at <= now, 'quality': state.quality, 'fresh': fresh, 'observed_at': state.observed_at.isoformat() if state.observed_at else None}


@api_view(['POST', 'DELETE'])
@authentication_classes([PropifyBearerAuthentication])
@permission_classes([IsAuthenticated])
def register_device(request):
    value = str(request.data.get('registration_id') or '').strip()
    target = request.data.get('target_type', 'fid')
    if not 10 <= len(value) <= 512 or any(c.isspace() for c in value) or target not in ('fid', 'token'):
        return Response({'ok': False, 'error': 'Registro de dispositivo inválido.'}, status=400)
    if request.method == 'DELETE':
        MobileNotificationDevice.objects.filter(registration_id=value, user=request.user.mobile_user).update(active=False)
        return Response({'ok': True})
    MobileNotificationDevice.objects.update_or_create(registration_id=value, defaults={'user': request.user.mobile_user, 'target_type': target, 'device_name': str(request.data.get('device_name') or '')[:200], 'active': True})
    return Response({'ok': True})


@api_view(['GET'])
@authentication_classes([PropifyBearerAuthentication])
@permission_classes([IsAuthenticated])
def alerts(request):
    access = access_for_mobile(request.user)
    if not access.member and not access.admin:
        return Response({'ok': False, 'error': 'Sin acceso al control de leads.'}, status=403)
    items = LeadObligation.objects.filter(lead__in=access.states()).select_related('lead', 'action')
    cutoff = active_since()
    if cutoff:
        items = items.filter(started_at__gte=cutoff)
    status = request.query_params.get('status', 'pending')
    category = request.query_params.get('kind', '')
    try:
        offset = int(request.query_params.get('offset', 0))
        limit = int(request.query_params.get('limit', 50))
        if offset < 0 or not 1 <= limit <= 200 or status not in ('pending', 'follow_up', 'closed') or (category and category not in KINDS):
            raise ValueError()
    except (ValueError, TypeError):
        return Response({'ok': False, 'error': 'Filtro o página inválidos.'}, status=400)
    if status == 'closed':
        items = items.exclude(action__status='pending')
    else:
        items = items.filter(action__status='pending', acknowledged_at__isnull=status != 'follow_up')
    if category:
        items = items.filter(kind=category)
    stale_before = timezone.now()-timedelta(minutes=policy().stale_minutes)
    fresh = Q(lead__quality='valid', lead__observed_at__gte=stale_before)
    if request.query_params.get('urgent') == '1':
        items = items.filter(fresh, action__status='pending', action__due_at__lt=timezone.now())
    if request.query_params.get('escalated') == '1':
        items = items.filter(fresh, action__status='pending', manager_at__lte=timezone.now())
    owners = dict(LeadControlMember.objects.filter(active=True, source_user_id__isnull=False).values_list('source_user_id', 'name'))
    total = items.count()
    return Response({'ok': True, 'total': total, 'next_offset': offset+limit if offset+limit < total else None, 'can_manage': access.manages, 'results': [serialize(item, owners, stale_before) for item in items.order_by('action__due_at', 'pk')[offset:offset+limit]]})


@api_view(['GET', 'POST'])
@authentication_classes([PropifyBearerAuthentication])
@permission_classes([IsAuthenticated])
def alert_detail(request, pk):
    access = access_for_mobile(request.user)
    item = get_object_or_404(LeadObligation.objects.filter(lead__in=access.states()).select_related('lead', 'action'), pk=pk)
    if request.method == 'POST':
        try:
            data = dict(request.data)
            if data.get('operation') in ('complete', 'reschedule'):
                due = parse_datetime(str(data.get('next_contact_at') or ''))
                if due is None:
                    raise ValueError('Indica fecha y hora de la próxima acción.')
                data['next_contact_at'] = timezone.make_aware(due, ZoneInfo('America/Lima')) if timezone.is_naive(due) else due
            intervene(item.pk, data.get('operation'), access.actor, access.member.source_user_id if access.member else None, data, manager=access.manages, access=access)
        except (ValueError, TypeError) as exc:
            return Response({'ok': False, 'error': str(exc)}, status=400)
        item.refresh_from_db()
    if access.member:
        LeadControlNotice.objects.filter(obligation=item, recipient=access.member, read_at__isnull=True).update(read_at=timezone.now())
    import json
    raw = item.lead.snapshot.get('messages') or []
    try:
        conversation = json.loads(raw) if isinstance(raw, str) else raw
    except (ValueError, TypeError):
        conversation = []
    conversation = [{'sender': m.get('sender', ''), 'timestamp': m.get('timestamp', ''), 'text': m.get('text') or m.get('content') or ''} for m in conversation if isinstance(m, dict)] if isinstance(conversation, list) else []
    return Response({'ok': True, 'can_manage': access.manages, 'alert': serialize(item), 'conversation': conversation})
