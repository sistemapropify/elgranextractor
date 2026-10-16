"""Server-side ACM identities, role policies, and role perspectives."""
import hashlib
import json
import secrets
from dataclasses import dataclass
from functools import wraps
from urllib.parse import urlencode

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connections
from django.http import JsonResponse
from django.shortcuts import redirect

from .access_models import ACMRolePolicy

PREVIEW_ROLES = {'administrador', 'desarrollador', 'gerente general'}
SESSION_PROFILE = 'acm_propify_profile'
SESSION_TOKEN = 'acm_propify_token'
SESSION_PREVIEW = 'acm_role_perspective'

# Defaults define the basic ACM; explicit role policies can restrict capabilities.
CATEGORIES = (
    ('Mapa y capas', (
        ('pdm_query', 'Consultar zonificación PDM', True),
        ('pdm_polygons', 'Mostrar polígonos PDM', False),
        ('pdm_card', 'Mostrar tarjeta PDM', False),
        ('street_view', 'Usar Street View', False),
        ('cadastral_info', 'Catastro maestro: lotes del distrito e información catastral', True),
    )),
    ('Propiedades comparables', (
        ('property_data', 'Consultar datos de la propiedad', True),
        ('property_pins', 'Mostrar pines de propiedades', True),
        ('photos', 'Mostrar fotografías', True),
        ('unreviewed_photos', 'Mostrar fotos sin revisión de marcas de origen', False),
    )),
    ('Origen de las publicaciones', (
        ('portal_names', 'Mostrar nombre del portal', False),
        ('portal_pins', 'Mostrar logos de portales en los pines', False),
        ('publication', 'Ver publicación', False),
        ('portal_link', 'Abrir el portal original', False),
    )),
    ('Fechas y metadatos', (
        ('publication_dates', 'Mostrar fecha de publicación', False),
        ('last_seen', 'Mostrar fecha de última vista', False),
        ('metadata', 'Mostrar datos de extracción y seguimiento', False),
    )),
    ('Análisis y valoración', (
        ('calculate', 'Buscar y calcular el ACM', True),
        ('adjust_valuation', 'Ajustar la valoración', True),
        ('adjust_areas', 'Comparar escenarios de superficies', False),
        ('ai', 'Usar explicación y propuestas de IA', False),
        ('nearby', 'Consultar lugares cercanos', False),
    )),
    ('Reportes e historial', (
        ('report_notes', 'Añadir justificación u observaciones al reporte', True),
        ('history', 'Guardar y consultar historial propio', True),
        ('reports', 'Generar reportes', True),
        ('report_photos', 'Incluir fotografías en el reporte PDF', True),
        ('export', 'Exportar datos del análisis', False),
    )),
)
DEFAULTS = {key: default for _, items in CATEGORIES for key, _, default in items}


def database():
    return getattr(settings, 'ACM_ACCESS_DATABASE', 'default')


def role_catalog():
    # Read-only against the actual singular Propify user and role tables.
    with connections['propifai'].cursor() as cursor:
        cursor.execute('SELECT r.id, r.name, r.is_internal, r.area_id, a.name '
                       'FROM [dbo].[role] r JOIN [dbo].[area] a ON a.id=r.area_id '
                       'WHERE r.is_active=1 ORDER BY a.name, r.name')
        return [dict(id=int(r[0]), name=r[1], internal=bool(r[2]), area_id=int(r[3]), area=r[4]) for r in cursor.fetchall()]


@dataclass
class ACMIdentity:
    pk: str
    username: str
    first_name: str = ''
    last_name: str = ''
    is_active: bool = True
    is_authenticated: bool = True
    is_superuser: bool = False

    def get_full_name(self):
        return (self.first_name + ' ' + self.last_name).strip()


@dataclass
class ACMAccess:
    user: ACMIdentity
    own_role: dict
    role: dict
    permissions: dict
    revision: int
    nonce: str

    @property
    def can_preview(self):
        return self.user.is_superuser or self.own_role['name'].strip().casefold() in PREVIEW_ROLES

    @property
    def can_configure(self):
        return self.user.is_superuser or self.own_role['name'].strip().casefold() == 'administrador'

    @property
    def previewing(self):
        return self.role['id'] != self.own_role['id']

    @property
    def fingerprint(self):
        data = [self.user.pk, self.role['id'], self.revision, self.permissions, self.nonce]
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def policy_for(role):
    if role['name'].strip().casefold() == 'administrador':
        return {key: True for key in DEFAULTS}, 0
    policy = ACMRolePolicy.objects.using(database()).filter(role_id=role['id']).first() if role['id'] else None
    values = dict(DEFAULTS)
    if policy:
        values.update({key: value for key, value in policy.permissions.items() if key in DEFAULTS and isinstance(value, bool)})
    # A logo, URL, or unreviewed watermark can identify the source independently.
    if not values['portal_names']:
        for key in ('portal_pins', 'publication', 'portal_link', 'unreviewed_photos'):
            values[key] = False
    if not values['property_data']:
        for key in ('property_pins', 'photos', 'unreviewed_photos', 'calculate', 'reports', 'export', 'ai'):
            values[key] = False
    return values, policy.revision if policy else 0


