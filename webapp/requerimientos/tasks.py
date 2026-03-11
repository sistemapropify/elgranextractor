"""
Tareas asíncronas para el análisis temporal de requerimientos.
"""
import time
from celery import shared_task
from django.core.cache import cache
from django.utils import timezone
from .analytics import (
    obtener_requerimientos_por_mes,
    obtener_distritos_por_mes,
    obtener_tipos_propiedad_por_mes,
    obtener_presupuesto_por_mes,
    obtener_caracteristicas_demandadas,
    calcular_crecimiento_porcentual,
    detectar_picos_y_valles,
    calcular_tendencia
)
import json
from datetime import datetime


@shared_task(bind=True)
def generar_analisis_temporal(self, filtros=None, fecha_inicio=None, fecha_fin=None):
    """
    Tarea asíncrona para generar análisis temporal.
    Actualiza el progreso en cache para que el frontend pueda monitorear.
    """
    task_id = self.request.id
    cache_key = f'analisis_task_{task_id}'
    
    # Paso 1: Inicializar progreso
    cache.set(cache_key, {
        'status': 'processing',
        'progress': 0,
        'message': 'Iniciando análisis...',
        'current_step': 'Preparando datos',
        'data': None
    }, timeout=300)
    
    total_steps = 6
    current_step = 0
    
    try:
        # Convertir fechas si existen
        if fecha_inicio and isinstance(fecha_inicio, str):
            fecha_inicio = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
        if fecha_fin and isinstance(fecha_fin, str):
            fecha_fin = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
        
        # Paso 2: Obtener requerimientos por mes
        current_step += 1
        cache.set(cache_key, {
            'status': 'processing',
            'progress': int((current_step / total_steps) * 100),
            'message': 'Calculando tendencia mensual...',
            'current_step': 'Tendencia mensual',
            'data': None
        }, timeout=300)
        
        datos_mes = list(obtener_requerimientos_por_mes(fecha_inicio, fecha_fin, filtros))
        
        # Paso 3: Distritos por mes
        current_step += 1
        cache.set(cache_key, {
            'status': 'processing',
            'progress': int((current_step / total_steps) * 100),
            'message': 'Analizando distritos...',
            'current_step': 'Análisis por distrito',
            'data': None
        }, timeout=300)
        
        distritos_mes = obtener_distritos_por_mes(fecha_inicio, fecha_fin)
        
        # Paso 4: Tipos de propiedad
        current_step += 1
        cache.set(cache_key, {
            'status': 'processing',
            'progress': int((current_step / total_steps) * 100),
            'message': 'Analizando tipos de propiedad...',
            'current_step': 'Tipos de propiedad',
            'data': None
        }, timeout=300)
        
        tipos_mes = obtener_tipos_propiedad_por_mes(fecha_inicio, fecha_fin)
        
        # Paso 5: Presupuesto
        current_step += 1
        cache.set(cache_key, {
            'status': 'processing',
            'progress': int((current_step / total_steps) * 100),
            'message': 'Calculando estadísticas de presupuesto...',
            'current_step': 'Análisis de presupuesto',
            'data': None
        }, timeout=300)
        
        presupuesto_mes = obtener_presupuesto_por_mes(fecha_inicio, fecha_fin)
        
        # Paso 6: Características
        current_step += 1
        cache.set(cache_key, {
            'status': 'processing',
            'progress': int((current_step / total_steps) * 100),
            'message': 'Analizando características demandadas...',
            'current_step': 'Características demandadas',
            'data': None
        }, timeout=300)
        
        caracteristicas_mes = obtener_caracteristicas_demandadas(fecha_inicio, fecha_fin)
        
        # Calcular métricas adicionales
        totales = [item['total'] for item in datos_mes]
        crecimiento = calcular_crecimiento_porcentual(totales)
        picos, valles = detectar_picos_y_valles(totales)
        tendencia = calcular_tendencia(totales)
        
        # Preparar datos finales
        result_data = {
            'success': True,
            'datos_mes': datos_mes,
            'distritos_mes': distritos_mes,
            'tipos_mes': tipos_mes,
            'presupuesto_mes': presupuesto_mes,
            'caracteristicas_mes': caracteristicas_mes,
            'metricas': {
                'totales': totales,
                'crecimiento': crecimiento,
                'picos': picos,
                'valles': valles,
                'tendencia': tendencia,
            }
        }
        
        # Paso final: Completado
        current_step += 1
        cache.set(cache_key, {
            'status': 'completed',
            'progress': 100,
            'message': 'Análisis completado exitosamente',
            'current_step': 'Finalizando',
            'data': result_data,
            'generated_at': timezone.now().isoformat()
        }, timeout=600)  # 10 minutos para recoger los datos
        
        return result_data
        
    except Exception as e:
        # Error handling
        cache.set(cache_key, {
            'status': 'failed',
            'progress': 0,
            'message': f'Error: {str(e)}',
            'current_step': 'Error',
            'data': None,
            'error': str(e)
        }, timeout=300)
        raise


@shared_task
def limpiar_cache_analisis():
    """Limpia las entradas de cache antiguas de análisis."""
    from django.core.cache import cache
    # Implementación básica - en producción usar un patrón más robusto
    pass


def obtener_progreso_tarea(task_id):
    """Obtiene el progreso de una tarea desde cache."""
    cache_key = f'analisis_task_{task_id}'
    return cache.get(cache_key, {
        'status': 'unknown',
        'progress': 0,
        'message': 'Tarea no encontrada',
        'current_step': 'Desconocido',
        'data': None
    })