import re
import signal
import hashlib
from datetime import datetime
from celery import shared_task
import logging
from typing import List, Dict, Optional
from django.db import IntegrityError
from .models import ExtractorLog, ArchivoExtraccionWhatsApp, LogEntry
from requerimientos.models import Requerimiento
from .services.whatsapp_txt_parser import WhatsAppTxtParser
from .services.text_normalizer import TextNormalizer
from .services.deduplicacion_ia import DeduplicadorIA
from .services.deepseek_transformer import DeepSeekTransformer
from intelligence.skills.orchestrator import SkillOrchestrator
from intelligence.skills.registry import SkillRegistry


class DeduplicadorIAError(Exception):
    '''Error base del servicio de deduplicación IA.'''
    pass


logger = logging.getLogger(__name__)

# Cada cuántos mensajes se reporta progreso vía LogEntry
LOTE_PROGRESO = 5

# Timeout máximo por mensaje (segundos) para evitar que una llamada
# a DeepSeek se cuelgue y detenga todo el procesamiento
TIMEOUT_POR_MENSAJE = 30


class TimeoutError(Exception):
    """Se lanza cuando una operación excede el tiempo máximo permitido."""
    pass


def _timeout_handler(signum, frame):
    """Manejador de timeout para signal.alarm()."""
    raise TimeoutError("La operación excedió el tiempo máximo permitido")


def _ejecutar_con_timeout(func, timeout: int, *args, **kwargs):
    """
    Ejecuta una función con timeout.
    Si la función no termina en `timeout` segundos, lanza TimeoutError.
    
    Args:
        func: Función a ejecutar.
        timeout: Timeout en segundos.
        args, kwargs: Argumentos para la función.
        
    Returns:
        El resultado de la función.
        
    Raises:
        TimeoutError: Si la función excede el timeout.
    """
    # signal.alarm() solo funciona en Unix, en Windows usamos un enfoque diferente
    import threading
    
    resultado = []
    excepcion = []
    
    def _target():
        try:
            resultado.append(func(*args, **kwargs))
        except Exception as e:
            excepcion.append(e)
    
    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    thread.join(timeout)
    
    if thread.is_alive():
        raise TimeoutError(f"La operación excedió el timeout de {timeout}s")
    
    if excepcion:
        raise excepcion[0]
    
    return resultado[0] if resultado else None


def _es_telefono(texto: str) -> bool:
    """Determina si un texto es un número de teléfono."""
    if not texto:
        return False
    # Limpiar caracteres de control Unicode (menciones WhatsApp)
    limpio = re.sub(r'[\u2068\u2069\u200e\u200f]', '', texto)
    # Quitar espacios y +
    solo_digitos = re.sub(r'[\s\+]', '', limpio)
    # Si después de limpiar solo quedan dígitos y tiene al menos 7, es teléfono
    if solo_digitos.isdigit() and len(solo_digitos) >= 7:
        return True
    return False


def _truncar(valor: Optional[str], max_length: int) -> str:
    """Trunca un string a max_length caracteres para evitar errores de truncamiento en SQL Server.
    
    Si el valor es None o vacío, retorna string vacío.
    Si excede max_length, trunca y agrega '...' al final.
    """
    if not valor:
        return ''
    if len(valor) > max_length:
        return valor[:max_length - 3] + '...'
    return valor