def get_access(request):
    if hasattr(request, 'acm_access'):
        return request.acm_access
    session = getattr(request, 'session', {})
    profile = session.get(SESSION_PROFILE)
    token = session.get(SESSION_TOKEN)
    # Reuse a verified Propify login, without creating or impersonating Prometeo users.
    if not profile or not token:
        if session.get('acm_logged_out'):
            return None
        profile = session.get('prospects_propify_profile')
        token = session.get('prospects_propify_access_token')
    if not isinstance(profile, dict) or not token or not str(profile.get('id') or profile.get('pk') or '').isdigit():
        return None
    uid = str(profile.get('id') or profile.get('pk'))
    with connections['propifai'].cursor() as cursor:
        cursor.execute('SELECT u.id, u.username, u.first_name, u.last_name, r.id, r.name, u.is_superuser '
                       'FROM [dbo].[user] u LEFT JOIN [dbo].[role] r ON r.id=u.role_id AND r.is_active=1 '
                       'WHERE u.id=%s AND u.is_active=1', [uid])
        row = cursor.fetchone()
    if not row:
        return None
    user = ACMIdentity(str(row[0]), row[1], row[2] or '', row[3] or '', is_superuser=bool(row[6]))
    own = {'id': int(row[4]) if row[4] else 0, 'name': row[5] or 'Sin rol'}
    selected = session.get(SESSION_PREVIEW, {})
    role = own
    if selected.get('owner') == user.pk and (user.is_superuser or own['name'].strip().casefold() in PREVIEW_ROLES):
        role = next((r for r in role_catalog() if r['id'] == selected.get('role_id')), own)
    permissions, revision = policy_for(role)
    access = ACMAccess(user, own, role, permissions, revision, selected.get('nonce', '') if selected.get('owner') == user.pk else '')
    request.acm_access = access
    request.acm_identity = user
    return access


def required(capability=None, page=False):
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            try:
                access = get_access(request)
            except Exception:
                return JsonResponse({'error': 'No se pudo validar el acceso a Propify. Reintenta.'}, status=503)
            if access is None:
                if page:
                    return redirect('/acm/login/?' + urlencode({'next': request.get_full_path()}))
                return JsonResponse({'error': 'Ingresa con tu cuenta de Propify.', 'login_url': '/acm/login/'}, status=401)
            if capability and not access.permissions.get(capability, False):
                return JsonResponse({'error': 'Esta función no está habilitada para la vista activa.'}, status=403)
            try:
                response = view(request, *args, **kwargs)
            except DatabaseError:
                return JsonResponse({'error': 'No se pudo consultar la configuración o el historial. Reintenta.'}, status=503)
            response['Cache-Control'] = 'no-store'
            response['Vary'] = 'Cookie'
            return response
        return wrapped
    return decorator


def template_context(request):
    access = request.acm_access
    return {'acm_access': access, 'acm_permissions': access.permissions,
            'show_acm_configuration': access.can_configure,
            'acm_roles': role_catalog() if access.can_preview or access.can_configure else [],
            'sources': ('all',), 'acm_is_authenticated': True}


def set_perspective(request, role_id):
    access = request.acm_access
    if not access.can_preview:
        raise PermissionDenied
    if role_id and not any(r['id'] == role_id for r in role_catalog()):
        raise ValueError('Selecciona un rol activo de Propify.')
    request.session[SESSION_PREVIEW] = {'owner': access.user.pk, 'role_id': role_id or access.own_role['id'], 'nonce': secrets.token_hex(16)}


def legacy_admin(view):
    @required()
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        access = request.acm_access
        if not access.can_configure or access.role['name'].strip().casefold() != 'administrador':
            return JsonResponse({'error': 'Esta herramienta pertenece a la administración del sistema.'}, status=403)
        return view(request, *args, **kwargs)
    return wrapped
