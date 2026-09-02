"""API autenticada para la aplicación Android de captura de prospectos."""

import hashlib
import logging
import secrets
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings
from django.core.cache import cache
from rest_framework import status
from rest_framework.authentication import BaseAuthentication, SessionAuthentication, get_authorization_header
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .crm_alerts import sync_crm_visit_alerts
from .models import CrmVisitIntentAlert, MobileAppVersion, MobileNotificationDevice, MobileProspectSession, MobileProspectUser, PropertyProspect


logger = logging.getLogger(__name__)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def mobile_version(request):
    """Fuente controlada de metadatos del APK móvil (sin autenticar)."""
    release = MobileAppVersion.objects.filter(published=True).order_by('-version_code').first()
    if release:
        return Response({'latest_version_code': release.version_code,
                         'min_supported_version_code': release.min_supported_version_code,
                         'download_url': release.download_url, 'sha256': release.sha256,
                         'force': release.force_update, 'notes': release.release_notes})
    return Response({
        'latest_version_code': int(getattr(settings, 'MOBILE_APP_LATEST_VERSION_CODE', 1)),
        'min_supported_version_code': int(getattr(settings, 'MOBILE_APP_MIN_SUPPORTED_VERSION_CODE', 1)),
        'download_url': getattr(settings, 'MOBILE_APP_DOWNLOAD_URL', ''),
        'sha256': getattr(settings, 'MOBILE_APP_SHA256', ''),
        'force': bool(getattr(settings, 'MOBILE_APP_FORCE', False)),
        'notes': getattr(settings, 'MOBILE_APP_RELEASE_NOTES', ''),
    })


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def mobile_schema_health(request):
    """Comprueba que el esquema requerido por la APK ya fue migrado."""
    try:
        MobileProspectUser.objects.values_list('can_view_crm_alerts', flat=True).first()
        MobileProspectSession.objects.values_list('pk', flat=True).first()
        CrmVisitIntentAlert.objects.values_list('pk', flat=True).first()
        MobileNotificationDevice.objects.values_list('pk', flat=True).first()
    except Exception:
        logger.exception('El esquema de la API móvil de Prometeo no está disponible')
        return Response({'status': 'unavailable'}, status=503)
    return Response({'status': 'ok'})


@dataclass(frozen=True)
class MobilePrincipal:
    mobile_user: MobileProspectUser

    @property
    def is_authenticated(self):
        return True


class PrometeoMobileAuthentication(BaseAuthentication):
    """Autentica exclusivamente con una sesión propia emitida por Prometeo."""

    def authenticate(self, request):
        parts = get_authorization_header(request).split()
        if not parts:
            return None
        if len(parts) != 2 or parts[0].lower() != b'bearer':
            raise AuthenticationFailed('Encabezado Authorization inválido.')

        token = parts[1].decode('utf-8')
        token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
        session = MobileProspectSession.objects.select_related('user').filter(token_hash=token_hash).first()
        if session is None:
            raise AuthenticationFailed('La sesión móvil de Prometeo no es válida.')
        session.save(update_fields=['last_used_at'])
        return MobilePrincipal(session.user), token


def _optional_decimal(value, field_name):
    if value in (None, ''):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f'{field_name} debe ser un número válido.')


def _optional_int(value, field_name):
    if value in (None, ''):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(f'{field_name} debe ser un número entero.')
    if parsed < 0:
        raise ValueError(f'{field_name} no puede ser negativo.')
    return parsed


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def mobile_login(request):
    username = str(request.data.get('username', '')).strip()
    password = str(request.data.get('password', ''))
    if not username or not password:
        return Response({'ok': False, 'error': 'Usuario y contraseña son obligatorios.'}, status=400)

    try:
        propify_response = requests.post(
            settings.PROPIFY_AUTH_TOKEN_URL,
            json={'username': username, 'password': password},
            timeout=15,
        )
    except requests.RequestException:
        return Response({'ok': False, 'error': 'No se pudo comprobar el usuario en Propify.'}, status=503)
    if propify_response.status_code != 200:
        return Response({
            'ok': False,
            'error': f'Propify rechazó el inicio de sesión (código {propify_response.status_code}).',
        }, status=401)

    # La respuesta y los tokens de Propify se descartan. Prometeo crea su sesión propia.
    try:
        user, _ = MobileProspectUser.objects.get_or_create(username=username)
        supervisor_names = {
            value.strip().casefold()
            for value in str(getattr(settings, 'MOBILE_CRM_ALERT_SUPERVISORS', 'adminpropify')).split(',')
            if value.strip()
        }
        if username.casefold() in supervisor_names and not user.can_view_crm_alerts:
            user.can_view_crm_alerts = True
            user.save(update_fields=['can_view_crm_alerts'])
        plain_token = secrets.token_urlsafe(48)
        MobileProspectSession.objects.create(
            user=user,
            token_hash=hashlib.sha256(plain_token.encode('utf-8')).hexdigest(),
        )
    except Exception:
        logger.exception('Propify validó a %s, pero Prometeo no pudo crear la sesión móvil', username)
        return Response({
            'ok': False,
            'error': 'Propify validó el usuario, pero Prometeo no pudo crear la sesión móvil.',
        }, status=500)
    return Response({
        'ok': True,
        'access': plain_token,
        'user': {
            'id': str(user.pk),
            'username': user.username,
            'can_view_crm_alerts': user.can_view_crm_alerts,
        },
    })


