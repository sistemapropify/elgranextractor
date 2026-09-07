from dataclasses import dataclass
from functools import wraps
from django.http import HttpResponseForbidden
from django.db.models import Q
from .models import LeadControlMember, LeadControlState


@dataclass
class ControlAccess:
    member: object = None
    admin: bool = False
    actor: str = ''

    @property
    def manages(self):
        return self.admin or bool(self.member and self.member.role in ('manager', 'supervisor'))

    @property
    def configures(self):
        return self.admin or bool(self.member and self.member.role == 'manager')

    def states(self):
        queryset = LeadControlState.objects.all()
        if self.admin or (self.member and self.member.role == 'manager'):
            return queryset
        if not self.member:
            return queryset.none()
        ids = [self.member.source_user_id] if self.member.source_user_id is not None else []
        if self.member.role == 'supervisor':
            ids += list(self.member.team.filter(active=True, source_user_id__isnull=False).values_list('source_user_id', flat=True))
        return queryset.filter(owner_id__in=ids)


def access_for(request):
    user = getattr(request, 'user', None)
    if getattr(user, 'is_authenticated', False):
        if getattr(user, 'is_superuser', False):
            return ControlAccess(admin=True, actor=f'django:{user.pk}')
        member = LeadControlMember.objects.filter(identity_type='django', identity_id=str(user.pk), active=True).first()
        if member:
            return ControlAccess(member=member, actor=f'django:{user.pk}')
    current = getattr(request, 'current_user', None)
    if current and getattr(current, 'is_active', False):
        # Never use the session simulator to grant operational write access.
        member = LeadControlMember.objects.filter(identity_type='intelligence', identity_id=str(current.pk), active=True).first()
        profile = getattr(current, 'intelligence_profile', None)
        admin = bool(profile and profile.level >= 3 and ('gerencia' in (profile.allowed_domains or []) or profile.level >= 5))
        if member or admin:
            return ControlAccess(member=member, admin=admin, actor=f'intelligence:{current.pk}')
    return None


def control_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        access = access_for(request)
        if not access:
            return HttpResponseForbidden('No tienes acceso al control de leads. Gerencia debe vincular tu identidad en el directorio.')
        request.control_access = access
        return view(request, *args, **kwargs)
    return wrapped
