"""API autenticada para la aplicación Android de captura de prospectos."""

from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import MobileAppVersion, PropertyProspect
from .propify_auth import (
    PropifyAuthError,
    PropifyBearerAuthentication,
    authenticate_propify_credentials,
)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def mobile_version(request):
    release = MobileAppVersion.objects.filter(published=True).order_by('-version_code').first()
    if release is not None:
        return Response({
            'latest_version_code': release.version_code,
            'min_supported_version_code': release.min_supported_version_code,
            'download_url': release.download_url,
            'sha256': release.sha256,
            'force': release.force_update,
            'notes': release.release_notes,
        })
    return Response({
        'latest_version_code': int(getattr(settings, 'MOBILE_APP_LATEST_VERSION_CODE', 1)),
        'min_supported_version_code': int(getattr(settings, 'MOBILE_APP_MIN_SUPPORTED_VERSION_CODE', 1)),
        'download_url': getattr(settings, 'MOBILE_APP_DOWNLOAD_URL', ''),
        'sha256': getattr(settings, 'MOBILE_APP_SHA256', ''),
        'force': bool(getattr(settings, 'MOBILE_APP_FORCE', False)),
        'notes': getattr(settings, 'MOBILE_APP_RELEASE_NOTES', ''),
    })


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
        token_payload, principal = authenticate_propify_credentials(username, password)
    except PropifyAuthError as exc:
        return Response({'ok': False, 'error': str(exc)}, status=exc.status_code)

    return Response({
        'ok': True,
        'access': principal.token,
        'refresh': token_payload.get('refresh', ''),
        'user': {
            'id': str(principal.profile.get('id') or principal.profile.get('pk') or principal.pk),
            'username': principal.username,
            'name': str(
                principal.profile.get('name')
                or principal.profile.get('full_name')
                or principal.username
            ),
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
@authentication_classes([PropifyBearerAuthentication])
@permission_classes([IsAuthenticated])
def mobile_capture(request):
    mobile_user = request.user.mobile_user
    if request.method == 'GET':
        prospects = PropertyProspect.objects.filter(
            Q(mobile_user=mobile_user)
            | Q(mobile_user__isnull=True, captured_by_username__iexact=request.user.username)
        ).order_by('-created_at')
        return Response({'ok': True, 'results': [_serialize_prospect(item) for item in prospects]})

    try:
        prospect = PropertyProspect(
            agent=None,
            mobile_user=mobile_user,
            captured_by_username=request.user.username,
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
@authentication_classes([PropifyBearerAuthentication])
@permission_classes([IsAuthenticated])
def mobile_capture_detail(request, pk):
    prospect = PropertyProspect.objects.filter(pk=pk).filter(
        Q(mobile_user=request.user.mobile_user)
        | Q(mobile_user__isnull=True, captured_by_username__iexact=request.user.username)
    ).first()
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
