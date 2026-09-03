import base64
import json
import logging
import re
from decimal import Decimal, InvalidOperation

import requests
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from .models import PropertyProspect
from .forms import ProspectEditForm

logger = logging.getLogger(__name__)


def get_property_type_choices():
    """Catálogo activo de dbo.property_type adaptado al campo del prospecto."""
    from django.db import connections
    value_map = {
        'Casa': 'casa', 'Departamento': 'departamento', 'Local': 'local',
        'Oficina': 'oficina', 'Otros': 'otro', 'Terreno': 'terreno',
    }
    with connections['propifai'].cursor() as cursor:
        cursor.execute('SELECT id, name FROM dbo.property_type WHERE is_active = 1 ORDER BY name')
        return [{'id': row[0], 'value': value_map.get(row[1], str(row[1]).lower()), 'name': row[1]} for row in cursor.fetchall()]


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


# ─────────────────────────────────────────────────────────────────────────────
# 1. CAPTURA: sube foto + coordenadas GPS → guarda borrador
# ─────────────────────────────────────────────────────────────────────────────
class CaptureView(View):
    """
    GET  → muestra el template de captura
    POST → guarda la foto y las coordenadas GPS, devuelve JSON con el prospect_id
    """

    def get(self, request):
        return render(request, 'prospects/capture.html', {
            'mode': 'new',
            'property_types': get_property_type_choices(),
        })

    def post(self, request):
        photo = request.FILES.get('photo')
        if not photo:
            return JsonResponse({'ok': False, 'error': 'No se recibió imagen.'}, status=400)

        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        try:
            latitude_value = Decimal(latitude)
            longitude_value = Decimal(longitude)
            if not (-90 <= latitude_value <= 90 and -180 <= longitude_value <= 180):
                raise InvalidOperation
        except (InvalidOperation, TypeError, ValueError):
            return JsonResponse({
                'ok': False,
                'error': 'Debes permitir la ubicación GPS antes de guardar la captura.',
            }, status=400)

        prospect = PropertyProspect.objects.create(
            agent=request.current_user,
            photo=photo,
            latitude=latitude_value,
            longitude=longitude_value,
            status='borrador',
        )

        return JsonResponse({
            'ok': True,
            'prospect_id': prospect.pk,
            'redirect_url': f'/prospects/{prospect.pk}/detail/',
        })


# ─────────────────────────────────────────────────────────────────────────────
# 2. DETALLE / EDICIÓN: muestra el prospecto con opción de procesar con IA
# ─────────────────────────────────────────────────────────────────────────────
class ProspectDetailView(View):
    """
    GET   → muestra formulario prellenado (o vacío si aún no se procesó)
    POST  → guarda edición manual del agente
    """

    def get_prospect(self, request, pk):
        return get_object_or_404(PropertyProspect, pk=pk, agent=request.current_user)

    def get(self, request, pk):
        prospect = self.get_prospect(request, pk)
        form = ProspectEditForm(instance=prospect)
        return render(request, 'prospects/capture.html', {
            'prospect': prospect,
            'form': form,
            'mode': 'detail',
            'can_process': is_mobile_device(request),
            'property_types': get_property_type_choices(),
        })

    def post(self, request, pk):
        prospect = self.get_prospect(request, pk)
        form = ProspectEditForm(request.POST, instance=prospect)
        if form.is_valid():
            saved = form.save(commit=False)
            # Si tenía borrador y ya tiene datos, pasa a pendiente
            if saved.status == 'borrador' and (saved.phone or saved.owner_name):
                saved.status = 'pendiente'
            saved.save()
            messages.success(request, 'Prospecto actualizado correctamente.')
            return redirect('prospects:detail', pk=pk)
        return render(request, 'prospects/capture.html', {
            'prospect': prospect,
            'form': form,
            'mode': 'detail',
            'property_types': get_property_type_choices(),
        })


# ─────────────────────────────────────────────────────────────────────────────
# 3. PROCESAR CON IA: llama Qwen3-VL y prellenar campos
# ─────────────────────────────────────────────────────────────────────────────
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

        prospect = get_object_or_404(PropertyProspect, pk=pk, agent=request.current_user)

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
def prospect_list(request):
    qs = PropertyProspect.objects.filter(agent=request.current_user)

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


