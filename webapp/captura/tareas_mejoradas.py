"""
Tareas mejoradas de captura que utilizan el MejoradorCaptura para obtener
contenido completo de páginas web, especialmente contenido dinámico.
"""

import logging
import time
from typing import Dict, Any, Optional
from celery import shared_task
from django.utils import timezone
from django.db import transaction

from .models import CapturaCruda
from .mejorador_captura import capturar_contenido_mejorado
from .detector_tipos import DetectorTiposContenido
from .azure_storage import upload_raw_content
from semillas.models import FuenteWeb

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def capturar_contenido_mejorado_task(self, fuente_id: int, forzar_selenium: bool = False) -> Dict[str, Any]:
    """
    Tarea Celery para capturar contenido usando el MejoradorCaptura.
    
    Args:
        fuente_id: ID de la fuente a capturar
        forzar_selenium: Si es True, fuerza el uso de Selenium incluso si requests funciona
        
    Returns:
        Diccionario con resultados de la captura
    """
    try:
        fuente = FuenteWeb.objects.get(id=fuente_id, estado='activa')
    except FuenteWeb.DoesNotExist:
        logger.warning(f"Fuente {fuente_id} no encontrada o inactiva")
        return {'estado': 'error', 'mensaje': 'Fuente no encontrada'}
    
    logger.info(f"Capturando contenido mejorado para {fuente.nombre} ({fuente.url})")
    
    try:
        # Usar el mejorador de captura
        resultado_captura = capturar_contenido_mejorado(
            url=fuente.url,
            usar_selenium=True  # Siempre habilitar Selenium para mejor captura
        )
        
        if not resultado_captura['exito']:
            error_msg = resultado_captura.get('error', 'Error desconocido en captura')
            logger.error(f"Error en captura mejorada para {fuente.url}: {error_msg}")
            
            # Crear captura de error
            crear_captura_error(fuente, 0, error_msg)
            return {'estado': 'error', 'mensaje': error_msg}
        
        # Detectar tipo de contenido
        detector = DetectorTiposContenido()
        info_tipo = detector.detectar_tipo_completo(
            url=fuente.url,
            content_type=resultado_captura['metadatos'].get('content_type', ''),
            contenido=resultado_captura['contenido_html'].encode('utf-8') if resultado_captura['contenido_html'] else None,
            headers={}
        )
        
        # Crear captura cruda
        with transaction.atomic():
            captura = CapturaCruda(
                fuente=fuente,
                estado_http='exito',
                estado_procesamiento='pendiente',
                tipo_documento=info_tipo['tipo_documento'],
                status_code=200,
                content_type=resultado_captura['metadatos'].get('content_type', ''),
                content_length=len(resultado_captura['contenido_html'].encode('utf-8')) if resultado_captura['contenido_html'] else 0,
                encoding='utf-8',
                tiempo_respuesta_ms=int(resultado_captura.get('tiempo_total', 0) * 1000),
                contenido_html=resultado_captura['contenido_html'],
                metadata_tecnica={
                    'metodo_captura': resultado_captura['metodo_usado'],
                    'calidad_captura': resultado_captura.get('calidad_analisis', {}),
                    'url_final': resultado_captura['metadatos'].get('url_final', fuente.url),
                    'tipo_detectado': info_tipo,
                }
            )
            
            # Para captura en crudo: el contenido principal ES el HTML completo
            # Guardarlo en texto_extraido también para consistencia
            if resultado_captura.get('contenido_html'):
                captura.texto_extraido = resultado_captura['contenido_html']
                captura.estado_procesamiento = 'texto_extraido_ok'
            
            captura.save()
            
            # Subir a Azure Storage si está configurado
            from django.conf import settings
            if (settings.RAW_HTML_STORAGE == 'blob_storage' and
                resultado_captura['contenido_html']):
                try:
                    blob_info = upload_raw_content(
                        resultado_captura['contenido_html'],
                        fuente.id,
                        timestamp=captura.fecha_captura,
                        tipo_documento=captura.tipo_documento,
                        metadata={
                            'content_type': captura.content_type,
                            'tipo_documento': captura.tipo_documento,
                            'fuente_url': fuente.url,
                            'metodo_captura': resultado_captura['metodo_usado'],
                        }
                    )
                    if blob_info:
                        captura.azure_blob_url = blob_info['url']
                        captura.azure_blob_name = blob_info['nombre']
                        captura.save()
                except Exception as e:
                    logger.error(f"Error subiendo a Azure Storage: {e}")
        
        # Actualizar fuente
        fuente.fecha_ultima_revision = timezone.now()
        fuente.total_capturas += 1
        fuente.save(update_fields=['fecha_ultima_revision', 'total_capturas'])
        
        logger.info(f"Captura mejorada #{captura.id} creada para {fuente.nombre}")
        
        return {
            'estado': 'exito',
            'captura_id': captura.id,
            'metodo': resultado_captura['metodo_usado'],
            'tamaño_bytes': len(resultado_captura['contenido_html'].encode('utf-8')) if resultado_captura['contenido_html'] else 0,
            'tiempo_segundos': resultado_captura.get('tiempo_total', 0),
            'tiene_contenido_principal': bool(resultado_captura.get('contenido_principal')),
        }
        
    except Exception as e:
        logger.error(f"Error en captura mejorada para fuente {fuente_id}: {e}")
        
        # Intentar retry si es posible
        if self.request.retries < self.max_retries:
            logger.info(f"Reintentando captura para fuente {fuente_id} (intento {self.request.retries + 1})")
            raise self.retry(exc=e)
        else:
            # Crear captura de error después de todos los reintentos
            crear_captura_error(fuente, 0, str(e))
            return {'estado': 'error', 'mensaje': str(e)}


