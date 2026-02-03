"""
Tareas Celery para el sistema de monitoreo web.

Este módulo contiene todas las tareas asíncronas para:
1. Captura de contenido web
2. Análisis de cambios
3. Notificaciones
4. Mantenimiento del sistema
"""

import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from celery import shared_task, group, chain
from django.utils import timezone
from django.db.models import Q, Count, Avg, Max, Min
from django.core.cache import cache

from semillas.models import FuenteWeb
from captura.models import CapturaCruda, EventoDeteccion
from captura.diff_engine import MotorDiferencias

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def revisar_fuente(self, fuente_id: int, forzar_captura: bool = False) -> Dict[str, Any]:
    """
    Revisa una fuente web específica y captura su contenido si es necesario.
    
    Args:
        fuente_id: ID de la fuente a revisar
        forzar_captura: Si True, captura incluso si no es el momento programado
        
    Returns:
        Diccionario con resultados de la revisión
    """
    try:
        fuente = FuenteWeb.objects.get(id=fuente_id, activa=True)
    except FuenteWeb.DoesNotExist:
        logger.warning(f"Fuente {fuente_id} no encontrada o inactiva")
        return {'estado': 'error', 'mensaje': 'Fuente no encontrada o inactiva'}
    
    # Verificar si es momento de capturar
    ahora = timezone.now()
    ultima_captura = fuente.ultima_captura_exitosa
    
    if not forzar_captura and ultima_captura:
        tiempo_desde_ultima = ahora - ultima_captura.fecha_captura
        frecuencia_minutos = fuente.frecuencia_revision_minutos
        
        if tiempo_desde_ultima.total_seconds() < frecuencia_minutos * 60:
            logger.debug(f"Fuente {fuente.nombre} aún no necesita revisión")
            return {
                'estado': 'omitido',
                'mensaje': f'Aún no es momento de revisar (frecuencia: {frecuencia_minutos} min)',
                'fuente_id': fuente_id,
                'fuente_nombre': fuente.nombre,
            }
    
    # Ejecutar captura
    resultado_captura = capturar_contenido.delay(fuente_id)
    
    return {
        'estado': 'en_proceso',
        'mensaje': 'Captura iniciada',
        'fuente_id': fuente_id,
        'fuente_nombre': fuente.nombre,
        'task_id': resultado_captura.id,
    }


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def capturar_contenido(self, fuente_id: int) -> Dict[str, Any]:
    """
    Captura el contenido de una fuente web.
    
    Args:
        fuente_id: ID de la fuente a capturar
        
    Returns:
        Diccionario con resultados de la captura
    """
    try:
        fuente = FuenteWeb.objects.get(id=fuente_id)
    except FuenteWeb.DoesNotExist:
        logger.error(f"Fuente {fuente_id} no encontrada para captura")
        return {'estado': 'error', 'mensaje': 'Fuente no encontrada'}
    
    logger.info(f"Iniciando captura de {fuente.nombre} ({fuente.url})")
    
    # Actualizar estadísticas de la fuente
    fuente.ultimo_intento_captura = timezone.now()
    fuente.save(update_fields=['ultimo_intento_captura'])
    
    try:
        # Importar aquí para evitar dependencias circulares
        import requests
        from bs4 import BeautifulSoup
        
        # Configurar headers para parecer navegador
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # Realizar la petición HTTP
        inicio = time.time()
        response = requests.get(
            fuente.url,
            headers=headers,
            timeout=30,
            allow_redirects=True
        )
        tiempo_respuesta_ms = int((time.time() - inicio) * 1000)
        
        # Verificar estado de la respuesta
        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}: {response.reason}")
        
        # Parsear el contenido
        soup = BeautifulSoup(response.content, 'html.parser')
        contenido_html = str(soup)
        
        # Extraer título si está disponible
        titulo = soup.title.string if soup.title else ''
        
        # Crear la captura
        captura = CapturaCruda(
            fuente=fuente,
            estado='exito',
            status_code=response.status_code,
            content_type=response.headers.get('Content-Type', ''),
            content_length=len(response.content),
            encoding=response.encoding or 'utf-8',
            contenido_html=contenido_html,
            tiempo_respuesta_ms=tiempo_respuesta_ms,
            tamaño_bytes=len(response.content.encode('utf-8')),
        )
        
        # Calcular estadísticas automáticamente (se ejecuta en save())
        captura.save()
        
        # Actualizar estadísticas de la fuente
        fuente.ultima_captura_exitosa = captura
        fuente.estado = 'activa'
        fuente.contador_exitos += 1
        fuente.tiempo_respuesta_promedio = (
            (fuente.tiempo_respuesta_promedio * (fuente.contador_exitos - 1) + tiempo_respuesta_ms) 
            / fuente.contador_exitos
        )
        fuente.save()
        
        logger.info(f"Captura exitosa de {fuente.nombre}: {len(contenido_html)} caracteres")
        
        # Programar análisis de cambios
        analizar_cambios.delay(captura.id)
        
        return {
            'estado': 'exito',
            'mensaje': 'Captura completada exitosamente',
            'fuente_id': fuente_id,
            'captura_id': captura.id,
            'tamaño_bytes': len(response.content),
            'tiempo_respuesta_ms': tiempo_respuesta_ms,
            'status_code': response.status_code,
        }
        
    except requests.exceptions.Timeout:
        logger.error(f"Timeout al capturar {fuente.nombre}")
        crear_captura_error(fuente, 'timeout', 'Timeout en la conexión')
        return {'estado': 'error', 'tipo': 'timeout', 'mensaje': 'Timeout en la conexión'}
        
    except requests.exceptions.ConnectionError:
        logger.error(f"Error de conexión al capturar {fuente.nombre}")
        crear_captura_error(fuente, 'error', 'Error de conexión')
        return {'estado': 'error', 'tipo': 'conexion', 'mensaje': 'Error de conexión'}
        
    except Exception as e:
        logger.error(f"Error al capturar {fuente.nombre}: {str(e)}")
        crear_captura_error(fuente, 'error', str(e))
        return {'estado': 'error', 'tipo': 'general', 'mensaje': str(e)}