def _serialize_prospect(prospect):
    return {
        'id': prospect.pk,
        'created_at': prospect.created_at.astimezone().strftime('%d/%m/%Y %H:%M'),
        'origin': prospect.origin,
        'origin_other': prospect.origin_other,
        'marketplace_url': prospect.marketplace_url,
        'owner_name': prospect.owner_name,
        'phone': prospect.phone,
        'operation_type': prospect.operation_type,
        'contract_type': prospect.contract_type,
        'property_type': prospect.property_type,
        'price': '' if prospect.price is None else str(prospect.price),
        'currency': prospect.currency,
        'bedrooms': '' if prospect.bedrooms is None else str(prospect.bedrooms),
        'area_m2': '' if prospect.area_m2 is None else str(prospect.area_m2),
        'zone': prospect.zone,
        'address': prospect.address,
        'district': prospect.district,
        'latitude': '' if prospect.latitude is None else str(prospect.latitude),
        'longitude': '' if prospect.longitude is None else str(prospect.longitude),
        'notes': prospect.notes,
        'status': prospect.status,
        'photo_url': prospect.photo.url if prospect.photo else '',
    }


def _apply_mobile_fields(prospect, request):
    origin = str(request.data.get('origin', '')).strip().lower()
    operation_type = str(request.data.get('operation_type', '')).strip().lower()
    contract_type = str(request.data.get('contract_type', '')).strip().lower()
    property_type = str(request.data.get('property_type', '')).strip().lower()
    currency = str(request.data.get('currency', 'USD')).strip().upper()

    valid_choices = {
        'origin': (origin, dict(PropertyProspect.ORIGIN_CHOICES)),
        'operation_type': (operation_type, dict(PropertyProspect.OPERATION_CHOICES)),
        'contract_type': (contract_type, dict(PropertyProspect.CONTRACT_CHOICES)),
        'property_type': (property_type, dict(PropertyProspect.PROPERTY_TYPES)),
        'currency': (currency, dict(PropertyProspect.CURRENCY_CHOICES)),
    }
    for field, (value, choices) in valid_choices.items():
        if value and value not in choices:
            raise ValueError(f'Valor inválido para {field}.')

    prospect.origin = origin
    prospect.origin_other = str(request.data.get('origin_other', '')).strip()
    prospect.marketplace_url = str(request.data.get('marketplace_url', '')).strip()
    prospect.owner_name = str(request.data.get('owner_name', '')).strip()
    prospect.phone = str(request.data.get('phone', '')).strip()
    prospect.operation_type = operation_type
    prospect.contract_type = contract_type
    prospect.property_type = property_type
    prospect.price = _optional_decimal(request.data.get('price'), 'Precio')
    prospect.currency = currency or 'USD'
    prospect.bedrooms = _optional_int(request.data.get('bedrooms'), 'Dormitorios')
    prospect.area_m2 = _optional_decimal(request.data.get('area_m2'), 'Área')
    prospect.address = str(request.data.get('address', '')).strip()
    prospect.zone = str(request.data.get('zone', '')).strip()
    prospect.district = str(request.data.get('district', '')).strip()
    prospect.latitude = _optional_decimal(request.data.get('latitude'), 'Latitud')
    prospect.longitude = _optional_decimal(request.data.get('longitude'), 'Longitud')
    prospect.notes = str(request.data.get('notes', '')).strip()
    photo = request.FILES.get('photo')
    if photo is not None:
        if not (photo.content_type or '').lower().startswith('image/'):
            raise ValueError('El archivo debe ser una imagen.')
        if photo.size > 15 * 1024 * 1024:
            raise ValueError('La imagen no debe superar 15 MB.')
        prospect.photo = photo


@api_view(['GET', 'POST'])
@authentication_classes([PrometeoMobileAuthentication])
@permission_classes([IsAuthenticated])
def mobile_capture(request):
    if request.method == 'GET':
        prospects = PropertyProspect.objects.filter(mobile_user=request.user.mobile_user).order_by('-created_at')
        return Response({'ok': True, 'results': [_serialize_prospect(item) for item in prospects]})

    try:
        prospect = PropertyProspect(
            mobile_user=request.user.mobile_user,
            captured_by_username=request.user.mobile_user.username,
            status='pendiente',
        )
        _apply_mobile_fields(prospect, request)
        prospect.full_clean()
        prospect.save()
    except ValueError as exc:
        return Response({'ok': False, 'error': str(exc)}, status=400)
    except Exception as exc:
        return Response({'ok': False, 'error': getattr(exc, 'message_dict', str(exc))}, status=400)

    return Response({
        'ok': True,
        'prospect_id': prospect.pk,
        'status': prospect.status,
        'detail_url': f'/prospects/{prospect.pk}/detail/',
    }, status=status.HTTP_201_CREATED)