@shared_task
def reprocesar_capturas_incompletas(limite: int = 10) -> Dict[str, Any]:
    """
    Reprocesa capturas que pueden estar incompletas usando el mejorador de captura.
    
    Args:
        limite: Número máximo de capturas a reprocesar
        
    Returns:
        Diccionario con resultados del reprocesamiento
    """
    logger.info(f"Reprocesando hasta {limite} capturas incompletas")
    
    # Buscar capturas que puedan estar incompletas
    # Criterios: HTML pequeño, poco texto, o estado de error previo
    capturas_a_reprocesar = CapturaCruda.objects.filter(
        estado_http='exito',
        tipo_documento='html',
    ).order_by('tamaño_bytes')[:limite]
    
    resultados = {
        'total_capturas': len(capturas_a_reprocesar),
        'reprocesadas_exitosas': 0,
        'reprocesadas_fallidas': 0,
        'detalles': [],
    }
    
    for captura in capturas_a_reprocesar:
        try:
            logger.info(f"Reprocesando captura #{captura.id} de {captura.fuente.nombre}")
            
            # Usar el mejorador de captura
            resultado_captura = capturar_contenido_mejorado(
                url=captura.fuente.url,
                usar_selenium=True
            )
            
            if resultado_captura['exito'] and resultado_captura['contenido_html']:
                # Comparar con la captura original
                tamaño_original = captura.tamaño_bytes or 0
                tamaño_nuevo = len(resultado_captura['contenido_html'].encode('utf-8'))
                
                # Si la nueva captura es significativamente más grande, actualizar
                if tamaño_nuevo > tamaño_original * 1.2:  # 20% más grande
                    captura.contenido_html = resultado_captura['contenido_html']
                    captura.tamaño_bytes = tamaño_nuevo
                    
                    # Actualizar texto extraído si está disponible
                    if resultado_captura.get('contenido_principal'):
                        captura.texto_extraido = resultado_captura['contenido_principal']
                        captura.estado_procesamiento = 'texto_extraido_ok'
                    
                    # Actualizar metadatos
                    metadata = captura.metadata_tecnica or {}
                    metadata['reprocesado'] = True
                    metadata['reprocesado_fecha'] = timezone.now().isoformat()
                    metadata['reprocesado_metodo'] = resultado_captura['metodo_usado']
                    metadata['tamaño_original'] = tamaño_original
                    metadata['tamaño_nuevo'] = tamaño_nuevo
                    metadata['incremento_porcentaje'] = ((tamaño_nuevo - tamaño_original) / max(tamaño_original, 1)) * 100
                    
                    captura.metadata_tecnica = metadata
                    captura.save()
                    
                    resultados['reprocesadas_exitosas'] += 1
                    resultados['detalles'].append({
                        'captura_id': captura.id,
                        'fuente': captura.fuente.nombre,
                        'tamaño_original': tamaño_original,
                        'tamaño_nuevo': tamaño_nuevo,
                        'incremento_porcentaje': ((tamaño_nuevo - tamaño_original) / max(tamaño_original, 1)) * 100,
                        'metodo': resultado_captura['metodo_usado'],
                        'estado': 'mejorada',
                    })
                    
                    logger.info(f"Captura #{captura.id} mejorada: {tamaño_original} -> {tamaño_nuevo} bytes "
                               f"({((tamaño_nuevo - tamaño_original)/max(tamaño_original,1)*100):.1f}%)")
                else:
                    resultados['detalles'].append({
                        'captura_id': captura.id,
                        'fuente': captura.fuente.nombre,
                        'tamaño_original': tamaño_original,
                        'tamaño_nuevo': tamaño_nuevo,
                        'incremento_porcentaje': ((tamaño_nuevo - tamaño_original) / max(tamaño_original, 1)) * 100,
                        'metodo': resultado_captura['metodo_usado'],
                        'estado': 'sin_cambio_significativo',
                    })
            else:
                resultados['reprocesadas_fallidas'] += 1
                resultados['detalles'].append({
                    'captura_id': captura.id,
                    'fuente': captura.fuente.nombre,
                    'error': resultado_captura.get('error', 'Error desconocido'),
                    'estado': 'fallo',
                })
                
        except Exception as e:
            logger.error(f"Error reprocesando captura #{captura.id}: {e}")
            resultados['reprocesadas_fallidas'] += 1
            resultados['detalles'].append({
                'captura_id': captura.id,
                'fuente': captura.fuente.nombre,
                'error': str(e),
                'estado': 'error',
            })
    
    logger.info(f"Reprocesamiento completado: {resultados['reprocesadas_exitosas']} exitosas, "
               f"{resultados['reprocesadas_fallidas']} fallidas")
    
    return resultados