def crear_captura_error(fuente: FuenteWeb, estado: str, mensaje_error: str):
    """Crea una captura con estado de error."""
    captura = CapturaCruda(
        fuente=fuente,
        estado=estado,
        mensaje_error=mensaje_error,
    )
    captura.save()
    
    # Actualizar estadísticas de la fuente
    fuente.contador_errores += 1
    
    # Si hay muchos errores consecutivos, desactivar temporalmente
    if fuente.contador_errores >= 5:
        fuente.estado = 'error'
        fuente.frecuencia_revision_minutos = min(
            fuente.frecuencia_revision_minutos * 2,  # Duplicar frecuencia
            1440  # Máximo 24 horas
        )
    
    fuente.save()


@shared_task(bind=True)
def analizar_cambios(self, captura_id: int) -> Dict[str, Any]:
    """
    Analiza cambios entre la captura actual y la anterior.
    
    Args:
        captura_id: ID de la captura nueva a analizar
        
    Returns:
        Diccionario con resultados del análisis
    """
    try:
        captura_nueva = CapturaCruda.objects.get(id=captura_id)
    except CapturaCruda.DoesNotExist:
        logger.error(f"Captura {captura_id} no encontrada para análisis")
        return {'estado': 'error', 'mensaje': 'Captura no encontrada'}
    
    # Obtener captura anterior
    captura_anterior = captura_nueva.obtener_captura_anterior()
    
    if not captura_anterior:
        logger.info(f"Primera captura de {captura_nueva.fuente.nombre}, sin cambios para analizar")
        return {
            'estado': 'omitido',
            'mensaje': 'Primera captura, sin cambios para analizar',
            'captura_id': captura_id,
        }
    
    # Usar el motor de diferencias
    motor = MotorDiferencias()
    resultado = motor.comparar_capturas(captura_anterior, captura_nueva)
    
    # Crear evento de detección si hay cambios significativos
    if resultado.similitud_porcentaje < 95:  # Umbral de 95% de similitud
        evento = motor.crear_evento_deteccion(resultado)
        
        # Notificar si el cambio es significativo
        if resultado.severidad in ['alto', 'critico']:
            notificar_cambio.delay(evento.id)
        
        logger.info(f"Cambio detectado en {captura_nueva.fuente.nombre}: "
                   f"{resultado.similitud_porcentaje:.1f}% similitud, "
                   f"severidad {resultado.severidad}")
        
        return {
            'estado': 'cambio_detectado',
            'mensaje': 'Cambio significativo detectado',
            'captura_id': captura_id,
            'evento_id': evento.id,
            'similitud_porcentaje': resultado.similitud_porcentaje,
            'tipo_cambio': resultado.tipo_cambio,
            'severidad': resultado.severidad,
        }
    else:
        logger.debug(f"Sin cambios significativos en {captura_nueva.fuente.nombre}: "
                    f"{resultado.similitud_porcentaje:.1f}% similitud")
        
        return {
            'estado': 'sin_cambios',
            'mensaje': 'Sin cambios significativos',
            'captura_id': captura_id,
            'similitud_porcentaje': resultado.similitud_porcentaje,
        }