# Patrón para extraer nombre del grupo del filename
# VERSIÓN GENÉRICA: captura cualquier texto después de "WhatsApp" hasta ".txt"
# Elimina automáticamente preposiciones/conectores comunes del resultado
# SIN lista fija en el regex - usa limpieza post-extracción para escalabilidad
# Ej: "Chat de WhatsApp con RED INMOBILIARIA AREQUIPA.txt" → "RED INMOBILIARIA AREQUIPA"
# Ej: "Chat de WhatsApp de EXITO INMOBILIARIO AGENTES.txt" → "EXITO INMOBILIARIO AGENTES"
# Ej: "Chat de WhatsApp por GRUPO VENTAS.txt" → "GRUPO VENTAS"
# Ej: "WhatsApp Chat with ENGLISH GROUP.txt" → "ENGLISH GROUP"
# Ej: "Chat WhatsApp - Grupo Ejemplo.txt" → "Grupo Ejemplo"
# Ej: "Chat de WhatsApp del GRUPO TEST.txt" → "GRUPO TEST"
# Ej: "Chat de WhatsApp en MI GRUPO.txt" → "MI GRUPO"
# Ej: "WhatsApp Chat GROUP NAME.txt" → "GROUP NAME"
PATRON_NOMBRE_GRUPO = re.compile(
    r'(?:Chat\s+(?:de\s+)?)?WhatsApp(?:\s*Chat)?(?:\s*[-–—]\s*|\s+(?:con|de|por|para|del|en|desde|with|from|by|for)\s+|\s+)?(.+?)\.txt$',
    re.IGNORECASE
)

# Preposiciones/conectores a eliminar del inicio del nombre extraído
_PREPOSICIONES_INICIO = (
    'con', 'de', 'por', 'para', 'del', 'en', 'desde',
    'with', 'from', 'by', 'for', 'the', 'a', 'an',
    'el', 'la', 'los', 'las', 'un', 'una',
)


def _limpiar_nombre_grupo(nombre: str) -> str:
    """Limpia el nombre del grupo eliminando preposiciones/conectores del inicio."""
    nombre = nombre.strip()
    # Separar en palabras y eliminar preposiciones del inicio
    palabras = nombre.split()
    while palabras and palabras[0].lower() in _PREPOSICIONES_INICIO:
        palabras = palabras[1:]
    return ' '.join(palabras).strip() or nombre


def _extraer_nombre_grupo(archivo: ArchivoExtraccionWhatsApp) -> str:
    """Extrae el nombre del grupo WhatsApp desde el archivo o su grupo relacionado."""
    # 1. Si tiene grupo relacionado, usar su nombre
    if archivo.grupo_relacionado and archivo.grupo_relacionado.nombre_grupo:
        return archivo.grupo_relacionado.nombre_grupo

    # 2. Extraer del nombre del archivo
    nombre = archivo.nombre_archivo_original
    match = PATRON_NOMBRE_GRUPO.search(nombre)
    if match:
        nombre_extraido = match.group(1).strip()
        return _limpiar_nombre_grupo(nombre_extraido)

    # 3. Fallback: usar el nombre del archivo sin extensión
    return nombre.replace('.txt', '').strip()


def _reportar_progreso(extractor_log, mensajes_procesados: int, total: int,
                       mensajes_validos: int, duplicados: int, nivel: str = 'INFO'):
    """Crea una entrada de LogEntry con el progreso actual."""
    pct = round((mensajes_procesados / total) * 100, 1) if total > 0 else 0
    LogEntry.objects.create(
        extractor_log=extractor_log,
        nivel=nivel,
        mensaje=(
            f'[{mensajes_procesados}/{total}] {pct}% — '
            f'{mensajes_validos} válidos, {duplicados} duplicados'
        ),
        detalles={
            'progreso': mensajes_procesados,
            'total': total,
            'porcentaje': pct,
            'validos': mensajes_validos,
            'duplicados': duplicados,
        }
    )


