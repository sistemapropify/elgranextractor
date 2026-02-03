from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count, Sum, Q
import json

from semillas.models import FuenteWeb
from captura.models import CapturaCruda, EventoDeteccion
from colas.tasks import revisar_fuentes_activas, actualizar_frecuencias_automaticas
from colas.tareas_descubrimiento import ejecutar_descubrimiento_automatico


def home(request):
    """Vista principal del dashboard"""
    # Obtener estadísticas básicas
    total_fuentes = FuenteWeb.objects.filter(estado='activa').count()
    total_capturas = CapturaCruda.objects.count()
    cambios_detectados = EventoDeteccion.objects.count()
    
    # Obtener fuentes activas recientes
    fuentes_activas = FuenteWeb.objects.filter(estado='activa').order_by('-fecha_ultima_revision')[:10]
    
    # Obtener cambios recientes
    cambios_recientes = EventoDeteccion.objects.select_related('captura', 'captura__fuente').order_by('-fecha_deteccion')[:5]
    
    context = {
        'total_fuentes': total_fuentes,
        'total_capturas': total_capturas,
        'cambios_detectados': cambios_detectados,
        'fuentes_activas': fuentes_activas,
        'cambios_recientes': cambios_recientes,
    }
    
    return render(request, 'index.html', context)


def fuentes_web(request):
    """Vista para la gestión de fuentes web"""
    # Obtener estadísticas por categoría
    categorias_data = []
    
    # Verificar si el modelo tiene CATEGORIA_CHOICES
    if hasattr(FuenteWeb, 'CATEGORIA_CHOICES'):
        for cat in FuenteWeb.CATEGORIA_CHOICES:
            categoria_val = cat[0]
            total = FuenteWeb.objects.filter(categoria=categoria_val).count()
            activas = FuenteWeb.objects.filter(categoria=categoria_val, estado='activa').count()
            capturas = FuenteWeb.objects.filter(categoria=categoria_val).aggregate(
                total_capturas=Sum('total_capturas')
            )['total_capturas'] or 0
            
            categorias_data.append({
                'categoria': categoria_val,
                'total': total,
                'activas': activas,
                'capturas': capturas
            })
    else:
        # Si no hay CATEGORIA_CHOICES, usar valores por defecto
        categorias_default = ['oferta', 'legal', 'infraestructura', 'inteligencia', 'riesgo', 'actores']
        for cat in categorias_default:
            total = FuenteWeb.objects.filter(categoria=cat).count()
            categorias_data.append({
                'categoria': cat,
                'total': total,
                'activas': 0,
                'capturas': 0
            })
    
    # Obtener todas las fuentes para la tabla
    fuentes = FuenteWeb.objects.all().order_by('-fecha_creacion')[:50]
    
    # Preparar datos para JavaScript
    fuentes_json = []
    for fuente in fuentes:
        fuentes_json.append({
            'id': fuente.id,
            'nombre': fuente.nombre,
            'url': fuente.url,
            'categoria': fuente.categoria if hasattr(fuente, 'categoria') else 'oferta',
            'estado': fuente.estado,
            'prioridad': fuente.prioridad,
            'frecuencia_revision_horas': fuente.frecuencia_revision_horas,
            'fecha_ultima_revision': fuente.fecha_ultima_revision.isoformat() if fuente.fecha_ultima_revision else None,
            'total_capturas': fuente.total_capturas or 0,
            'total_cambios_detectados': fuente.total_cambios_detectados or 0,
            'tasa_cambio_porcentaje': fuente.tasa_cambio_porcentaje or 0,
            'tipo': fuente.tipo or 'sitio_web',
            'descripcion': fuente.descripcion or '',
            'respetar_robots_txt': fuente.respetar_robots_txt,
            'delay_entre_requests': fuente.delay_entre_requests or 2,
            'fecha_creacion': fuente.fecha_creacion.isoformat() if fuente.fecha_creacion else None,
            'fecha_proxima_revision': fuente.fecha_proxima_revision.isoformat() if fuente.fecha_proxima_revision else None
        })
    
    context = {
        'categorias': categorias_data,
        'total_fuentes': FuenteWeb.objects.count(),
        'fuentes_activas': FuenteWeb.objects.filter(estado='activa').count(),
        'fuentes': fuentes,
        'fuentes_json': json.dumps(fuentes_json),  # Datos serializados para JavaScript
    }
    
    return render(request, 'fuentes_web.html', context)