@shared_task
def notificar_cambio(evento_id: int) -> Dict[str, Any]:
    """
    Notifica sobre un cambio detectado.
    
    Args:
        evento_id: ID del evento de detección
        
    Returns:
        Diccionario con resultados de la notificación
    """
    try:
        evento = EventoDeteccion.objects.get(id=evento_id)
    except EventoDeteccion.DoesNotExist:
        logger.error(f"Evento {evento_id} no encontrado para notificación")
        return {'estado': 'error', 'mensaje': 'Evento no encontrado'}
    
    # Aquí se implementaría la lógica de notificación
    # Por ahora solo registramos en el log
    logger.info(f"Notificación: Cambio {evento.severidad} en {evento.fuente.nombre}: "
               f"{evento.resumen_cambio}")
    
    # Marcar como notificado
    # evento.notificado = True
    # evento.save()
    
    return {
        'estado': 'notificado',
        'mensaje': 'Cambio notificado',
        'evento_id': evento_id,
        'fuente_nombre': evento.fuente.nombre,
        'severidad': evento.severidad,
    }


@shared_task
def revisar_fuentes_activas() -> Dict[str, Any]:
    """
    Revisa todas las fuentes activas y programa capturas según su frecuencia.
    
    Returns:
        Diccionario con resultados de la revisión
    """
    ahora = timezone.now()
    fuentes_activas = FuenteWeb.objects.filter(
        activa=True,
        estado='activa'
    ).select_related('ultima_captura_exitosa')
    
    tareas_programadas = 0
    fuentes_revisadas = 0
    
    for fuente in fuentes_activas:
        fuentes_revisadas += 1
        
        # Verificar si es momento de capturar
        if not fuente.ultima_captura_exitosa:
            # Primera captura
            revisar_fuente.delay(fuente.id)
            tareas_programadas += 1
            continue
        
        tiempo_desde_ultima = ahora - fuente.ultima_captura_exitosa.fecha_captura
        frecuencia_segundos = fuente.frecuencia_revision_minutos * 60
        
        if tiempo_desde_ultima.total_seconds() >= frecuencia_segundos:
            revisar_fuente.delay(fuente.id)
            tareas_programadas += 1
    
    logger.info(f"Revisión de fuentes: {fuentes_revisadas} revisadas, "
               f"{tareas_programadas} tareas programadas")
    
    return {
        'estado': 'completado',
        'mensaje': f'Revisión completada: {tareas_programadas} tareas programadas',
        'fuentes_revisadas': fuentes_revisadas,
        'tareas_programadas': tareas_programadas,
    }


