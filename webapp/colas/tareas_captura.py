"""
Tareas Celery para captura y procesamiento de contenido crudo.
Implementa el flujo unificado de captura según tipo de fuente.
"""

import time
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from celery import shared_task
from django.utils import timezone
from django.db import transaction

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

from semillas.models import FuenteWeb
from captura.models import CapturaCruda
from captura.detector_tipos import DetectorTiposContenido
from captura.extractor_pdf import ExtractorPDF
from captura.azure_storage import upload_raw_content, upload_pdf_binario, AzureStorageError

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay= 60)
def procesar_fuente_completa(self, fuente_id: int) -> Dict[str, Any]:
    """
    Procesa una fuente completamente según su tipo.
    
    Flujo:
    1. Identificar tipo de fuente
    2. Descargar contenido
    3. Guardar en RAW
    4. Procesar según tipo:
       - SEMILLA_LISTADO: Extraer links → crear fuentes hijo
       - DOCUMENTO_DIRECTO_HTML: Extraer texto limpio
       - DOCUMENTO_DIRECTO_PDF: Extraer texto (nativo) o marcar para OCR
    
    Args:
        fuente_id: ID de la fuente a procesar
        
    Returns:
        Resultado del procesamiento
    """
    try:
        fuente = FuenteWeb.objects.get(id=fuente_id, estado='activa')
    except FuenteWeb.DoesNotExist:
        logger.warning(f"Fuente {fuente_id} no encontrada o inactiva")
        return {'estado': 'error', 'mensaje': 'Fuente no encontrada'}
    
    logger.info(f"Procesando fuente {fuente.nombre} ({fuente.tipo})")
    
    try:
        # Paso 1: Descargar contenido
        resultado_descarga = descargar_contenido.delay(fuente_id)
        captura_id = resultado_descarga.get(timeout=120)
        
        if not captura_id:
            return {'estado': 'error', 'mensaje': 'Error en descarga'}
        
        # Paso 2: Procesar según tipo
        if fuente.tipo == 'semilla_listado':
            resultado_procesamiento = procesar_semilla_listado.delay(captura_id)
        elif fuente.tipo == 'documento_directo_html':
            resultado_procesamiento = procesar_documento_html.delay(captura_id)
        elif fuente.tipo == 'documento_directo_pdf':
            resultado_procesamiento = procesar_documento_pdf.delay(captura_id)
        else:
            logger.warning(f"Tipo de fuente no soportado: {fuente.tipo}")
            return {'estado': 'error', 'mensaje': f'Tipo no soportado: {fuente.tipo}'}
        
        return {
            'estado': 'procesando',
            'fuente_id': fuente_id,
            'captura_id': captura_id,
            'task_procesamiento_id': resultado_procesamiento.id,
        }
        
    except Exception as e:
        logger.error(f"Error procesando fuente {fuente_id}: {e}")
        return {'estado': 'error', 'mensaje': str(e)}


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def descargar_contenido(self, fuente_id: int) -> Optional[int]:
    """
    Descarga contenido de una URL y lo guarda en CapturaCruda.
    
    Args:
        fuente_id: ID de la fuente a descargar
        
    Returns:
        ID de la captura creada o None si hubo error
    """
    try:
        fuente = FuenteWeb.objects.get(id=fuente_id)
    except FuenteWeb.DoesNotExist:
        logger.error(f"Fuente {fuente_id} no encontrada")
        return None
    
    logger.info(f"Descargando {fuente.url}")
    
    # Configurar headers
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
    }
    
    try:
        # Realizar descarga
        inicio = time.time()
        response = requests.get(
            fuente.url,
            headers=headers,
            timeout=30,
            allow_redirects=True,
            stream=True  # Para descargas grandes
        )
        tiempo_respuesta_ms = int((time.time() - inicio) * 1000)
        
        # Verificar respuesta
        if response.status_code != 200:
            logger.error(f"HTTP {response.status_code} para {fuente.url}")
            crear_captura_error(fuente, response.status_code, f"HTTP {response.status_code}")
            return None
        
        # Obtener content-type
        content_type = response.headers.get('Content-Type', '')
        
        # Detector de tipos
        detector = DetectorTiposContenido()
        
        # Descargar contenido completo
        contenido_bytes = response.content
        
        # Detectar tipo de documento
        info_tipo = detector.detectar_tipo_completo(
            url=fuente.url,
            content_type=content_type,
            contenido=contenido_bytes,
            headers=dict(response.headers)
        )
        
        logger.info(f"Tipo detectado: {info_tipo['tipo_documento']} - {info_tipo['tipo_fuente']}")
        
        # Crear captura según tipo
        captura = CapturaCruda(
            fuente=fuente,
            estado_http='exito',
            estado_procesamiento='pendiente',
            tipo_documento=info_tipo['tipo_documento'],
            status_code=response.status_code,
            content_type=content_type,
            content_length=len(contenido_bytes),
            encoding=response.encoding or 'utf-8',
            tiempo_respuesta_ms=tiempo_respuesta_ms,
            metadata_tecnica={
                'headers': dict(response.headers),
                'url_final': response.url,
                'tipo_detectado': info_tipo,
            }
        )
        
        # Guardar contenido según tipo
        if info_tipo['tipo_documento'] == 'html':
            # HTML: guardar como texto
            try:
                contenido_texto = contenido_bytes.decode(response.encoding or 'utf-8')
            except UnicodeDecodeError:
                contenido_texto = contenido_bytes.decode('latin-1', errors='ignore')
            
            captura.contenido_html = contenido_texto
            captura.save()
            
        elif info_tipo['tipo_documento'] in ['pdf_nativo', 'pdf_escaneado']:
            # PDF: subir binario a Azure y guardar referencia
            try:
                blob_info = upload_pdf_binario(
                    contenido_bytes,
                    fuente.id,
                    metadata={'url': fuente.url}
                )
                captura.contenido_binario_blob = blob_info['nombre']
                captura.azure_blob_url = blob_info['url']
                captura.azure_blob_name = blob_info['nombre']
            except Exception as e:
                logger.error(f"Error subiendo PDF a Azure: {e}")
                # Continuar sin Azure
            
            captura.save()
            
        else:
            # Otros: guardar como texto
            try:
                contenido_texto = contenido_bytes.decode('utf-8')
            except UnicodeDecodeError:
                contenido_texto = str(contenido_bytes)
            
            captura.contenido_html = contenido_texto
            captura.save()
        
        # Actualizar fuente
        fuente.fecha_ultima_revision = timezone.now()
        fuente.total_capturas += 1
        fuente.save(update_fields=['fecha_ultima_revision', 'total_capturas'])
        
        logger.info(f"Captura #{captura.id} creada para {fuente.nombre}")
        return captura.id
        
    except requests.exceptions.Timeout:
        logger.error(f"Timeout descargando {fuente.url}")
        crear_captura_error(fuente, 0, 'Timeout')
        return None
        
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Error de conexión: {e}")
        crear_captura_error(fuente, 0, f'Error de conexión: {str(e)}')
        return None
        
    except Exception as e:
        logger.error(f"Error descargando {fuente.url}: {e}")
        crear_captura_error(fuente, 0, str(e))
        return None