@shared_task
def procesar_archivo_extraccion(archivo_id: int, extractor_log_id: Optional[int] = None) -> Dict:
    '''Procesa un archivo de extracción WhatsApp.

    Args:
        archivo_id: ID del ArchivoExtraccionWhatsApp a procesar.
        extractor_log_id: ID del ExtractorLog ya creado (opcional).
                         Si se proporciona, se reutiliza en lugar de crear uno nuevo.
                         Esto permite que la vista cree el log ANTES de iniciar el hilo,
                         para que la página de progreso pueda mostrarlo inmediatamente.

    Returns:
        Dict con el resumen del proceso.
    '''
    try:
        # 1. Obtener archivo
        archivo = ArchivoExtraccionWhatsApp.objects.get(id=archivo_id)
        if not archivo:
            raise ValueError(f'Archivo no encontrado: {archivo_id}')

        # 2. Extraer nombre del grupo WhatsApp desde el archivo
        nombre_grupo = _extraer_nombre_grupo(archivo)

        # 3. Iniciar o reutilizar log
        if extractor_log_id:
            # Reutilizar el log ya creado desde la vista
            extractor_log = ExtractorLog.objects.get(pk=extractor_log_id)
            LogEntry.objects.create(
                extractor_log=extractor_log,
                nivel='INFO',
                mensaje=f'📁 Grupo detectado: {nombre_grupo}',
                detalles={'nombre_grupo': nombre_grupo},
            )
        else:
            # Crear nuevo log (modo legacy)
            extractor_log = ExtractorLog(
                archivo_subido=archivo.nombre_archivo_original,
                estado='running',
                mensajes_extraidos_total=0,
                mensajes_validos=0,
                requerimientos_duplicados=0,
            )
            extractor_log.save()

            LogEntry.objects.create(
                extractor_log=extractor_log,
                nivel='INFO',
                mensaje=f'📁 Grupo detectado: {nombre_grupo}',
                detalles={'nombre_grupo': nombre_grupo},
            )

            # Log de inicio
            LogEntry.objects.create(
                extractor_log=extractor_log,
                nivel='INFO',
                mensaje='Iniciando procesamiento del archivo...',
                detalles={},
            )

        # 3. Parsear archivo
        mensajes = WhatsAppTxtParser.parsear_archivo(archivo.ruta_almacenamiento)
        total_mensajes = len(mensajes)

        # ACTUALIZAR el contador en BD inmediatamente después del parseo
        extractor_log.mensajes_extraidos_total = total_mensajes
        extractor_log.save(update_fields=['mensajes_extraidos_total'])

        # --- FILTRO DE DUPLICADOS DENTRO DEL MISMO ARCHIVO TXT ---
        # Antes de procesar, detectamos mensajes repetidos dentro del mismo archivo
        # para no llamar a DeepSeek ni a la BD innecesariamente.
        mensajes_unicos = set()
        mensajes_filtrados = []
        duplicados_en_txt = 0
        for msg in mensajes:
            texto_normalizado = ' '.join(msg.get('texto', '').lower().split())
            if texto_normalizado in mensajes_unicos:
                duplicados_en_txt += 1
                continue
            mensajes_unicos.add(texto_normalizado)
            mensajes_filtrados.append(msg)

        mensajes = mensajes_filtrados
        total_mensajes_original = extractor_log.mensajes_extraidos_total
        total_mensajes = len(mensajes)

        LogEntry.objects.create(
            extractor_log=extractor_log,
            nivel='INFO',
            mensaje=f'Archivo parseado: {total_mensajes_original} mensajes totales, {duplicados_en_txt} duplicados dentro del archivo, {total_mensajes} únicos a procesar',
            detalles={
                'total_mensajes': total_mensajes_original,
                'duplicados_en_txt': duplicados_en_txt,
                'mensajes_unicos': total_mensajes,
            },
        )

        if total_mensajes == 0:
            LogEntry.objects.create(
                extractor_log=extractor_log,
                nivel='WARNING',
                mensaje='El archivo no contiene mensajes nuevos para procesar (todos son duplicados dentro del archivo)',
                detalles={},
            )
            extractor_log.mensajes_extraidos_total = 0
            extractor_log.estado = 'completed'
            extractor_log.save()
            archivo.procesado = True
            archivo.save()
            return {
                'success': True,
                'archivo_id': archivo.id,
                'mensajes_procesados': 0,
                'mensajes_validos': 0,
                'mensajes_duplicados': duplicados_en_txt,
                'extractor_log_id': extractor_log.id,
            }

        for idx, msg in enumerate(mensajes, start=1):
            # 4. Verificar estado de pausa/detención antes de procesar cada mensaje
            # Recargar el log desde BD para obtener el estado actual
            log_refreshed = ExtractorLog.objects.get(pk=extractor_log.pk)
            
            # Actualizar progreso en BD cada 10 mensajes para que el frontend lo vea
            if idx % 10 == 0:
                extractor_log.mensajes_extraidos_total = total_mensajes
                extractor_log.mensajes_validos = log_refreshed.mensajes_validos
                extractor_log.requerimientos_duplicados = log_refreshed.requerimientos_duplicados
                extractor_log.save(update_fields=['mensajes_extraidos_total', 'mensajes_validos', 'requerimientos_duplicados'])
            if log_refreshed.estado == 'paused':
                LogEntry.objects.create(
                    extractor_log=extractor_log,
                    nivel='WARNING',
                    mensaje=f'⏸️ Procesamiento pausado en mensaje #{idx}. Esperando reanudación...',
                    detalles={'mensaje_idx': idx, 'accion': 'pausado'},
                )
                # Esperar hasta que se reanude o se detenga
                while True:
                    import time
                    time.sleep(2)
                    log_refreshed = ExtractorLog.objects.get(pk=extractor_log.pk)
                    if log_refreshed.estado == 'running':
                        LogEntry.objects.create(
                            extractor_log=extractor_log,
                            nivel='INFO',
                            mensaje=f'▶️ Procesamiento reanudado en mensaje #{idx}',
                            detalles={'mensaje_idx': idx, 'accion': 'reanudado'},
                        )
                        break
                    elif log_refreshed.estado == 'error':
                        LogEntry.objects.create(
                            extractor_log=extractor_log,
                            nivel='ERROR',
                            mensaje=f'🛑 Procesamiento detenido por el usuario en mensaje #{idx}',
                            detalles={'mensaje_idx': idx, 'accion': 'detenido'},
                        )
                        # Marcar archivo como no procesado para poder reprocesar
                        archivo.procesado = False
                        archivo.save(update_fields=['procesado'])
                        # Salir de la función completamente
                        extractor_log.mensajes_extraidos_total = idx - 1
                        extractor_log.save(update_fields=['mensajes_extraidos_total'])
                        return {
                            'success': False,
                            'error': 'Procesamiento detenido por el usuario',
                            'archivo_id': archivo.id,
                            'mensajes_procesados': idx - 1,
                            'mensajes_validos': extractor_log.mensajes_validos,
                            'mensajes_duplicados': extractor_log.requerimientos_duplicados + duplicados_en_txt,
                            'extractor_log_id': extractor_log.id,
                        }
                    elif log_refreshed.estado in ('completed',):
                        # Si alguien marcó como completado, salir
                        return {
                            'success': True,
                            'archivo_id': archivo.id,
                            'mensajes_procesados': idx - 1,
                            'mensajes_validos': extractor_log.mensajes_validos,
                            'mensajes_duplicados': extractor_log.requerimientos_duplicados + duplicados_en_txt,
                            'extractor_log_id': extractor_log.id,
                        }

            elif log_refreshed.estado == 'error':
                # Si detectamos que fue detenido externamente
                LogEntry.objects.create(
                    extractor_log=extractor_log,
                    nivel='ERROR',
                    mensaje=f'🛑 Procesamiento detenido externamente en mensaje #{idx}',
                    detalles={'mensaje_idx': idx, 'accion': 'detenido_externo'},
                )
                archivo.procesado = False
                archivo.save(update_fields=['procesado'])
                extractor_log.mensajes_extraidos_total = idx - 1
                extractor_log.save(update_fields=['mensajes_extraidos_total'])
                return {
                    'success': False,
                    'error': 'Procesamiento detenido',
                    'archivo_id': archivo.id,
                    'mensajes_procesados': idx - 1,
                    'mensajes_validos': extractor_log.mensajes_validos,
                    'mensajes_duplicados': extractor_log.requerimientos_duplicados + duplicados_en_txt,
                    'extractor_log_id': extractor_log.id,
                }

            # 5. Normalizar texto
            texto_limpio = TextNormalizer.limpiar_texto(msg['texto'])

            try:
                # 6. Verificar duplicado contra BD (histórico de requerimientos)
                is_duplicate, matching_id = DeduplicadorIA.verificar_duplicado_simple(
                    texto_limpio,
                    agente=msg.get('autor', ''),
                )

                if is_duplicate:
                    logger.info(f'Mensaje duplicado en BD: {msg["texto"][:50]}')
                    extractor_log.requerimientos_duplicados += 1
                    continue

                # 7. Extraer campos estructurados con DeepSeek (con timeout)
                # Pasar fecha y hora del mensaje parseado para que se usen en vez de timezone.now()
                fecha_msg_param = msg.get('fecha', '')
                hora_msg_param = msg.get('hora', '')
                try:
                    datos_extraidos = _ejecutar_con_timeout(
                        DeepSeekTransformer.transformar,
                        TIMEOUT_POR_MENSAJE,
                        texto=texto_limpio,
                        fuente=nombre_grupo,
                        autor=msg.get('autor', ''),
                        fecha=fecha_msg_param,
                        hora=hora_msg_param,
                    )
                except TimeoutError:
                    logger.warning(f'Timeout extrayendo datos del mensaje {idx}, se omite')
                    LogEntry.objects.create(
                        extractor_log=extractor_log,
                        nivel='WARNING',
                        mensaje=f'Mensaje #{idx}: timeout al extraer datos con DeepSeek (>={TIMEOUT_POR_MENSAJE}s)',
                        detalles={'mensaje_idx': idx, 'texto_preview': texto_limpio[:100]},
                    )
                    continue
                except Exception as e:
                    logger.error(f'Error extrayendo datos del mensaje {idx}: {e}')
                    LogEntry.objects.create(
                        extractor_log=extractor_log,
                        nivel='ERROR',
                        mensaje=f'Mensaje #{idx}: error al extraer datos: {str(e)[:200]}',
                        detalles={'mensaje_idx': idx, 'error': str(e)},
                    )
                    continue

                if not datos_extraidos:
                    logger.warning(f'No se obtuvieron datos para mensaje {idx}')
                    continue

                # --- FILTRO: Saltar si la extracción devolvió un resultado vacío (con _error) ---
                if datos_extraidos.get('_error'):
                    logger.warning(f'Mensaje {idx}: extracción fallida: {datos_extraidos["_error"]}')
                    LogEntry.objects.create(
                        extractor_log=extractor_log,
                        nivel='WARNING',
                        mensaje=f'Mensaje #{idx}: extracción fallida (todos los campos vacíos): {datos_extraidos["_error"]}',
                        detalles={'mensaje_idx': idx, 'error': datos_extraidos['_error']},
                    )
                    continue

                # 8. Guardar como Requerimiento con todos los campos extraídos
                tipo_original = _truncar(datos_extraidos.get('tipo_original'), 80) or 'EXTRACCION_WHATSAPP'
                # Extraer fecha y hora del mensaje original (fecha_hora viene del parser en ISO format)
                fecha_msg = None
                hora_msg = None
                fecha_hora_str = msg.get('fecha_hora')
                if fecha_hora_str:
                    try:
                        # fecha_hora_str viene en ISO format: "2024-01-15T14:30:00"
                        dt_parsed = datetime.fromisoformat(fecha_hora_str)
                        fecha_msg = dt_parsed.date()
                        hora_msg = dt_parsed.time()
                    except (ValueError, TypeError):
                        pass

                # Usar el texto original del mensaje (msg['texto']) para el campo 'requerimiento',
                # NO texto_limpio, porque el normalizador puede dejar el texto vacío.
                # texto_limpio se usa solo para el análisis de DeepSeek.
                texto_original = msg.get('texto', '') or texto_limpio
                # --- TELÉFONO DEL AGENTE ---
                # 1° prioridad: teléfono extraído por el parser desde el encabezado (msg['agente_telefono'])
                # 2° prioridad: teléfono extraído por DeepSeek desde el cuerpo del mensaje
                # 3° prioridad: el autor del encabezado si parece un teléfono
                autor_raw = msg.get('autor', '') or ''
                telefono_parser = msg.get('agente_telefono', '') or ''
                telefono_deepseek = datos_extraidos.get('agente_telefono', '') or ''
                if telefono_parser:
                    telefono_final = telefono_parser
                elif telefono_deepseek:
                    telefono_final = telefono_deepseek
                elif _es_telefono(autor_raw):
                    telefono_final = autor_raw
                else:
                    telefono_final = ''
                # --- NOMBRE DEL AGENTE ---
                # 1° prioridad: nombre extraído por DeepSeek desde el cuerpo del mensaje
                # 2° prioridad: el autor del encabezado (si no es teléfono)
                # 3° prioridad: el teléfono del encabezado como fallback
                nombre_extraido = datos_extraidos.get('agente', '') or ''
                if nombre_extraido:
                    nombre_agente = nombre_extraido
                elif not _es_telefono(autor_raw):
                    nombre_agente = autor_raw
                else:
                    nombre_agente = telefono_final or autor_raw
                # Calcular hash SHA256 del texto normalizado para deduplicación
                texto_normalizado = ' '.join(texto_original.lower().split())
                texto_hash = hashlib.sha256(texto_normalizado.encode()).hexdigest()

                # --- Verificar duplicado por texto_hash ANTES de insertar ---
                # El índice único en BD es (texto_hash, fecha, hora, fuente)
                # Hacemos una verificación extra aquí para atraparlo antes del error de BD
                duplicado_bd = Requerimiento.objects.filter(
                    texto_hash=texto_hash,
                    fecha=fecha_msg,
                    hora=hora_msg,
                    fuente=_truncar(nombre_grupo, 60),
                ).exists()
                if duplicado_bd:
                    logger.info(f'Mensaje duplicado (por hash+BD): {texto_original[:50]}')
                    extractor_log.requerimientos_duplicados += 1
                    continue

                try:
                    Requerimiento.objects.create(
                        requerimiento=texto_original,
                        texto_hash=texto_hash,
                        fuente=_truncar(nombre_grupo, 60),
                        agente=_truncar(nombre_agente, 120),
                        fecha=fecha_msg,
                        hora=hora_msg,
                        extractor_log=extractor_log,
                        tipo_original=tipo_original,
                        condicion=_truncar(datos_extraidos.get('condicion'), 20) or 'no_especificado',
                        tipo_propiedad=_truncar(datos_extraidos.get('tipo_propiedad'), 20) or 'no_especificado',
                        distritos=_truncar(datos_extraidos.get('distritos'), 300),
                        presupuesto_monto=datos_extraidos.get('presupuesto_monto'),
                        presupuesto_moneda=_truncar(datos_extraidos.get('presupuesto_moneda'), 20) or 'no_especificado',
                        presupuesto_forma_pago=_truncar(datos_extraidos.get('presupuesto_forma_pago'), 20) or 'no_especificado',
                        habitaciones=datos_extraidos.get('habitaciones'),
                        banos=datos_extraidos.get('banos'),
                        cochera=_truncar(datos_extraidos.get('cochera'), 12) or 'indiferente',
                        ascensor=_truncar(datos_extraidos.get('ascensor'), 12) or 'indiferente',
                        amueblado=_truncar(datos_extraidos.get('amueblado'), 12) or 'indiferente',
                        area_m2=datos_extraidos.get('area_m2'),
                        piso_preferencia=_truncar(datos_extraidos.get('piso_preferencia'), 60),
                        caracteristicas_extra=_truncar(datos_extraidos.get('caracteristicas_extra'), 300),
                        agente_telefono=_truncar(telefono_final, 20),
                    )
                    extractor_log.mensajes_validos += 1
                except IntegrityError:
                    # El índice único de BD detectó un duplicado que no atrapamos antes
                    logger.info(f'Mensaje duplicado (IntegrityError BD): {texto_original[:50]}')
                    extractor_log.requerimientos_duplicados += 1
                    continue

            except IntegrityError:
                # IntegrityError del create() si no pasó por el bloque try anidado
                logger.info(f'Mensaje duplicado (IntegrityError BD, outer): {texto_original[:50]}')
                extractor_log.requerimientos_duplicados += 1
                continue
            except Exception as e:
                logger.error(f'Error procesando mensaje {idx}: {e}', exc_info=True)
                LogEntry.objects.create(
                    extractor_log=extractor_log,
                    nivel='ERROR',
                    mensaje=f'Mensaje #{idx}: error inesperado: {str(e)[:200]}',
                    detalles={'mensaje_idx': idx, 'error': str(e)},
                )
                continue

            # 9. Reportar progreso cada LOTE_PROGRESO mensajes (después de procesar)
            if idx % LOTE_PROGRESO == 0 or idx == total_mensajes:
                _reportar_progreso(
                    extractor_log,
                    mensajes_procesados=idx,
                    total=total_mensajes,
                    mensajes_validos=extractor_log.mensajes_validos,
                    duplicados=extractor_log.requerimientos_duplicados,
                )

        # 8. Finalizar log
        total_duplicados = extractor_log.requerimientos_duplicados + duplicados_en_txt
        extractor_log.mensajes_extraidos_total = total_mensajes
        extractor_log.estado = 'completed'
        extractor_log.save()

        # Log de finalización
        LogEntry.objects.create(
            extractor_log=extractor_log,
            nivel='INFO',
            mensaje=(
                f'✅ Procesamiento completado: '
                f'{extractor_log.mensajes_validos} nuevos, '
                f'{total_duplicados} duplicados '
                f'({duplicados_en_txt} en TXT, {extractor_log.requerimientos_duplicados} en BD) '
                f'de {total_mensajes_original} mensajes totales'
            ),
            detalles={
                'progreso': total_mensajes,
                'total': total_mensajes_original,
                'porcentaje': 100.0,
                'validos': extractor_log.mensajes_validos,
                'duplicados': total_duplicados,
                'duplicados_en_txt': duplicados_en_txt,
                'duplicados_en_bd': extractor_log.requerimientos_duplicados,
            }
        )

        # 9. Marcar archivo como procesado
        archivo.procesado = True
        archivo.save()

        logger.info(
            f'Archivo {archivo.nombre_archivo_original} procesado: '
            f'{extractor_log.mensajes_validos} nuevos, '
            f'{total_duplicados} duplicados '
            f'({duplicados_en_txt} en TXT, {extractor_log.requerimientos_duplicados} en BD)'
        )

        return {
            'success': True,
            'archivo_id': archivo.id,
            'mensajes_procesados': extractor_log.mensajes_extraidos_total,
            'mensajes_validos': extractor_log.mensajes_validos,
            'mensajes_duplicados': total_duplicados,
            'extractor_log_id': extractor_log.id,
        }

    except ArchivoExtraccionWhatsApp.DoesNotExist:
        logger.error(f'Archivo no encontrado: {archivo_id}')
        return {
            'success': False,
            'error': f'Archivo no encontrado: {archivo_id}',
        }
    except Exception as e:
        logger.error(f'Error procesando archivo {archivo_id}: {e}', exc_info=True)
        if 'extractor_log' in locals():
            extractor_log.estado = 'error'
            extractor_log.mensaje_error = str(e)
            extractor_log.save()
            LogEntry.objects.create(
                extractor_log=extractor_log,
                nivel='ERROR',
                mensaje=f'❌ Error: {str(e)}',
                detalles={'error': str(e)},
            )
        return {
            'success': False,
            'error': str(e),
        }
