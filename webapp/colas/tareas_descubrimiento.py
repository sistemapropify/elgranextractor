"""
Tareas Celery para el descubrimiento automático de URLs.

Este módulo contiene tareas para descubrir automáticamente
nuevas fuentes web de bienes raíces en Arequipa.
"""

import logging
from typing import Dict, Any
from celery import shared_task
from django.utils import timezone

from semillas.descubrimiento import DescubridorURLs
from semillas.models import FuenteWeb

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def ejecutar_descubrimiento_automatico(self) -> Dict[str, Any]:
    """
    Ejecuta el descubrimiento automático de nuevas fuentes web.
    
    Returns:
        Diccionario con resultados del descubrimiento
    """
    logger.info("Iniciando descubrimiento automático de fuentes")
    
    try:
        # Crear descubridor
        descubridor = DescubridorURLs(dominio_principal="arequipa")
        
        # Ejecutar descubrimiento completo
        resultados = descubridor.ejecutar_descubrimiento_completo()
        
        # Registrar en log
        if resultados['estado'] == 'completado':
            logger.info(
                f"Descubrimiento completado: "
                f"{resultados['urls_descubiertas']} URLs descubiertas, "
                f"{resultados['fuentes_creadas']} fuentes creadas"
            )
        else:
            logger.error(f"Descubrimiento falló: {resultados.get('error', 'Error desconocido')}")
        
        return resultados
        
    except Exception as e:
        logger.error(f"Error en descubrimiento automático: {str(e)}")
        
        # Reintentar si es posible
        try:
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            logger.error("Máximo de reintentos excedido para descubrimiento automático")
        
        return {
            'estado': 'error',
            'mensaje': str(e),
            'timestamp': timezone.now().isoformat(),
        }


