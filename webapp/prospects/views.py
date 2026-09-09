import base64
import json
import logging
import os
import re
from uuid import uuid4

import requests
from django.contrib import messages
from django.db import DatabaseError, connection, transaction
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponseForbidden, JsonResponse
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


def _form_errors_response(form, status=400):
    errors = {field: [str(error) for error in field_errors]
              for field, field_errors in form.errors.items()}
    first_error = next((message for values in errors.values() for message in values),
                       'Revisa los datos ingresados.')
    return JsonResponse({'ok': False, 'error': first_error, 'errors': errors}, status=status)


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


def _post_login_target(request):
    """Destino tras el login de Propify. Si no hay un 'next' profundo (o el next
    es la lista/landing por defecto), se abre el dashboard cartográfico."""
    destino = safe_next_url(request)
    if not destino or destino.rstrip('/') in ('/prospects', '/prospects/login'):
        destino = '/marketing/prospeccion/'
    return destino


def propify_login(request):
    if request.method == 'GET' and get_web_propify_principal(request) is not None:
        return redirect(_post_login_target(request))

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
                request.session.set_expiry(60 * 60 * 24 * 30)  # conservar login 30 días
                return redirect(_post_login_target(request))

    return render(request, 'prospects/propify_login.html', {
        'error': error,
        'username': username,
        'next': _post_login_target(request),
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
            'form': ProspectCaptureForm(),
            'property_types': PropertyProspect.PROPERTY_TYPES,
            'google_maps_api_key': getattr(
                settings,
                'GOOGLE_MAPS_API_KEY',
                'AIzaSyBrL1QF7vTl9zF8FmCUumfRpFJcaYokO7Q',
            ),
        })

    def post(self, request):
        foto = request.FILES.get('photo')
        if request.POST.get('photo_expected') == '1' and not foto:
            logger.warning('Captura web sin la foto anunciada: usuario_propify_id=%s', request.propify_user.pk)
            return JsonResponse({
                'ok': False,
                'error': 'La foto seleccionada no llegó al servidor. Selecciónala nuevamente y vuelve a guardar.',
            }, status=400)
        form = ProspectCaptureForm(request.POST, request.FILES)
        if not form.is_valid():
            logger.warning(
                'Captura web inválida: usuario_propify_id=%s campos=%s foto_recibida=%s',
                request.propify_user.pk, list(form.errors), bool(foto),
            )
            return _form_errors_response(form)

        prospect = form.save(commit=False)
        prospect.agent = None
        prospect.mobile_user = request.propify_user.mobile_user
        prospect.captured_by_username = request.propify_user.username
        prospect.status = 'pendiente'
        if foto:
            try:
                prospect.photo = _guardar_foto_azure(foto)
            except Exception:
                logger.exception('No se pudo subir la foto de la captura web: usuario_propify_id=%s', request.propify_user.pk)
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
        logger.info(
            'Captura web guardada: prospecto_id=%s usuario_propify_id=%s foto_guardada=%s foto_bytes=%s',
            prospect.pk, request.propify_user.pk, bool(prospect.photo), foto.size if foto else 0,
        )
        return JsonResponse({
            'ok': True,
            'prospect_id': prospect.pk,
            'photo_saved': bool(prospect.photo),
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
        # Espacio colaborativo: cualquier usuario Propify autenticado puede
        # consultar y editar las captaciones del equipo.
        return get_object_or_404(PropertyProspect, pk=pk)

    def get(self, request, pk):
        prospect = self.get_prospect(request, pk)
        form = ProspectEditForm(instance=prospect)
        return self.render_form(request, prospect, form)

    def render_form(self, request, prospect, form, status=200):
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
        }, status=status)

    def post(self, request, pk):
        prospect = self.get_prospect(request, pk)
        original_photo = prospect.photo.name
        wants_json = 'application/json' in request.headers.get('Accept', '')
        # Sin nueva ubicación se conserva el par guardado. Una ubicación nueva
        # incompleta o inválida debe avisarse, no mezclarse con la anterior.
        post_data = request.POST.copy()
        if not any((post_data.get(key) or '').strip() for key in ('latitude', 'longitude')):
            post_data['latitude'] = str(prospect.latitude) if prospect.latitude is not None else ''
            post_data['longitude'] = str(prospect.longitude) if prospect.longitude is not None else ''

        form = ProspectEditForm(post_data, request.FILES, instance=prospect)
        response_status = 400
        if form.is_valid():
            saved = form.save(commit=False)
            # Si tenía borrador y ya tiene datos, pasa a pendiente
            if saved.status == 'borrador' and (saved.phone or saved.owner_name):
                saved.status = 'pendiente'
            foto_edit = request.FILES.get('photo')
            try:
                if foto_edit:
                    saved.photo = _guardar_foto_azure(foto_edit)
            except Exception:
                logger.exception('No se pudo subir la foto al editar el prospecto pk=%s', pk)
                form.add_error('photo', 'No se pudo subir la foto. Inténtalo nuevamente.')
                response_status = 500
            else:
                try:
                    saved.save()
                except Exception:
                    logger.exception('No se pudo guardar la edición del prospecto pk=%s', pk)
                    form.add_error(None, 'El servidor no pudo guardar los cambios. Inténtalo nuevamente.')
                    response_status = 500
                else:
                    if wants_json:
                        return JsonResponse({
                            'ok': True, 'prospect_id': saved.pk,
                            'photo_saved': bool(saved.photo),
                            'redirect_url': '/marketing/prospeccion/',
                        })
                    messages.success(request, 'Prospecto actualizado correctamente.')
                    return redirect('marketing_prospeccion_dashboard')
        logger.warning(
            'ProspectEditForm inválido pk=%s errores=%s',
            prospect.pk,
            list(form.errors),
        )
        if wants_json:
            return _form_errors_response(form, status=response_status)
        prospect.photo = original_photo
        return self.render_form(request, prospect, form, status=response_status)


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

        # El procesamiento también pertenece al espacio compartido.
        prospect = get_object_or_404(PropertyProspect, pk=pk)

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
    # Igual que el dashboard, la lista muestra las captaciones de todo el equipo.
    qs = PropertyProspect.objects.all().order_by('-created_at', '-pk')

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


