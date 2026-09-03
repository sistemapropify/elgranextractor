import base64
import json
import logging
import math
import os
import re
from uuid import uuid4

import requests
from django.contrib import messages
from django.db import DatabaseError, connection
from django.db.models import Q
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.conf import settings

from .models import PropertyProspect
from .forms import ProspectCaptureForm, ProspectEditForm
from .propify_auth import (
    PropifyAuthError,
    WEB_PROFILE_SESSION_KEY,
    WEB_TOKEN_SESSION_KEY,
    authenticate_propify_credentials,
    clear_web_propify_session,
    get_web_propify_principal,
    propify_web_required,
    safe_next_url,
)

logger = logging.getLogger(__name__)


def _guardar_foto_azure(foto):
    """Sube la foto directamente a Azure Blob (evita el storage de Django que
    falla con MEDIA_ROOT=None) y devuelve el nombre del blob (ruta) para
    guardarlo en prospect.photo."""
    from datetime import datetime
    from django.conf import settings as _s
    from captura.azure_storage import get_blob_service_client
    ext = os.path.splitext(foto.name or '')[-1] or '.jpg'
    nombre = 'prospects/photos/%s/prospecto_%s%s' % (
        datetime.now().strftime('%Y/%m'),
        uuid4().hex[:10],
        ext,
    )
    contenedor = getattr(_s, 'AZURE_CONTAINER', 'fotosprospecciones')
    bsc = get_blob_service_client()
    blob = bsc.get_container_client(contenedor).get_blob_client(nombre)
    blob.upload_blob(foto.read(), overwrite=True,
                     content_type=foto.content_type or 'image/jpeg')
    return nombre


def signed_prospect_photo(prospect):
    """Devuelve la URL de la foto del prospecto firmada con SAS (24h).

    El contenedor de fotos es privado; sin la firma el navegador recibe 403.
    Si no hay foto o no se puede firmar, devuelve '' o la URL original.
    """
    try:
        raw_url = prospect.photo.url if prospect.photo else ''
    except (ValueError, AttributeError):
        return ''
    if not raw_url:
        return ''
    try:
        from captura.azure_storage import generate_read_sas_url
        return generate_read_sas_url(raw_url, expiry_minutes=1440) or raw_url
    except Exception:
        logger.warning('No se pudo firmar SAS de la foto del prospecto.', exc_info=True)
        return raw_url


def _prospects_for_principal(principal):
    """Capturas propias de una identidad Propify, incluidas las antiguas."""
    return PropertyProspect.objects.filter(
        Q(mobile_user=principal.mobile_user)
        | Q(
            mobile_user__isnull=True,
            captured_by_username__iexact=principal.username,
        )
    )


def propify_login(request):
    if request.method == 'GET' and get_web_propify_principal(request) is not None:
        return redirect(safe_next_url(request))

    error = ''
    username = ''
    if request.method == 'POST':
        username = str(request.POST.get('username', '')).strip()
        password = str(request.POST.get('password', ''))
        if not username or not password:
            error = 'Usuario y contraseña son obligatorios.'
        else:
            try:
                _, principal = authenticate_propify_credentials(username, password)
            except PropifyAuthError as exc:
                error = str(exc)
            else:
                request.session[WEB_TOKEN_SESSION_KEY] = principal.token
                request.session[WEB_PROFILE_SESSION_KEY] = principal.profile
                return redirect(safe_next_url(request))

    return render(request, 'prospects/propify_login.html', {
        'error': error,
        'username': username,
        'next': safe_next_url(request),
    })


def propify_logout(request):
    clear_web_propify_session(request)
    return redirect('prospects:login')


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: detección de dispositivo móvil/tablet por User-Agent
# ─────────────────────────────────────────────────────────────────────────────
MOBILE_UA_RE = re.compile(
    r'(android|iphone|ipad|ipod|mobile|tablet|blackberry|windows phone)',
    re.IGNORECASE,
)


def is_mobile_device(request) -> bool:
    """
    Devuelve True si el request viene de un móvil o tablet.
    Se usa para mostrar/ocultar el botón de procesar con IA
    y para bloquear el endpoint /process/ desde desktop.
    """
    ua = request.META.get('HTTP_USER_AGENT', '')
    return bool(MOBILE_UA_RE.search(ua))