@shared_task
def actualizar_frecuencias_automaticas() -> Dict[str, Any]:
    """
    Actualiza automáticamente las frecuencias de revisión basado en la tasa de cambios.
    
    Returns:
        Diccionario con resultados de la actualización
    """
    fuentes = FuenteWeb.objects.filter(activa=True)
    fuentes_actualizadas = 0
    
    for fuente in fuentes:
        # Obtener estadísticas de cambios recientes (últimos 7 días)
        fecha_limite = timezone.now() - timedelta(days=7)
        eventos_recientes = EventoDeteccion.objects.filter(
            fuente=fuente,
            fecha_deteccion__gte=fecha_limite,
            severidad__in=['alto', 'critico']
        ).count()
        
        # Calcular nueva frecuencia basada en tasa de cambios
        if eventos_recientes > 10:  # Muchos cambios -> revisar más frecuentemente
            nueva_frecuencia = max(5, fuente.frecuencia_revision_minutos // 2)
        elif eventos_recientes < 2:  # Pocos cambios -> revisar menos frecuentemente
            nueva_frecuencia = min(240, fuente.frecuencia_revision_minutos * 2)
        else:
            nueva_frecuencia = fuente.frecuencia_revision_minutos
        
        # Actualizar si hay cambio
        if nueva_frecuencia != fuente.frecuencia_revision_minutos:
            fuente.frecuencia_revision_minutos = nueva_frecuencia
            fuente.save(update_fields=['frecuencia_revision_minutos'])
            fuentes_actualizadas += 1
    
    logger.info(f"Frecuencias actualizadas: {fuentes_actualizadas} fuentes modificadas")
    
    return {
        'estado': 'completado',
        'mensaje': f'Frecuencias actualizadas: {fuentes_actualizadas} fuentes',
        'fuentes_actualizadas': fuentes_actualizadas,
    }


@shared_task
def limpiar_capturas_antiguas(dias_a_mantener: int = 30) -> Dict[str, Any]:
    """
    Elimina capturas antiguas para liberar espacio.
    
    Args:
        dias_a_mantener: Número de días de capturas a mantener
        
    Returns:
        Diccionario con resultados de la limpieza
    """
    fecha_limite = timezone.now() - timedelta(days=dias_a_mantener)
    
    # Contar antes de eliminar
    total_capturas = CapturaCruda.objects.count()
    capturas_a_eliminar = CapturaCruda.objects.filter(
        fecha_captura__lt=fecha_limite
    ).count()
    
    if capturas_a_eliminar == 0:
        return {
            'estado': 'sin_cambios',
            'mensaje': 'No hay capturas antiguas para eliminar',
            'total_capturas': total_capturas,
            'capturas_eliminadas': 0,
        }
    
    # Eliminar en lotes para evitar bloqueos
    batch_size = 1000
    capturas_eliminadas = 0
    
    while True:
        # Obtener un lote de capturas antiguas
        capturas_lote = CapturaCruda.objects.filter(
            fecha_captura__lt=fecha_limite
        )[:batch_size]
        
        if not capturas_lote:
            break
        
        # Eliminar el lote
        ids_a_eliminar = [c.id for c in capturas_lote]
        CapturaCruda.objects.filter(id__in=ids_a_eliminar).delete()
        capturas_eliminadas += len(capturas_lote)
        
        logger.debug(f"Eliminado lote de {len(capturas_lote)} capturas antiguas")
    
    logger.info(f"Limpieza completada: {capturas_eliminadas} capturas eliminadas")
    
    return {
        'estado': 'completado',
        'mensaje': f'Limpieza completada: {capturas_eliminadas} capturas eliminadas',
        'total_capturas': total_capturas,
        'capturas_eliminadas': capturas_eliminadas,
    }


@shared_task
def ejecutar_prueba_sistema() -> Dict[str, Any]:
    """
    Ejecuta una prueba completa del sistema para verificar que todo funciona.
    
    Returns:
        Diccionario con resultados de la prueba
    """
    resultados = {
        'estado': 'en_progreso',
        'pruebas': {},
        'timestamp': timezone.now().isoformat(),
    }
    
    # Prueba 1: Verificar modelos
    try:
        fuentes_count = FuenteWeb.objects.count()
        resultados['pruebas']['modelos'] = {
            'estado': 'exito',
            'mensaje': f'{fuentes_count} fuentes encontradas',
            'fuentes_count': fuentes_count,
        }
    except Exception as e:
        resultados['pruebas']['modelos'] = {
            'estado': 'error',
            'mensaje': str(e),
        }
    
    # Prueba 2: Verificar conexión a base de datos
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            resultados['pruebas']['base_datos'] = {
                'estado': 'exito',
                'mensaje': 'Conexión a base de datos exitosa',
            }
    except Exception as e:
        resultados['pruebas']['base_datos'] = {
            'estado': 'error',
            'mensaje': str(e),
        }
    
    # Prueba 3: Verificar tareas Celery
    try:
        from .celery import app
        inspeccion = app.control.inspect()
        trabajadores = inspeccion.active() if inspeccion else None
        
        if trabajadores:
            resultados['pruebas']['celery'] = {
                'estado': 'exito',
                'mensaje': 'Celery funcionando con trabajadores activos',
                'trabajadores': len(trabajadores),
            }
        else:
            resultados['pruebas']['celery'] = {
                'estado': 'advertencia',
                'mensaje': 'Celery configurado pero sin trabajadores activos',
            }
    except Exception as e:
        resultados['pruebas']['celery'] = {
            'estado': 'error',
            'mensaje': str(e),
        }
    
    # Determinar estado general
    estados = [prueba['estado'] for prueba in resultados['pruebas'].values()]
    
    if 'error' in estados:
        resultados['estado'] = 'error'
    elif 'advertencia' in estados:
        resultados['estado'] = 'advertencia'
    else:
        resultados['estado'] = 'exito'
    
    resultados['mensaje'] = f'Prueba completada: {len(resultados["pruebas"])} pruebas ejecutadas'
    
    return resultados


@shared_task
def reiniciar_fuente_error(fuente_id: int) -> Dict[str, Any]:
    """
    Reinicia una fuente que está en estado de error.
    
    Args:
        fuente_id: ID de la fuente a reiniciar
        
    Returns:
        Diccionario con resultados del reinicio
    """
    try:
        fuente = FuenteWeb.objects.get(id=fuente_id)
    except FuenteWeb.DoesNotExist:
        return {'estado': 'error', 'mensaje': 'Fuente no encontrada'}
    
    # Reiniciar contadores y estado
    fuente.estado = 'activa'
    fuente.contador_errores = 0
    fuente.frecuencia_revision_minutos = max(30, fuente.frecuencia_revision_minutos // 2)
    fuente.save()
    
    logger.info(f"Fuente {fuente.nombre} reiniciada desde estado de error")
    
    # Programar nueva captura
    revisar_fuente.delay(fuente_id, forzar_captura=True)
    
    return {
        'estado': 'exito',
        'mensaje': f'Fuente {fuente.nombre} reiniciada exitosamente',
        'fuente_id': fuente_id,
        'fuente_nombre': fuente.nombre,
    }


@shared_task
def generar_reporte_estadisticas(dias: int = 7) -> Dict[str, Any]:
    """
    Genera un reporte estadístico del sistema.
    
    Args:
        dias: Número de días a incluir en el reporte
        
    Returns:
        Diccionario con estadísticas del sistema
    """
    fecha_inicio = timezone.now() - timedelta(days=dias)
    
    # Estadísticas de fuentes
    fuentes_totales = FuenteWeb.objects.count()
    fuentes_activas = FuenteWeb.objects.filter(activa=True).count()
    fuentes_error = FuenteWeb.objects.filter(estado='error').count()
    
    # Estadísticas de capturas
    capturas_totales = CapturaCruda.objects.filter(
        fecha_captura__gte=fecha_inicio
    ).count()
    
    capturas_exitosas = CapturaCruda.objects.filter(
        fecha_captura__gte=fecha_inicio,
        estado='exito'
    ).count()
    
    capturas_error = CapturaCruda.objects.filter(
        fecha_captura__gte=fecha_inicio,
        estado='error'
    ).count()
    
    # Estadísticas de cambios
    cambios_totales = EventoDeteccion.objects.filter(
        fecha_deteccion__gte=fecha_inicio
    ).count()
    
    cambios_significativos = EventoDeteccion.objects.filter(
        fecha_deteccion__gte=fecha_inicio,
        severidad__in=['alto', 'critico']
    ).count()
    
    # Tasa de éxito
    tasa_exito = (capturas_exitosas / max(capturas_totales, 1)) * 100
    
    # Tamaño total de capturas (aproximado)
    tamaño_promedio = CapturaCruda.objects.filter(
        fecha_captura__gte=fecha_inicio
    ).aggregate(Avg('tamaño_bytes'))['tamaño_bytes__avg'] or 0
    
    tamaño_total = tamaño_promedio * capturas_totales
    
    reporte = {
        'estado': 'completado',
        'periodo_dias': dias,
        'fecha_inicio': fecha_inicio.isoformat(),
        'fecha_fin': timezone.now().isoformat(),
        'estadisticas': {
            'fuentes': {
                'totales': fuentes_totales,
                'activas': fuentes_activas,
                'en_error': fuentes_error,
                'porcentaje_activas': (fuentes_activas / max(fuentes_totales, 1)) * 100,
            },
            'capturas': {
                'totales': capturas_totales,
                'exitosas': capturas_exitosas,
                'errores': capturas_error,
                'tasa_exito': tasa_exito,
            },
            'cambios': {
                'totales': cambios_totales,
                'significativos': cambios_significativos,
                'porcentaje_significativos': (cambios_significativos / max(cambios_totales, 1)) * 100,
            },
            'almacenamiento': {
                'tamaño_promedio_kb': tamaño_promedio / 1024,
                'tamaño_total_mb': tamaño_total / (1024 * 1024),
                'capturas_por_dia': capturas_totales / dias,
            },
        },
        'recomendaciones': [],
    }
    
    # Generar recomendaciones basadas en estadísticas
    if tasa_exito < 80:
        reporte['recomendaciones'].append(
            'La tasa de éxito de capturas es baja. Considera revisar las fuentes con errores.'
        )
    
    if fuentes_error > fuentes_totales * 0.3:
        reporte['recomendaciones'].append(
            'Más del 30% de las fuentes están en error. Considera reiniciarlas.'
        )
    
    if cambios_significativos > 0:
        reporte['recomendaciones'].append(
            f'Se detectaron {cambios_significativos} cambios significativos en el período.'
        )
    
    logger.info(f"Reporte generado para {dias} días: {capturas_totales} capturas, "
               f"{cambios_totales} cambios, {tasa_exito:.1f}% éxito")
    
    return reporte