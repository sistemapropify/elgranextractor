"""Authenticated model operations and a separate, labelled ACM estimate."""
import json
import math

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .ml_candidate_views import authorized
from .ml_context import load_zones
from .ml_dataset import schema_ready
from .ml_pricing import TYPES, VERSION, predict
from .ml_training import active_run, publish
from .models import MLDatasetSnapshot, MLPipelineState, MLTrainingRun
from .spatial_rules import assess_location


def _user(request):
    return getattr(request, 'current_user', None) or getattr(request, 'user', None)


def _admin(request):
    user = _user(request)
    return bool(authorized(request) and (getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False)))


@require_GET
@ensure_csrf_cookie
def dashboard(request):
    if not authorized(request):
        return JsonResponse({'error': 'Inicia sesión.'}, status=401)
    ready = schema_ready()
    dataset = MLDatasetSnapshot.objects.order_by('-pk').first() if ready else None
    runs = list(MLTrainingRun.objects.select_related('dataset').order_by('-pk')[:30]) if ready else []
    active = {kind: active_run(kind) for kind in TYPES} if ready else {}
    monitoring = {}
    if ready:
        for kind in TYPES:
            state = MLPipelineState.objects.filter(pk='model-monitor:' + kind).first()
            monitoring[kind] = list((state.payload or {}).get('history') or [])[-10:][::-1] if state else []
    cards = [{'kind': kind, 'run': active.get(kind), 'monitoring': monitoring.get(kind, [])}
             for kind in TYPES]
    response = render(request, 'ingestas/ml_models.html', {
        'ready': ready, 'dataset': dataset, 'runs': runs, 'cards': cards,
        'can_manage': _admin(request)})
    response['Cache-Control'] = 'private, no-store'
    return response


@require_POST
@csrf_protect
def queue_training(request):
    if not _admin(request):
        return JsonResponse({'error': 'Solo un administrador puede solicitar entrenamiento.'}, status=403)
    if not schema_ready():
        return JsonResponse({'error': 'Migración de conjuntos pendiente.'}, status=503)
    kind = request.POST.get('property_type')
    if kind not in TYPES:
        return JsonResponse({'error': 'Tipo de propiedad inválido.'}, status=400)
    dataset = MLDatasetSnapshot.objects.order_by('-pk').first()
    if not dataset or not dataset.included:
        return JsonResponse({'error': 'Todavía no hay un conjunto congelado con ofertas aptas.'}, status=409)
    existing = MLTrainingRun.objects.filter(dataset=dataset, property_type=kind,
                                            status__in=['queued', 'running']).order_by('-pk').first()
    if not existing:
        MLTrainingRun.objects.create(dataset=dataset, property_type=kind, algorithm='pending',
                                     code_version=VERSION, status='queued')
    return redirect('acm:modelos_dashboard')


@require_POST
@csrf_protect
def publish_run(request, pk):
    if not _admin(request):
        return JsonResponse({'error': 'Solo un administrador puede publicar o restaurar un modelo.'}, status=403)
    run = get_object_or_404(MLTrainingRun, pk=pk)
    reason = (request.POST.get('reason') or 'Publicación manual desde el centro de modelos').strip()
    if len(reason) > 500:
        return JsonResponse({'error': 'Motivo demasiado largo.'}, status=400)
    try:
        user = _user(request)
        publish(run, str(getattr(user, 'username', '') or getattr(user, 'name', '') or user.pk), reason)
    except ValueError as error:
        return JsonResponse({'error': str(error)}, status=409)
    return redirect('acm:modelos_dashboard')


@require_POST
@csrf_protect
def estimate(request):
    if not authorized(request):
        return JsonResponse({'error': 'Inicia sesión.'}, status=401)
    try:
        data = json.loads(request.body or b'{}')
        kind = data.get('property_type')
        if kind not in TYPES:
            raise ValueError('Tipo de propiedad inválido.')
        def number(key, required=False):
            raw = data.get(key)
            if raw in (None, ''):
                if required:
                    raise ValueError('Falta ' + key + '.')
                return None
            value = float(raw)
            if not math.isfinite(value):
                raise ValueError(key + ' debe ser finito.')
            return value
        lat, lng = number('lat', True), number('lng', True)
        land, built, age = number('land'), number('built'), number('age')
        if not (-90 <= lat <= 90 and -180 <= lng <= 180) or \
                (kind in ('Casa', 'Terreno') and not (0 < (land or 0) <= 1000000)) or \
                (kind != 'Terreno' and not (0 < (built or 0) <= 1000000)) or \
                (age is not None and not 0 <= age <= 200):
            raise ValueError('Coordenadas, superficies o antigüedad fuera de rango.')
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        return JsonResponse({'error': str(error)}, status=400)
    run = active_run(kind) if schema_ready() else None
    if not run:
        return JsonResponse({'available': False, 'message': 'No hay un modelo publicado para este tipo.'})
    geo = assess_location({'latitud': lat, 'longitud': lng, 'precision_ubicacion': 'exacta'}, load_zones())
    if geo['status'] != 'exact_zone':
        return JsonResponse({'available': False, 'message': 'El punto no pertenece a una microzona exacta evaluable.'})
    target = {'features': {'area_terreno': land, 'area_construida': built, 'antiguedad_anios': age,
                           'latitud': lat, 'longitud': lng, 'zone_id': geo['selected_zone_id']}}
    value, evidence = predict(run.configuration['artifact'], target)
    if not math.isfinite(value) or value <= 0:
        return JsonResponse({'available': False, 'message': 'La estimación no es válida para este punto.'})
    results = [run.metrics.get('temporal') or {}, run.metrics.get('spatial') or {}]
    p80 = max((item.get('p80_error_pct', 0) for item in results if item.get('available')), default=None)
    spread = max(.1, min(.8, p80 / 100)) if p80 is not None else None
    return JsonResponse({'available': True, 'price_usd': round(value),
                         'range_usd': [round(value * (1-spread)), round(value * (1+spread))] if spread else None,
                         'run_id': run.pk, 'dataset_id': run.dataset_id,
                         'quality': run.metrics.get('reliability', 'exploratorio'),
                         'sample': run.eligible_count, 'algorithm': run.algorithm,
                         'evidence': evidence, 'target': 'precio anunciado de venta USD',
                         'warning': 'Estimación experimental de ofertas; la ubicación fue indicada por el usuario.'})