def _mobile_capture_actors():
    """Obtiene el usuario APK sin exigir que exista un agente web relacionado."""
    prospect_table = connection.ops.quote_name(PropertyProspect._meta.db_table)
    mobile_user_table = connection.ops.quote_name('prospects_mobileprospectuser')
    try:
        with connection.cursor() as cursor:
            cursor.execute(f'''
                SELECT prospect.id,
                       prospect.mobile_user_id,
                       prospect.captured_by_username,
                       mobile_user.username
                FROM {prospect_table} prospect
                LEFT JOIN {mobile_user_table} mobile_user
                  ON mobile_user.id = prospect.mobile_user_id
            ''')
            return {
                row[0]: {
                    'mobile_user_id': row[1],
                    'captured_by_username': row[2] or '',
                    'mobile_username': row[3] or '',
                }
                for row in cursor.fetchall()
            }
    except DatabaseError:
        # Compatibilidad con instalaciones anteriores a la API móvil.
        logger.warning('No se encontró metadata de usuarios móviles de prospección.')
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# 1. CAPTURA: sube foto + coordenadas GPS → guarda borrador
# ─────────────────────────────────────────────────────────────────────────────
@method_decorator(propify_web_required, name='dispatch')
class CaptureView(View):
    """
    GET  → muestra el template de captura
    POST → guarda la captura completa en PropertyProspect y devuelve su id
    """

    def get(self, request):
        return render(request, 'prospects/capture.html', {
            'mode': 'new',
            'property_types': PropertyProspect.PROPERTY_TYPES,
            'google_maps_api_key': getattr(
                settings,
                'GOOGLE_MAPS_API_KEY',
                'AIzaSyBrL1QF7vTl9zF8FmCUumfRpFJcaYokO7Q',
            ),
        })

    def post(self, request):
        form = ProspectCaptureForm(request.POST, request.FILES)
        if not request.POST.get('origin'):
            form.add_error('origin', 'Selecciona el origen de la prospección.')
        if not form.is_valid():
            errors = {
                field: [str(error) for error in field_errors]
                for field, field_errors in form.errors.items()
            }
            first_error = next(
                (message for field_errors in errors.values() for message in field_errors),
                'Revisa los datos ingresados.',
            )
            return JsonResponse({
                'ok': False,
                'error': first_error,
                'errors': errors,
            }, status=400)

        prospect = form.save(commit=False)
        prospect.agent = None
        prospect.mobile_user = request.propify_user.mobile_user
        prospect.captured_by_username = request.propify_user.username
        prospect.status = 'pendiente'
        foto = request.FILES.get('photo')
        if foto:
            try:
                prospect.photo = _guardar_foto_azure(foto)
            except Exception:
                logger.exception('No se pudo subir la foto de la captura web.')
                return JsonResponse({
                    'ok': False,
                    'error': 'No se pudo subir la foto. Inténtalo nuevamente.',
                }, status=500)
        try:
            prospect.save()
        except Exception:
            logger.exception('No se pudo guardar la captura web de prospección.')
            return JsonResponse({
                'ok': False,
                'error': 'El servidor no pudo guardar la captura. Revisa los datos e inténtalo nuevamente.',
            }, status=500)

        # Tras guardar, volver automáticamente al dashboard de prospección
        # (/marketing/prospeccion/) en vez de abrir la página de detalle.
        return JsonResponse({
            'ok': True,
            'prospect_id': prospect.pk,
            'redirect_url': '/marketing/prospeccion/',
        })