@shared_task
def evaluar_calidad_capturas(limite: int = 50) -> Dict[str, Any]:
    """
    Evalúa la calidad de las capturas existentes.
    
    Args:
        limite: Número máximo de capturas a evaluar
        
    Returns:
        Diccionario con resultados de la evaluación
    """
    logger.info(f"Evaluando calidad de hasta {limite} capturas")
    
    from .mejorador_captura import MejoradorCaptura
    
    mejorador = MejoradorCaptura(usar_selenium=False)
    
    # Obtener capturas recientes
    capturas = CapturaCruda.objects.filter(
        estado_http='exito',
        tipo_documento='html',
        contenido_html__isnull=False
    ).order_by('-fecha_captura')[:limite]
    
    resultados = {
        'total_evaluadas': len(capturas),
        'por_calidad': {
            'alta': 0,
            'media': 0,
            'baja': 0,
            'muy_baja': 0,
        },
        'detalles': [],
    }
    
    for captura in capturas:
        try:
            # Analizar calidad
            analisis_calidad = mejorador.analizar_calidad_captura(captura.contenido_html)
            
            calidad = analisis_calidad['calidad']
            resultados['por_calidad'][calidad] = resultados['por_calidad'].get(calidad, 0) + 1
            
            # Guardar análisis en metadatos si es baja calidad
            if calidad in ['baja', 'muy_baja']:
                metadata = captura.metadata_tecnica or {}
                metadata['analisis_calidad'] = analisis_calidad
                metadata['analisis_calidad_fecha'] = timezone.now().isoformat()
                captura.metadata_tecnica = metadata
                captura.save()
            
            resultados['detalles'].append({
                'captura_id': captura.id,
                'fuente': captura.fuente.nombre,
                'calidad': calidad,
                'razon': analisis_calidad['razon'],
                'palabras': analisis_calidad['metricas'].get('palabras', 0),
                'tamaño_bytes': captura.tamaño_bytes or 0,
            })
            
        except Exception as e:
            logger.error(f"Error evaluando calidad de captura #{captura.id}: {e}")
            resultados['detalles'].append({
                'captura_id': captura.id,
                'fuente': captura.fuente.nombre,
                'error': str(e),
                'calidad': 'error',
            })
    
    # Calcular porcentajes
    total = resultados['total_evaluadas']
    if total > 0:
        for calidad in resultados['por_calidad']:
            resultados['por_calidad'][f'{calidad}_porcentaje'] = (
                resultados['por_calidad'][calidad] / total * 100
            )
    
    logger.info(f"Evaluación de calidad completada: {resultados}")
    
    return resultados


