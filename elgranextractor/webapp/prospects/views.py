import base64
import json
import logging
import re

import requests
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from .models import PropertyProspect
from .forms import ProspectEditForm

logger = logging.getLogger(__name__)


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
        })

    def post(self, request):
        photo = request.FILES.get('photo')
        if not photo:
            return JsonResponse({'ok': False, 'error': 'No se recibió imagen.'}, status=400)

        prospect = PropertyProspect.objects.create(
            agent=request.current_user,
            photo=photo,
            latitude=request.POST.get('latitude') or None,
            longitude=request.POST.get('longitude') or None,
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