# ─────────────────────────────────────────────────────────────────────────────
# 2. DETALLE / EDICIÓN: muestra el prospecto con opción de procesar con IA
# ─────────────────────────────────────────────────────────────────────────────
@method_decorator(propify_web_required, name='dispatch')
class ProspectDetailView(View):
    """
    GET   → muestra formulario prellenado (o vacío si aún no se procesó)
    POST  → guarda edición manual del agente
    """

    def get_prospect(self, request, pk):
        return get_object_or_404(_prospects_for_principal(request.propify_user), pk=pk)

    def get(self, request, pk):
        prospect = self.get_prospect(request, pk)
        form = ProspectEditForm(instance=prospect)
        return render(request, 'prospects/capture.html', {
            'prospect': prospect,
            'form': form,
            'photo_url': signed_prospect_photo(prospect),
            'mode': 'detail',
            'can_process': is_mobile_device(request),
            'property_types': PropertyProspect.PROPERTY_TYPES,
            'google_maps_api_key': getattr(
                settings,
                'GOOGLE_MAPS_API_KEY',
                'AIzaSyBrL1QF7vTl9zF8FmCUumfRpFJcaYokO7Q',
            ),
        })

    def post(self, request, pk):
        prospect = self.get_prospect(request, pk)
        # Las coordenadas llegan a veces vacías/'' en el cliente; si el prospecto
        # ya tiene GPS, se preservan para no invalidar el formulario ni borrarlas.
        post_data = request.POST.copy()

        def _normalizar_coord(key, actual):
            raw = (post_data.get(key) or '').strip()
            if raw:
                try:
                    val = float(raw)
                except (TypeError, ValueError):
                    raw = ''
                else:
                    # Rechazar NaN/Infinito (el JS a veces escribe 'NaN')
                    if not math.isfinite(val):
                        raw = ''
            if not raw:
                raw = str(actual) if actual is not None else ''
            post_data[key] = raw

        _normalizar_coord('latitude', prospect.latitude)
        _normalizar_coord('longitude', prospect.longitude)

        form = ProspectEditForm(post_data, request.FILES, instance=prospect)
        if form.is_valid():
            saved = form.save(commit=False)
            # Si tenía borrador y ya tiene datos, pasa a pendiente
            if saved.status == 'borrador' and (saved.phone or saved.owner_name):
                saved.status = 'pendiente'
            foto_edit = request.FILES.get('photo')
            if foto_edit:
                saved.photo = _guardar_foto_azure(foto_edit)
            saved.save()
            messages.success(request, 'Prospecto actualizado correctamente.')
            # Tras guardar, regresar automáticamente al dashboard de prospección
            return redirect('marketing_prospeccion_dashboard')
        logger.warning(
            'ProspectEditForm inválido pk=%s errores=%s',
            prospect.pk,
            dict(form.errors),
        )
        return render(request, 'prospects/capture.html', {
            'prospect': prospect,
            'form': form,
            'photo_url': signed_prospect_photo(prospect),
            'mode': 'detail',
            'property_types': PropertyProspect.PROPERTY_TYPES,
            'google_maps_api_key': getattr(
                settings,
                'GOOGLE_MAPS_API_KEY',
                'AIzaSyBrL1QF7vTl9zF8FmCUumfRpFJcaYokO7Q',
            ),
        })