@shared_task
def descubrir_fuentes_por_categoria(categoria: str, limite: int = 20) -> Dict[str, Any]:
    """
    Descubre fuentes específicas por categoría.
    
    Args:
        categoria: Categoría a buscar (casas, departamentos, terrenos, etc.)
        limite: Número máximo de fuentes a descubrir
        
    Returns:
        Diccionario con resultados del descubrimiento
    """
    logger.info(f"Descubriendo fuentes de categoría: {categoria}")
    
    try:
        descubridor = DescubridorURLs(dominio_principal="arequipa")
        
        # Construir consulta basada en categoría
        consultas_por_categoria = {
            'casas': ['casas venta arequipa', 'casa en venta arequipa'],
            'departamentos': ['departamentos alquiler arequipa', 'apartamentos arequipa'],
            'terrenos': ['terrenos venta arequipa', 'lotes arequipa'],
            'locales': ['locales comerciales arequipa', 'tiendas arequipa'],
            'oficinas': ['oficinas arequipa', 'espacios oficina arequipa'],
        }
        
        consultas = consultas_por_categoria.get(categoria, [f'{categoria} arequipa'])
        
        todas_urls = []
        for consulta in consultas:
            urls = descubridor.descubrir_urls_por_busqueda(consulta, limite=limite // len(consultas))
            todas_urls.extend(urls)
        
        # Filtrar URLs existentes
        urls_nuevas = descubridor.filtrar_urls_existentes(todas_urls)
        
        # Crear fuentes
        fuentes_creadas = []
        if urls_nuevas:
            fuentes_creadas = descubridor.crear_fuentes_desde_urls(urls_nuevas)
        
        logger.info(
            f"Descubrimiento por categoría '{categoria}': "
            f"{len(urls_nuevas)} URLs nuevas, "
            f"{len(fuentes_creadas)} fuentes creadas"
        )
        
        return {
            'estado': 'completado',
            'categoria': categoria,
            'urls_descubiertas': len(todas_urls),
            'urls_nuevas': len(urls_nuevas),
            'fuentes_creadas': len(fuentes_creadas),
            'timestamp': timezone.now().isoformat(),
        }
        
    except Exception as e:
        logger.error(f"Error descubriendo fuentes por categoría '{categoria}': {str(e)}")
        return {
            'estado': 'error',
            'categoria': categoria,
            'mensaje': str(e),
            'timestamp': timezone.now().isoformat(),
        }


@shared_task
def explorar_sitio_especifico(url_sitio: str, profundidad: int = 2) -> Dict[str, Any]:
    """
    Explora un sitio web específico para descubrir nuevas fuentes.
    
    Args:
        url_sitio: URL del sitio a explorar
        profundidad: Profundidad máxima de exploración
        
    Returns:
        Diccionario con resultados de la exploración
    """
    logger.info(f"Explorando sitio: {url_sitio} (profundidad: {profundidad})")
    
    try:
        descubridor = DescubridorURLs(dominio_principal="arequipa")
        
        # Explorar el sitio
        urls_descubiertas = descubridor.descubrir_urls_por_exploracion(
            url_sitio, profundidad=profundidad
        )
        
        # Filtrar URLs existentes
        urls_nuevas = descubridor.filtrar_urls_existentes(urls_descubiertas)
        
        # Crear fuentes
        fuentes_creadas = []
        if urls_nuevas:
            fuentes_creadas = descubridor.crear_fuentes_desde_urls(urls_nuevas)
        
        logger.info(
            f"Exploración de {url_sitio}: "
            f"{len(urls_descubiertas)} URLs descubiertas, "
            f"{len(urls_nuevas)} URLs nuevas, "
            f"{len(fuentes_creadas)} fuentes creadas"
        )
        
        return {
            'estado': 'completado',
            'url_sitio': url_sitio,
            'profundidad': profundidad,
            'urls_descubiertas': len(urls_descubiertas),
            'urls_nuevas': len(urls_nuevas),
            'fuentes_creadas': len(fuentes_creadas),
            'timestamp': timezone.now().isoformat(),
        }
        
    except Exception as e:
        logger.error(f"Error explorando sitio {url_sitio}: {str(e)}")
        return {
            'estado': 'error',
            'url_sitio': url_sitio,
            'mensaje': str(e),
            'timestamp': timezone.now().isoformat(),
        }


@shared_task
def analizar_sitemap(url_sitemap: str) -> Dict[str, Any]:
    """
    Analiza un sitemap XML para descubrir nuevas fuentes.
    
    Args:
        url_sitemap: URL del sitemap XML
        
    Returns:
        Diccionario con resultados del análisis
    """
    logger.info(f"Analizando sitemap: {url_sitemap}")
    
    try:
        descubridor = DescubridorURLs(dominio_principal="arequipa")
        
        # Analizar sitemap
        urls_descubiertas = descubridor.descubrir_urls_por_sitemap(url_sitemap)
        
        # Filtrar URLs existentes
        urls_nuevas = descubridor.filtrar_urls_existentes(urls_descubiertas)
        
        # Crear fuentes
        fuentes_creadas = []
        if urls_nuevas:
            fuentes_creadas = descubridor.crear_fuentes_desde_urls(urls_nuevas)
        
        logger.info(
            f"Análisis de sitemap {url_sitemap}: "
            f"{len(urls_descubiertas)} URLs descubiertas, "
            f"{len(urls_nuevas)} URLs nuevas, "
            f"{len(fuentes_creadas)} fuentes creadas"
        )
        
        return {
            'estado': 'completado',
            'url_sitemap': url_sitemap,
            'urls_descubiertas': len(urls_descubiertas),
            'urls_nuevas': len(urls_nuevas),
            'fuentes_creadas': len(fuentes_creadas),
            'timestamp': timezone.now().isoformat(),
        }
        
    except Exception as e:
        logger.error(f"Error analizando sitemap {url_sitemap}: {str(e)}")
        return {
            'estado': 'error',
            'url_sitemap': url_sitemap,
            'mensaje': str(e),
            'timestamp': timezone.now().isoformat(),
        }


@shared_task
def evaluar_fuentes_descubiertas() -> Dict[str, Any]:
    """
    Evalúa el rendimiento de las fuentes descubiertas automáticamente.
    
    Returns:
        Diccionario con estadísticas de evaluación
    """
    logger.info("Evaluando fuentes descubiertas automáticamente")
    
    try:
        # Obtener fuentes descubiertas automáticamente
        fuentes_descubiertas = FuenteWeb.objects.filter(
            descubierta_automaticamente=True
        )
        
        total_fuentes = fuentes_descubiertas.count()
        
        # Estadísticas por estado
        por_estado = fuentes_descubiertas.values('estado').annotate(
            count=Count('id')
        )
        
        # Estadísticas por categoría
        por_categoria = fuentes_descubiertas.values('categoria').annotate(
            count=Count('id')
        )
        
        # Calcular tasa de éxito
        fuentes_activas = fuentes_descubiertas.filter(estado='activa').count()
        tasa_exito = (fuentes_activas / max(total_fuentes, 1)) * 100
        
        # Fuentes con capturas exitosas recientes (últimos 7 días)
        from django.db.models import Count, Q
        from datetime import timedelta
        
        fecha_limite = timezone.now() - timedelta(days=7)
        fuentes_con_capturas = fuentes_descubiertas.filter(
            capturas__estado='exito',
            capturas__fecha_captura__gte=fecha_limite
        ).distinct().count()
        
        logger.info(
            f"Evaluación de fuentes descubiertas: "
            f"{total_fuentes} total, "
            f"{fuentes_activas} activas ({tasa_exito:.1f}%), "
            f"{fuentes_con_capturas} con capturas recientes"
        )
        
        return {
            'estado': 'completado',
            'total_fuentes': total_fuentes,
            'fuentes_activas': fuentes_activas,
            'tasa_exito': tasa_exito,
            'fuentes_con_capturas_recientes': fuentes_con_capturas,
            'estadisticas_por_estado': list(por_estado),
            'estadisticas_por_categoria': list(por_categoria),
            'timestamp': timezone.now().isoformat(),
        }
        
    except Exception as e:
        logger.error(f"Error evaluando fuentes descubiertas: {str(e)}")
        return {
            'estado': 'error',
            'mensaje': str(e),
            'timestamp': timezone.now().isoformat(),
        }


@shared_task
def optimizar_fuentes_descubiertas() -> Dict[str, Any]:
    """
    Optimiza las fuentes descubiertas automáticamente basado en su rendimiento.
    
    Returns:
        Diccionario con resultados de la optimización
    """
    logger.info("Optimizando fuentes descubiertas automáticamente")
    
    try:
        from datetime import timedelta
        
        fecha_limite = timezone.now() - timedelta(days=30)
        
        # Obtener fuentes descubiertas automáticamente con mal rendimiento
        fuentes_problema = FuenteWeb.objects.filter(
            descubierta_automaticamente=True,
            estado='error',
            ultimo_intento_captura__lt=fecha_limite
        )
        
        fuentes_desactivadas = 0
        fuentes_reiniciadas = 0
        
        for fuente in fuentes_problema:
            # Si tiene muchos errores y no ha tenido éxito en mucho tiempo, desactivar
            if fuente.contador_errores >= 10:
                fuente.activa = False
                fuente.save(update_fields=['activa'])
                fuentes_desactivadas += 1
                logger.debug(f"Fuente desactivada por muchos errores: {fuente.nombre}")
            
            # Si tiene algunos errores pero podría recuperarse, reiniciar
            elif fuente.contador_errores >= 3:
                fuente.estado = 'activa'
                fuente.contador_errores = 0
                fuente.frecuencia_revision_minutos = min(
                    fuente.frecuencia_revision_minutos * 2,
                    480  # Máximo 8 horas
                )
                fuente.save(update_fields=['estado', 'contador_errores', 'frecuencia_revision_minutos'])
                fuentes_reiniciadas += 1
                logger.debug(f"Fuente reiniciada: {fuente.nombre}")
        
        logger.info(
            f"Optimización completada: "
            f"{fuentes_desactivadas} fuentes desactivadas, "
            f"{fuentes_reiniciadas} fuentes reiniciadas"
        )
        
        return {
            'estado': 'completado',
            'fuentes_desactivadas': fuentes_desactivadas,
            'fuentes_reiniciadas': fuentes_reiniciadas,
            'timestamp': timezone.now().isoformat(),
        }
        
    except Exception as e:
        logger.error(f"Error optimizando fuentes descubiertas: {str(e)}")
        return {
            'estado': 'error',
            'mensaje': str(e),
            'timestamp': timezone.now().isoformat(),
        }