@csrf_exempt
@propify_web_required
def tomar_prospeccion(request, pk):
    """Tomar / soltar una captación del dashboard de prospección.

    - 'tomar':   asigna la captación al usuario actual SOLO si nadie la tomó.
    - 'soltar':  la libera SOLO si la tomó el usuario actual.
    Regresa JSON con el nuevo estado para que el panel se repinte al instante.
    """
    prospect = get_object_or_404(PropertyProspect, pk=pk)
    principal = getattr(request, 'propify_user', None)
    username = str(getattr(principal, 'username', '') or '').strip()
    if not username:
        return JsonResponse({'ok': False, 'error': 'Sesión de usuario inválida.'}, status=401)

    accion = (request.POST.get('accion') or request.GET.get('accion') or '').strip().lower()
    if accion not in ('tomar', 'soltar'):
        return JsonResponse({'ok': False, 'error': 'Acción inválida.'}, status=400)

    with transaction.atomic():
        locked = PropertyProspect.objects.select_for_update().get(pk=pk)
        actual = (locked.tomada_por_username or '').strip()

        if accion == 'tomar':
            if actual:
                if actual == username:
                    return JsonResponse({
                        'ok': True,
                        'tomada_por_username': actual,
                        'nota': 'Ya la tenías tomada.',
                    })
                return JsonResponse({
                    'ok': False,
                    'error': f'Esta prospección ya la tomó {actual}.',
                    'tomada_por_username': actual,
                }, status=409)
            locked.tomada_por_username = username
            locked.tomada_en = timezone.now()
            locked.save(update_fields=['tomada_por_username', 'tomada_en'])
            return JsonResponse({'ok': True, 'tomada_por_username': username})

        # accion == 'soltar'
        if not actual:
            return JsonResponse({'ok': True, 'tomada_por_username': '', 'nota': 'Ya estaba libre.'})
        if actual != username:
            return JsonResponse({
                'ok': False,
                'error': f'Solo {actual} puede soltar esta prospección.',
                'tomada_por_username': actual,
            }, status=403)
        locked.tomada_por_username = ''
        locked.tomada_en = None
        locked.save(update_fields=['tomada_por_username', 'tomada_en'])
        return JsonResponse({'ok': True, 'tomada_por_username': ''})