# ─────────────────────────────────────────────────────────────────────────────
# 3. PROCESAR CON IA: llama Qwen3-VL y prellenar campos
# ─────────────────────────────────────────────────────────────────────────────
@method_decorator(propify_web_required, name='dispatch')
class ProcessImageView(View):
    """
    POST → lee la foto guardada, la envía a Qwen3-VL, actualiza el prospecto
           y devuelve JSON con los campos extraídos para que el frontend los muestre.
    """

    QWEN_API_URL = 'https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation'

    def post(self, request, pk):
        # Bloqueo server-side: solo móvil/tablet puede procesar con IA
        if not is_mobile_device(request):
            return JsonResponse({
                'ok': False,
                'error': 'El procesamiento con IA solo está disponible desde móvil o tablet.',
            }, status=403)

        prospect = get_object_or_404(_prospects_for_principal(request.propify_user), pk=pk)

        if not prospect.photo:
            return JsonResponse({'ok': False, 'error': 'No hay foto asociada.'}, status=400)

        try:
            extracted = self._call_qwen(prospect)
        except Exception as exc:
            logger.exception('Error al llamar Qwen3-VL: %s', exc)
            return JsonResponse({'ok': False, 'error': str(exc)}, status=500)

        # Actualizar solo los campos que Qwen encontró (no pisar lo ya editado manualmente)
        fields_map = {
            'owner_name': 'owner_name',
            'phone': 'phone',
            'operation_type': 'operation_type',
            'property_type': 'property_type',
            'price': 'price',
            'currency': 'currency',
            'bedrooms': 'bedrooms',
            'area_m2': 'area_m2',
        }
        for api_key, model_field in fields_map.items():
            value = extracted.get(api_key)
            if value not in (None, '', 'null'):
                setattr(prospect, model_field, value)

        prospect.ocr_raw_text = extracted.get('raw_text', '')
        prospect.ocr_processed_at = timezone.now()
        if prospect.status == 'borrador':
            prospect.status = 'pendiente'
        prospect.save()

        return JsonResponse({'ok': True, 'extracted': extracted})

    def _call_qwen(self, prospect: PropertyProspect) -> dict:
        from django.conf import settings

        # Leer imagen y convertir a base64
        with prospect.photo.open('rb') as f:
            image_b64 = base64.b64encode(f.read()).decode('utf-8')

        prompt = """Eres un asistente experto en inmuebles peruanos.
Analiza esta imagen de un anuncio inmobiliario y extrae ÚNICAMENTE la información visible.
Devuelve SOLO un objeto JSON válido con estas claves (usa null si no encuentras el dato):

{
  "owner_name": "nombre del propietario o agencia",
  "phone": "número de teléfono (solo dígitos, sin espacios)",
  "operation_type": "alquiler o venta (en minúsculas)",
  "property_type": "departamento | casa | local | terreno | oficina | otro",
  "price": número (solo el valor numérico, sin símbolo),
  "currency": "USD o PEN",
  "bedrooms": número de dormitorios,
  "area_m2": número de metros cuadrados,
  "raw_text": "todo el texto que puedes leer en la imagen"
}

No incluyas explicaciones, solo el JSON."""

        headers = {
            'Authorization': f'Bearer {settings.QWEN_API_KEY}',
            'Content-Type': 'application/json',
        }

        payload = {
            'model': 'qwen-vl-max',
            'input': {
                'messages': [
                    {
                        'role': 'user',
                        'content': [
                            {
                                'image': f'data:image/jpeg;base64,{image_b64}',
                            },
                            {
                                'text': prompt,
                            },
                        ],
                    }
                ]
            },
        }

        response = requests.post(
            self.QWEN_API_URL,
            json=payload,
            headers=headers,
            timeout=30.0,
        )
        response.raise_for_status()

        data = response.json()
        raw_content = data['output']['choices'][0]['message']['content'][0]['text']

        # Limpiar posibles bloques de código markdown
        raw_content = raw_content.strip()
        if raw_content.startswith('```'):
            raw_content = raw_content.split('```')[1]
            if raw_content.startswith('json'):
                raw_content = raw_content[4:]

        return json.loads(raw_content.strip())


# ─────────────────────────────────────────────────────────────────────────────
# 4. LISTA DE PROSPECTOS
# ─────────────────────────────────────────────────────────────────────────────
@propify_web_required
def prospect_list(request):
    qs = _prospects_for_principal(request.propify_user)

    status_filter = request.GET.get('status', '')
    if status_filter:
        qs = qs.filter(status=status_filter)

    stats = {
        'total': qs.count(),
        'borradores': qs.filter(status='borrador').count(),
        'pendientes': qs.filter(status='pendiente').count(),
        'contactados': qs.filter(status='contactado').count(),
        'negociando': qs.filter(status='negociando').count(),
        'captados': qs.filter(status='captado').count(),
    }

    return render(request, 'prospects/list.html', {
        'prospects': qs,
        'stats': stats,
        'status_filter': status_filter,
    })