@api_view(['GET', 'PUT'])
@authentication_classes([PrometeoMobileAuthentication])
@permission_classes([IsAuthenticated])
def mobile_capture_detail(request, pk):
    prospect = PropertyProspect.objects.filter(pk=pk, mobile_user=request.user.mobile_user).first()
    if prospect is None:
        return Response({'ok': False, 'error': 'Prospecto no encontrado.'}, status=404)
    if request.method == 'GET':
        return Response({'ok': True, 'prospect': _serialize_prospect(prospect)})
    try:
        _apply_mobile_fields(prospect, request)
        prospect.full_clean()
        prospect.save()
    except ValueError as exc:
        return Response({'ok': False, 'error': str(exc)}, status=400)
    except Exception as exc:
        return Response({'ok': False, 'error': getattr(exc, 'message_dict', str(exc))}, status=400)
    return Response({'ok': True, 'prospect_id': prospect.pk, 'status': prospect.status})


def _require_alert_supervisor(request):
    return bool(getattr(request.user.mobile_user, 'can_view_crm_alerts', False))


def _serialize_crm_alert(item):
    return {
        'id': item.pk, 'lead_id': item.source_lead_id, 'agent_name': item.agent_name,
        'contact_name': item.contact_name, 'phone': item.phone, 'property_code': item.property_code,
        'property_title': item.property_title, 'evidence': item.evidence, 'status': item.status,
        'detected_at': item.detected_at.isoformat(),
        'responded_at': item.responded_at.isoformat() if item.responded_at else None,
        'response_seconds': int((item.responded_at - item.detected_at).total_seconds()) if item.responded_at else None,
    }


@api_view(['GET'])
@authentication_classes([PrometeoMobileAuthentication])
@permission_classes([IsAuthenticated])
def mobile_crm_alerts(request):
    if not _require_alert_supervisor(request):
        return Response({'ok': False, 'error': 'No tienes acceso al control de alertas CRM.'}, status=403)
    requested_status = request.GET.get('status', CrmVisitIntentAlert.Status.PENDING)
    if requested_status not in dict(CrmVisitIntentAlert.Status.choices):
        requested_status = CrmVisitIntentAlert.Status.PENDING
    if requested_status == CrmVisitIntentAlert.Status.PENDING and cache.add('crm-alert-sync-recent', True, timeout=20):
        try:
            sync_crm_visit_alerts()
        except Exception:
            logger.exception('No se pudieron sincronizar las alertas CRM; se devuelve el último estado persistido')
    items = CrmVisitIntentAlert.objects.filter(status=requested_status)[:500]
    return Response({'ok': True, 'count': len(items), 'results': [_serialize_crm_alert(item) for item in items]})


@api_view(['GET', 'POST'])
@authentication_classes([PrometeoMobileAuthentication])
@permission_classes([IsAuthenticated])
def mobile_crm_alert_detail(request, pk):
    if not _require_alert_supervisor(request):
        return Response({'ok': False, 'error': 'No autorizado.'}, status=403)
    item = CrmVisitIntentAlert.objects.filter(pk=pk).first()
    if item is None:
        return Response({'ok': False, 'error': 'Alerta no encontrada.'}, status=404)
    if request.method == 'POST' and request.data.get('status') == CrmVisitIntentAlert.Status.CLOSED:
        item.status = CrmVisitIntentAlert.Status.CLOSED
        item.save(update_fields=['status', 'updated_at'])
    return Response({'ok': True, 'alert': _serialize_crm_alert(item)})


@api_view(['POST'])
@authentication_classes([PrometeoMobileAuthentication])
@permission_classes([IsAuthenticated])
def mobile_notification_device(request):
    if not _require_alert_supervisor(request):
        return Response({'ok': False, 'error': 'No autorizado.'}, status=403)
    registration_id = str(request.data.get('registration_id') or request.data.get('fcm_token') or '').strip()
    if not registration_id:
        return Response({'ok': False, 'error': 'registration_id es obligatorio.'}, status=400)
    target_type = str(request.data.get('target_type', MobileNotificationDevice.TargetType.FID))
    if target_type not in dict(MobileNotificationDevice.TargetType.choices):
        return Response({'ok': False, 'error': 'target_type no es válido.'}, status=400)
    device, _ = MobileNotificationDevice.objects.update_or_create(
        registration_id=registration_id,
        defaults={
            'user': request.user.mobile_user,
            'target_type': target_type,
            'device_name': str(request.data.get('device_name', ''))[:200],
            'active': True,
        },
    )
    return Response({'ok': True, 'device_id': device.pk})