@csrf_exempt
def agregar_fuente_api(request):
    """API para agregar nueva fuente desde el dashboard"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            url = data.get('url', '').strip()
            frecuencia = data.get('frecuencia', 60)
            categoria = data.get('categoria', 'venta')
            prioridad_str = data.get('prioridad', 'media')
            
            if not url:
                return JsonResponse({'error': 'URL es requerida'}, status=400)
            
            # Convertir prioridad de string a número
            prioridad_map = {'alta': 3, 'media': 2, 'baja': 1}
            prioridad = prioridad_map.get(prioridad_str.lower(), 2)
            
            # Crear nueva fuente con campos correctos
            fuente = FuenteWeb.objects.create(
                url=url,
                nombre=url[:100],  # Nombre temporal
                estado='activa',
                prioridad=prioridad,
                frecuencia_revision_horas=frecuencia / 60,  # Convertir minutos a horas
                tipo=categoria,
                descripcion=f'Fuente agregada manualmente desde dashboard'
            )
            
            return JsonResponse({
                'success': True,
                'message': f'Fuente agregada: {url}',
                'fuente_id': fuente.id
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Método no permitido'}, status=405)


@csrf_exempt
def ejecutar_sistema_api(request):
    """API para ejecutar el sistema manualmente"""
    if request.method == 'POST':
        try:
            # Ejecutar tarea de revisión de fuentes activas
            task = revisar_fuentes_activas.delay()
            
            return JsonResponse({
                'success': True,
                'message': 'Sistema ejecutado. Revisando todas las fuentes activas.',
                'task_id': task.id
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Método no permitido'}, status=405)


@csrf_exempt
def descubrir_urls_api(request):
    """API para descubrir nuevas URLs"""
    if request.method == 'POST':
        try:
            # Ejecutar tarea de descubrimiento
            task = ejecutar_descubrimiento_automatico.delay()
            
            return JsonResponse({
                'success': True,
                'message': 'Buscando nuevos portales inmobiliarios en Arequipa...',
                'task_id': task.id
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Método no permitido'}, status=405)


@csrf_exempt
def actualizar_frecuencias_api(request):
    """API para actualizar frecuencias automáticamente"""
    if request.method == 'POST':
        try:
            # Ejecutar tarea de actualización de frecuencias
            task = actualizar_frecuencias_automaticas.delay()
            
            return JsonResponse({
                'success': True,
                'message': 'Actualizando frecuencias basadas en tasa de cambios...',
                'task_id': task.id
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Método no permitido'}, status=405)


def estadisticas_api(request):
    """API para obtener estadísticas en formato JSON"""
    total_fuentes = FuenteWeb.objects.filter(estado='activa').count()
    total_capturas = CapturaCruda.objects.count()
    cambios_detectados = EventoDeteccion.objects.count()
    
    # Contar URLs descubiertas (fuentes con estado 'descubierta')
    urls_descubiertas = FuenteWeb.objects.filter(estado='descubierta').count()
    
    return JsonResponse({
        'total_fuentes': total_fuentes,
        'total_capturas': total_capturas,
        'cambios_detectados': cambios_detectados,
        'urls_descubiertas': urls_descubiertas,
    })


def fuentes_api(request):
    """API para obtener lista de fuentes activas"""
    # Obtener todas las fuentes, no solo activas
    fuentes = FuenteWeb.objects.all().order_by('-fecha_creacion')[:50]
    
    fuentes_data = []
    for fuente in fuentes:
        # Determinar categoría (usar campo categoria si existe, sino 'oferta')
        categoria = getattr(fuente, 'categoria', 'oferta')
        
        fuentes_data.append({
            'id': fuente.id,
            'nombre': fuente.nombre or fuente.url,
            'url': fuente.url,
            'estado': fuente.estado,
            'categoria': categoria,
            'prioridad': fuente.prioridad,
            'frecuencia': fuente.frecuencia_revision_horas or 24,
            'ultima_captura': fuente.fecha_ultima_revision.strftime('%Y-%m-%d %H:%M') if fuente.fecha_ultima_revision else 'Nunca',
            'total_capturas': fuente.total_capturas or 0,
            'total_cambios_detectados': fuente.total_cambios_detectados or 0,
            'tasa_cambio_porcentaje': fuente.tasa_cambio_porcentaje or 0,
            'tipo': fuente.tipo or 'sitio_web',
            'descripcion': fuente.descripcion or '',
            'respetar_robots_txt': fuente.respetar_robots_txt,
            'delay_entre_requests': fuente.delay_entre_requests or 2,
            'fecha_creacion': fuente.fecha_creacion.strftime('%Y-%m-%d %H:%M') if fuente.fecha_creacion else '',
            'fecha_proxima_revision': fuente.fecha_proxima_revision.strftime('%Y-%m-%d %H:%M') if fuente.fecha_proxima_revision else ''
        })
    
    return JsonResponse(fuentes_data, safe=False)