# ─────────────────────────────────────────────────────────────────────────────
# 5. DASHBOARD DE PROSPECCIONES (captaciones de todos los agentes)
#    URL: /marketing/prospeccion/  (se mantienen Alertas CRM móviles intactas)
# ─────────────────────────────────────────────────────────────────────────────
def prospect_dashboard(request):
    """Dashboard de prospecciones: KPIs, filtros y listado de captaciones."""
    from django.db.models import Q

    qs = PropertyProspect.objects.all().order_by('-created_at')
    distrito = (request.GET.get('distrito') or '').strip()
    tipo = (request.GET.get('tipo') or '').strip()
    telefono = (request.GET.get('telefono') or '').strip()  # con | sin

    if distrito:
        qs = qs.filter(district=distrito)
    if tipo:
        qs = qs.filter(property_type=tipo)
    if telefono == 'con':
        qs = qs.exclude(phone='').exclude(phone__isnull=True)
    elif telefono == 'sin':
        qs = qs.filter(Q(phone__isnull=True) | Q(phone=''))

    prospects = list(qs)

    agent_ids = {prospect.agent_id for prospect in prospects if prospect.agent_id}
    agent_model = PropertyProspect._meta.get_field('agent').remote_field.model
    agents_by_id = (
        {agent.pk: agent for agent in agent_model.objects.filter(pk__in=agent_ids)}
        if agent_ids
        else {}
    )

    rows = []
    for prospect in prospects:
        agent = agents_by_id.get(prospect.agent_id)
        if agent is not None:
            agent_name = ' '.join(
                part
                for part in (agent.first_name, agent.last_name)
                if part
            ).strip() or getattr(agent, 'username', '') or f'Usuario {agent.pk}'
        else:
            agent_name = prospect.captured_by_username or 'Usuario APK'
        rows.append({
            'id': prospect.pk,
            'distrito': prospect.district or 'Sin distrito',
            'tipo_propiedad': prospect.get_property_type_display() or 'Prospección',
            'titulo': prospect.owner_name or f'Prospección #{prospect.pk}',
            'descripcion': prospect.address or prospect.notes or 'Sin dirección registrada',
            'precio': str(prospect.price) if prospect.price is not None else '',
            'moneda': prospect.currency or 'USD',
            'area': str(prospect.area_m2) if prospect.area_m2 is not None else '',
            'habitaciones': prospect.bedrooms or '',
            'telefono': prospect.phone or '',
            'agente': agent_name,
            'zona': prospect.zone or '',
            'operacion': prospect.get_operation_type_display() or '',
            'contrato': prospect.get_contract_type_display() or '',
            'origen': prospect.get_origin_display() or prospect.origin or '',
            'status': prospect.get_status_display(),
            'url': f'/prospects/{prospect.pk}/detail/',
            'foto': prospect.photo.url if prospect.photo else '',
            'creado': (
                prospect.created_at.strftime('%d/%m/%Y %H:%M')
                if prospect.created_at
                else ''
            ),
        })

    districts = sorted({p.district for p in prospects if p.district})
    tipos = sorted({
        prospect.get_property_type_display()
        for prospect in prospects
        if prospect.get_property_type_display()
    })
    with_phone = sum(1 for prospect in prospects if (prospect.phone or '').strip())
    geolocated = sum(
        1
        for prospect in prospects
        if prospect.latitude is not None and prospect.longitude is not None
    )

    return render(request, 'prospects/dashboard.html', {
        'prospects': rows,
        'distritos_arequipa': districts,
        'tipos_propiedad': tipos,
        'filtro_distrito': distrito,
        'filtro_tipo': tipo,
        'filtro_telefono': telefono,
        'dashboard_stats': {
            'total': len(prospects),
            'geolocated': geolocated,
            'without_gps': len(prospects) - geolocated,
            'users': len(
                {
                    prospect.agent_id or prospect.captured_by_username
                    for prospect in prospects
                }
            ),
            'with_phone': with_phone,
            'without_phone': len(prospects) - with_phone,
        },
    })