@propify_web_required
def prospect_dashboard(request):
    """Dashboard cartográfico con las captaciones de todos los agentes."""
    prospects = list(PropertyProspect.objects.all().order_by('-created_at'))
    current_mobile_user_id = request.propify_user.mobile_user.pk
    mobile_actors = _mobile_capture_actors()

    agent_ids = {prospect.agent_id for prospect in prospects if prospect.agent_id}
    agent_model = PropertyProspect._meta.get_field('agent').remote_field.model
    agents_by_id = {
        agent.pk: agent for agent in agent_model.objects.filter(pk__in=agent_ids)
    }

    # El template del portal consume este contrato de datos para pintar
    # marcadores y tarjetas. Se mantiene el layout y comportamiento original.
    data = []
    user_identities = set()
    for prospect in prospects:
        actor = mobile_actors.get(prospect.pk, {})
        agent = agents_by_id.get(prospect.agent_id)
        if agent is not None:
            agent_name = ' '.join(
                part for part in (agent.first_name, agent.last_name) if part
            ).strip() or agent.username or f'Usuario {agent.pk}'
            user_identities.add(f'agent:{agent.pk}')
        else:
            agent_name = (
                actor.get('captured_by_username')
                or actor.get('mobile_username')
                or 'Usuario APK'
            )
            mobile_identity = actor.get('mobile_user_id') or agent_name
            user_identities.add(f'mobile:{mobile_identity}')
        can_edit = bool(
            prospect.mobile_user_id == current_mobile_user_id
            or (
                prospect.mobile_user_id is None
                and prospect.captured_by_username.lower() == request.propify_user.username.lower()
            )
        )

        # Contenedor de fotos privado: firmar URL con SAS (24h) para las tarjetas/mapa
        photo_url = signed_prospect_photo(prospect)

        data.append({
            'id': prospect.pk,
            'lat': str(prospect.latitude) if prospect.latitude is not None else '',
            'lng': str(prospect.longitude) if prospect.longitude is not None else '',
            'distrito': prospect.district or 'Sin distrito',
            'distrito_nombre': prospect.district or 'Sin distrito',
            'tipo_propiedad': prospect.get_property_type_display() or 'Prospección',
            'titulo': prospect.owner_name or f'Prospección #{prospect.pk}',
            'descripcion': prospect.address or prospect.notes or 'Sin dirección registrada',
            'precio_publicacion': str(prospect.price) if prospect.price is not None else '',
            'precio': str(prospect.price) if prospect.price is not None else '',
            'moneda': prospect.currency or 'USD',
            'area_construida': str(prospect.area_m2) if prospect.area_m2 is not None else '',
            'habitaciones': prospect.bedrooms or '',
            'banios': '',
            'direccion': prospect.address or '',
            'portal': 'Facebook',
            'es_externo': False,
            'es_propify': False,
            'es_captacion': True,
            'primera_imagen': photo_url,
            'agente': agent_name,
            'url': f'/prospects/{prospect.pk}/detail/' if can_edit else '',
            'status': prospect.get_status_display(),
            'telefono': prospect.phone or '',
            'marketplace_url': prospect.marketplace_url or '',
            'owner_name': prospect.owner_name or '',
            'notas': prospect.notes or '',
            'zona': prospect.zone or '',
            'operacion': prospect.get_operation_type_display() or '',
            'contrato': prospect.get_contract_type_display() or '',
            'origen': prospect.get_origin_display() or prospect.origin or '',
            'creado': prospect.created_at.strftime('%d/%m/%Y %H:%M') if prospect.created_at else '',
        })

    districts = sorted({p.district for p in prospects if p.district})
    geolocated = sum(1 for p in prospects if p.has_gps)
    user_count = len(user_identities)
    with_phone = sum(1 for p in prospects if (p.phone or '').strip())
    without_phone = len(prospects) - with_phone
    tipos_presentes = sorted({
        (p.get_property_type_display() or 'Prospección') for p in prospects
    })
    return render(request, 'prospects/dashboard.html', {
        'todas_propiedades_json': data,
        'distritos_arequipa': districts,
        'tipos_propiedad': tipos_presentes,
        'google_maps_api_key': getattr(
            settings,
            'GOOGLE_MAPS_API_KEY',
            'AIzaSyBrL1QF7vTl9zF8FmCUumfRpFJcaYokO7Q',
        ),
        'hide_filters': True,
        'mostrar_todos_marcadores': True,
        'map_title': 'Mapa de captaciones',
        'selection_title': 'Captaciones seleccionadas',
        'entity_singular': 'captación',
        'entity_plural': 'captaciones',
        'dashboard_stats': {
            'total': len(prospects),
            'geolocated': geolocated,
            'without_gps': len(prospects) - geolocated,
            'users': user_count,
            'with_phone': with_phone,
            'without_phone': without_phone,
        },
    })