@shared_task
def procesar_semilla_listado(captura_id: int) -> Dict[str, Any]:
    """
    Procesa una semilla listado: extrae links y crea fuentes hijo.
    
    Args:
        captura_id: ID de la captura a procesar
        
    Returns:
        Resultado del procesamiento
    """
    try:
        captura = CapturaCruda.objects.get(id=captura_id)
    except CapturaCruda.DoesNotExist:
        logger.error(f"Captura {captura_id} no encontrada")
        return {'estado': 'error', 'mensaje': 'Captura no encontrada'}
    
    logger.info(f"Procesando semilla listado: {captura.fuente.nombre}")
    
    captura.estado_procesamiento = 'procesando'
    captura.save()
    
    try:
        if not captura.contenido_html:
            raise ValueError("No hay contenido HTML para procesar")
        
        # Parsear HTML
        soup = BeautifulSoup(captura.contenido_html, 'html.parser')
        
        # Extraer todos los links internos
        links_encontrados = []
        base_url = captura.fuente.url
        dominio_base = urlparse(base_url).netloc
        
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            if not href:
                continue
            
            # Convertir a URL absoluta
            url_absoluta = urljoin(base_url, href)
            
            # Filtrar solo links del mismo dominio
            dominio_link = urlparse(url_absoluta).netloc
            if dominio_link != dominio_base:
                continue
            
            # Evitar duplicados
            if url_absoluta not in [l['url'] for l in links_encontrados]:
                links_encontrados.append({
                    'url': url_absoluta,
                    'texto': link.get_text(strip=True)[:200],
                })
        
        logger.info(f"Encontrados {len(links_encontrados)} enlaces en semilla")
        
        # Crear fuentes hijo para cada link
        fuentes_creadas = 0
        with transaction.atomic():
            for link_info in links_encontrados:
                # Verificar si ya existe
                if FuenteWeb.objects.filter(url=link_info['url']).exists():
                    continue
                
                # Crear fuente hijo
                fuente_hijo = FuenteWeb(
                    nombre=link_info['texto'] or f"Documento desde {captura.fuente.nombre}",
                    url=link_info['url'],
                    tipo='documento_directo_html',  # Por defecto HTML
                    categoria=captura.fuente.categoria,
                    estado='activa',
                    prioridad=max(1, captura.fuente.prioridad - 1),
                    frecuencia_revision_horas=captura.fuente.frecuencia_revision_horas * 2,
                    descubierta_por=captura.fuente,
                    profundidad_descubrimiento=captura.fuente.profundidad_descubrimiento + 1,
                )
                fuente_hijo.save()
                fuentes_creadas += 1
        
        # Actualizar estado
        captura.estado_procesamiento = 'completado'
        captura.num_links = len(links_encontrados)
        captura.save()
        
        logger.info(f"Semilla procesada: {fuentes_creadas} fuentes nuevas creadas")
        
        return {
            'estado': 'completado',
            'links_encontrados': len(links_encontrados),
            'fuentes_creadas': fuentes_creadas,
        }
        
    except Exception as e:
        logger.error(f"Error procesando semilla listado: {e}")
        captura.estado_procesamiento = 'error'
        captura.mensaje_error = str(e)
        captura.save()
        return {'estado': 'error', 'mensaje': str(e)}