@propify_web_required
def prospect_dashboard(request):
    """Dashboard cartográfico con las captaciones de todos los agentes."""
    prospects = list(PropertyProspect.objects.all().order_by('-created_at'))
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
            'url': f'/prospects/{prospect.pk}/detail/',
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
            'tomada_por_username': prospect.tomada_por_username or '',
            'tomada_en': prospect.tomada_en.strftime('%d/%m/%Y %H:%M') if prospect.tomada_en else '',
            'captado': bool(prospect.captado),
        })

    districts = sorted({p.district for p in prospects if p.district})
    geolocated = sum(1 for p in prospects if p.has_gps)
    user_count = len(user_identities)
    with_phone = sum(1 for p in prospects if (p.phone or '').strip())
    without_phone = len(prospects) - with_phone
    tipos_presentes = sorted({
        (p.get_property_type_display() or 'Prospección') for p in prospects
    })
    principal_actual = getattr(request, 'propify_user', None)
    usuario_actual_username = str(getattr(principal_actual, 'username', '') or '').strip()
    return render(request, 'prospects/dashboard.html', {
        'todas_propiedades_json': data,
        'usuario_actual_username': usuario_actual_username,
        'puede_metricas': _propify_puede_metricas(request),
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


# ── Métricas gerenciales (prospección) ──────────────────────────

def _propify_rol_db(username):
    """Lee el rol del usuario en la tabla `users` de dbpropify_be (alias 'propifai')."""
    if not username:
        return ''
    try:
        from django.db import connections
        with connections['propifai'].cursor() as cursor:
            for col in ('role', 'rol', 'rol_name', 'nombre_rol'):
                try:
                    cursor.execute(f'SELECT {col} FROM users WHERE username = %s', [username])
                    row = cursor.fetchone()
                    if row and row[0]:
                        return str(row[0])
                except Exception:
                    continue
    except Exception:
        pass
    return ''


def _propify_puede_metricas(request):
    principal = getattr(request, 'propify_user', None)
    username = str(getattr(principal, 'username', '') or '').strip()
    if not username:
        return False
    # En desarrollo local (DEBUG) se muestra a cualquier usuario logueado para
    # poder probar; en producción se exige el rol gerente/desarrollador.
    if settings.DEBUG:
        return True
    rol = _propify_rol_db(username).lower()
    return any(tok in rol for tok in ('gerente', 'desarrollador', 'developer'))


def _agente_captacion(prospect, mobile_actors, agents_by_id):
    agent = agents_by_id.get(prospect.agent_id)
    if agent is not None:
        nombre = ' '.join(part for part in (agent.first_name, agent.last_name) if part).strip()
        return nombre or agent.username or f'Usuario {agent.pk}'
    actor = mobile_actors.get(prospect.pk, {})
    return actor.get('captured_by_username') or actor.get('mobile_username') or 'Usuario APK'


def _bucket_key(dt_local, gran):
    if gran == 'hora':
        return (dt_local.year, dt_local.month, dt_local.day, dt_local.hour), dt_local.strftime('%d/%m %H:00')
    if gran == 'semana':
        iso = dt_local.isocalendar()
        return (iso.year, iso.week), f'{iso.year}-S{iso.week:02d}'
    if gran == 'mes':
        return (dt_local.year, dt_local.month), dt_local.strftime('%m/%Y')
    if gran == 'anio':
        return (dt_local.year,), str(dt_local.year)
    return (dt_local.year, dt_local.month, dt_local.day), dt_local.strftime('%d/%m/%Y')


def _metricas_datos(gran, agente_filtro):
    prospects = list(PropertyProspect.objects.all().order_by('created_at', 'pk'))
    mobile_actors = _mobile_capture_actors()
    agent_ids = {p.agent_id for p in prospects if p.agent_id}
    agent_model = PropertyProspect._meta.get_field('agent').remote_field.model
    agents_by_id = {a.pk: a for a in agent_model.objects.filter(pk__in=agent_ids)}
    serie = {}
    orden = []
    agentes = set()
    for pr in prospects:
        if pr.created_at is None:
            continue
        label = _agente_captacion(pr, mobile_actors, agents_by_id)
        agentes.add(label)
        if agente_filtro and agente_filtro != 'total' and label != agente_filtro:
            continue
        dt_local = timezone.localtime(pr.created_at)
        key, texto = _bucket_key(dt_local, gran)
        if key not in serie:
            serie[key] = 0
            orden.append((key, texto))
        serie[key] += 1
    puntos = [{'label': texto, 'count': serie[key]} for key, texto in orden]
    return puntos, sorted(agentes)


def _render_chart_metricas(puntos, gran, agente_filtro):
    try:
        import base64 as _b64
        from io import BytesIO
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except Exception:
        return ''
    labels = [p['label'] for p in puntos]
    values = [p['count'] for p in puntos]
    if not labels:
        return ''
    try:
        fig, ax = plt.subplots(figsize=(12, 4.6), facecolor='#0d1117')
        ax.set_facecolor('#0d1117')
        ax.plot(range(len(labels)), values, color='#58a6ff', linewidth=2, marker='o', markersize=4)
        ax.fill_between(range(len(labels)), values, color='#58a6ff', alpha=0.15)
        for spine in ax.spines.values():
            spine.set_color('#30363d')
        ax.tick_params(colors='#8b949e')
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=8)
        ax.set_title(f'Evolución de captaciones · {gran} · {agente_filtro}', color='#e6edf3', fontsize=12)
        ax.grid(True, color='#21262d')
        buf = BytesIO()
        fig.tight_layout()
        fig.savefig(buf, format='png', facecolor=fig.get_facecolor())
        plt.close(fig)
        return _b64.b64encode(buf.getvalue()).decode('ascii')
    except Exception:
        return ''


@propify_web_required
def prospect_metricas(request):
    """Dashboard gerencial: evolución de captaciones por agente y granularidad."""
    if not _propify_puede_metricas(request):
        if 'application/json' in request.headers.get('Accept', ''):
            return JsonResponse({'ok': False, 'error': 'No tienes permisos gerenciales.'}, status=403)
        return HttpResponseForbidden('No tienes permisos para ver métricas gerenciales.')
    gran = (request.GET.get('gran', '') or 'dia').strip().lower()
    if gran not in ('hora', 'dia', 'semana', 'mes', 'anio'):
        gran = 'dia'
    agente_filtro = (request.GET.get('agente', '') or 'total').strip()
    puntos, agentes = _metricas_datos(gran, agente_filtro)
    chart_b64 = _render_chart_metricas(puntos, gran, agente_filtro)
    total = sum(p['count'] for p in puntos)
    return render(request, 'prospects/metricas.html', {
        'chart_b64': chart_b64,
        'granularidad': gran,
        'agente_filtro': agente_filtro,
        'agentes': agentes,
        'total': total,
        'puntos': puntos,
        'granularidades': [
            ('hora', 'Hora'),
            ('dia', 'Día'),
            ('semana', 'Semana'),
            ('mes', 'Mes'),
            ('anio', 'Año'),
        ],
    })
