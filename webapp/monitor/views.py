"""Dashboard de monitoreo del negocio (Propify), en solo lectura."""
from __future__ import annotations

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render

from . import metrics
from .db import disponible

DIAS_SERIE = 60
MESES_SERIE = 12
TOP_ESTADOS = 8
TOP_RECIENTES = 15


def _usuario_ok(request) -> bool:
    user = getattr(request, 'current_user', None) or getattr(request, 'user', None)
    return bool(user and getattr(user, 'is_authenticated', False)
                and getattr(user, 'is_active', False))


def _entero(request, nombre):
    """Lee un id de la URL. Devuelve None si viene vacio o no es un numero."""
    valor = (request.GET.get(nombre) or '').strip()
    return int(valor) if valor.isdigit() else None


def _ambito(request):
    """(area_id, rol_id) pedidos en la URL. area puede venir como 'sin'."""
    area = (request.GET.get('area') or '').strip()
    if area == metrics.SIN_AREA:
        return metrics.SIN_AREA, None
    return (int(area) if area.isdigit() else None), _entero(request, 'rol')


def dashboard(request):
    if not _usuario_ok(request):
        return HttpResponse('Inicia sesión para ver el monitoreo.', status=401)

    area_id, rol_id = _ambito(request)
    ok, detalle = disponible()
    contexto = {'disponible': ok, 'detalle': detalle, 'area_id': area_id, 'rol_id': rol_id}

    if ok:
        por_dia = metrics.registros_por_dia(DIAS_SERIE, area_id, rol_id)
        areas = metrics.areas()
        roles = metrics.roles_de(area_id) if isinstance(area_id, int) else []
        contexto.update({
            'resumen': metrics.resumen_usuarios(area_id, rol_id),
            'pulso': metrics.pulso(area_id, rol_id),
            'por_dia': por_dia,
            'eje': metrics.eje_de_dias(por_dia),
            'max_dia': max((d['total'] for d in por_dia), default=0),
            'por_mes': metrics.registros_por_mes(MESES_SERIE, area_id, rol_id),
            'estados': metrics.por_estado(area_id, rol_id)[:TOP_ESTADOS],
            'ultimos': metrics.ultimos_registros(TOP_RECIENTES, area_id, rol_id),
            'areas': areas,
            'roles': roles,
            'sin_rol': metrics.sin_rol(),
            'area_activa': next((a for a in areas if a['id'] == area_id), None)
                           or ({'id': metrics.SIN_AREA, 'nombre': 'Sin rol', 'usuarios': metrics.sin_rol()}
                               if area_id == metrics.SIN_AREA else None),
            'rol_activo': next((r for r in roles if r['id'] == rol_id), None),
        })
    return render(request, 'monitor/dashboard.html', contexto)


def usuarios_api(request):
    """Lista de usuarios de una etapa del embudo, ya acotada al area/rol activos."""
    if not _usuario_ok(request):
        return JsonResponse({'error': 'Inicia sesión.'}, status=401)
    grupo = request.GET.get('grupo', 'registrados')
    area_id, rol_id = _ambito(request)
    try:
        usuarios = metrics.usuarios_de(grupo, area_id=area_id, rol_id=rol_id)
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    return JsonResponse({'grupo': grupo, 'total': len(usuarios), 'usuarios': usuarios})