@shared_task
def procesar_documento_html(captura_id: int) -> Dict[str, Any]:
    """
    Procesa un documento HTML: extrae texto limpio.
    
    Args:
        captura_id: ID de la captura a procesar
        
    Returns:
        Resultado del procesamiento
    """
    try:
        captura = CapturaCruda.objects.get(id=captura_id)
    except CapturaCruda.DoesNotExist:
        logger.error(f"Captura {captura_id} no encontrada")
        return {'estado': 'error', 'mensaje': 'Captura no encontrada'}
    
    logger.info(f"Procesando documento HTML: {captura.fuente.nombre}")
    
    captura.estado_procesamiento = 'procesando'
    captura.save()
    
    try:
        if not captura.contenido_html:
            raise ValueError("No hay contenido HTML")
        
        # Parsear HTML
        soup = BeautifulSoup(captura.contenido_html, 'html.parser')
        
        # Extraer texto limpio
        # Eliminar scripts y estilos
        for script in soup(['script', 'style', 'nav', 'footer', 'header']):
            script.decompose()
        
        # Obtener texto
        texto_limpio = soup.get_text(separator='\n', strip=True)
        
        # Limpiar espacios múltiples
        import re
        texto_limpio = re.sub(r'\n+', '\n', texto_limpio)
        texto_limpio = re.sub(r' +', ' ', texto_limpio)
        
        # Guardar texto extraído
        captura.texto_extraido = texto_limpio
        captura.estado_procesamiento = 'texto_extraido_ok'
        captura.save()
        
        logger.info(f"HTML procesado: {len(texto_limpio)} caracteres extraídos")
        
        return {
            'estado': 'completado',
            'caracteres_extraidos': len(texto_limpio),
        }
        
    except Exception as e:
        logger.error(f"Error procesando HTML: {e}")
        captura.estado_procesamiento = 'error'
        captura.mensaje_error = str(e)
        captura.save()
        return {'estado': 'error', 'mensaje': str(e)}


@shared_task
def procesar_documento_pdf(captura_id: int) -> Dict[str, Any]:
    """
    Procesa un documento PDF: intenta extraer texto nativo o marca para OCR.
    
    Args:
        captura_id: ID de la captura a procesar
        
    Returns:
        Resultado del procesamiento
    """
    try:
        captura = CapturaCruda.objects.get(id=captura_id)
    except CapturaCruda.DoesNotExist:
        logger.error(f"Captura {captura_id} no encontrada")
        return {'estado': 'error', 'mensaje': 'Captura no encontrada'}
    
    logger.info(f"Procesando documento PDF: {captura.fuente.nombre}")
    
    captura.estado_procesamiento = 'procesando'
    captura.save()
    
    try:
        # Obtener contenido del PDF
        if captura.contenido_binario_blob:
            # Descargar desde Azure
            from captura.azure_storage import download_raw_content
            contenido_pdf = download_raw_content(captura.contenido_binario_blob)
        else:
            raise ValueError("No hay contenido PDF disponible")
        
        # Extraer información del PDF
        extractor = ExtractorPDF()
        info_pdf = extractor.extraer_informacion_pdf(contenido_pdf)
        
        if info_pdf.get('error'):
            raise ValueError(f"Error extrayendo PDF: {info_pdf['error']}")
        
        # Guardar información
        captura.pdf_tiene_texto = info_pdf.get('tiene_texto', False)
        captura.pdf_num_paginas = info_pdf.get('num_paginas', 0)
        
        if info_pdf.get('tiene_texto'):
            # PDF nativo con texto
            captura.tipo_documento = 'pdf_nativo'
            captura.texto_extraido = info_pdf.get('texto_extraido', '')
            captura.estado_procesamiento = 'texto_extraido_ok'
            logger.info(f"PDF nativo: {len(captura.texto_extraido)} caracteres extraídos")
        else:
            # PDF escaneado - requiere OCR
            captura.tipo_documento = 'pdf_escaneado'
            captura.estado_procesamiento = 'requiere_ocr'
            logger.info(f"PDF escaneado detectado - marcado para OCR")
        
        captura.save()
        
        return {
            'estado': 'completado',
            'tipo_pdf': captura.tipo_documento,
            'num_paginas': captura.pdf_num_paginas,
            'caracteres_extraidos': len(captura.texto_extraido) if captura.texto_extraido else 0,
            'requiere_ocr': captura.necesita_ocr(),
        }
        
    except Exception as e:
        logger.error(f"Error procesando PDF: {e}")
        captura.estado_procesamiento = 'error'
        captura.mensaje_error = str(e)
        captura.save()
        return {'estado': 'error', 'mensaje': str(e)}


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
    )
    captura.save()
    
    logger.info(f"Captura de error creada para {fuente.nombre}: {mensaje}")