@shared_task
def capturar_url_manual_mejorada(url: str, categoria: str = 'manual') -> Dict[str, Any]:
    """
    Captura una URL manualmente usando el mejorador de captura.
    
    Args:
        url: URL a capturar
        categoria: Categoría para la fuente temporal
        
    Returns:
        Diccionario con resultados de la captura
    """
    logger.info(f"Captura manual mejorada para URL: {url}")
    
    try:
        # Crear fuente temporal
        from django.utils.text import slugify
        import uuid
        
        nombre_fuente = f"Captura manual - {slugify(url[:50])} - {uuid.uuid4().hex[:8]}"
        
        fuente = FuenteWeb(
            nombre=nombre_fuente,
            url=url,
            tipo='documento_directo_html',
            categoria=categoria,
            estado='activa',
            prioridad=1,
            frecuencia_revision_horas=24 * 30,  # 30 días (solo para captura manual)
            es_semilla_activa=False,
        )
        fuente.save()
        
        # Usar la tarea de captura mejorada
        resultado = capturar_contenido_mejorado_task.delay(fuente.id, forzar_selenium=True)
        
        # Esperar resultado (timeout de 120 segundos)
        try:
            resultado_final = resultado.get(timeout=120)
        except Exception as e:
            logger.error(f"Timeout en captura manual para {url}: {e}")
            return {
                'estado': 'error',
                'mensaje': f'Timeout en captura: {str(e)}',
                'url': url,
            }
        
        # Combinar resultados
        resultado_final['fuente_temporal_id'] = fuente.id
        resultado_final['fuente_temporal_nombre'] = fuente.nombre
        resultado_final['url'] = url
        
        return resultado_final
        
    except Exception as e:
        logger.error(f"Error en captura manual mejorada para {url}: {e}")
        return {
            'estado': 'error',
            'mensaje': str(e),
            'url': url,
        }


def crear_captura_error(fuente: FuenteWeb, status_code: int, mensaje: str):
    """
    Crea una captura con estado de error.
    
    Args:
        fuente: Fuente web
        status_code: Código de estado HTTP
        mensaje: Mensaje de error
    """
    captura = CapturaCruda(
        fuente=fuente,
        estado_http='error',
        estado_procesamiento='error',
        status_code=status_code,
        mensaje_error=mensaje,
        metadata_tecnica={
            'error_timestamp': timezone.now().isoformat(),
            'error_mensaje': mensaje,
        }
    )
    captura.save()
    
    logger.info(f"Captura de error creada para {fuente.nombre}: {mensaje}")