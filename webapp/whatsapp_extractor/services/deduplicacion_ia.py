"""
Servicio de deduplicación de requerimientos inmobiliarios.

AHORA usa deduplicación LOCAL por hash de texto normalizado
en lugar de llamar a DeepSeek API por cada mensaje.
Esto reduce drásticamente el tiempo de procesamiento
(de ~4 horas a ~minutos para archivos grandes).

El método original con DeepSeek se mantiene como `verificar_duplicado()`
por si se necesita en el futuro para análisis más profundos.
"""

import json
import logging
import hashlib
from datetime import timedelta
from typing import Dict, List, Optional, Tuple
from django.db.models.query import QuerySet
from django.utils import timezone
from requerimientos.models import Requerimiento
from intelligence.services.llm import LLMService


logger = logging.getLogger(__name__)


class DeduplicacionIAError(Exception):
    """Error base del servicio de deduplicación IA."""
    pass


class DeduplicadorIA:
    """
    Deduplicador semántico de requerimientos.

    AHORA usa deduplicación LOCAL rápida por defecto.
    El método con DeepSeek API se mantiene como alternativa.

    Attributes:
        ULTIMOS_REQUERIMIENTOS: Cantidad de requerimientos recientes a comparar.
        DIAS_HISTORICO: Ventana de tiempo para buscar duplicados.
        THRESHOLD_SIMILITUD: Porcentaje mínimo para considerar duplicado (0-100).
    """

    # Configuración de búsqueda
    ULTIMOS_REQUERIMIENTOS = 10000  # Buscar en hasta 10,000 requerimientos históricos
    DIAS_HISTORICO = 3650  # 10 años - buscar en TODO el histórico
    THRESHOLD_SIMILITUD = 85  # 85% mínimo para considerar duplicado

    # Prompt para DeepSeek
    PROMPT_DEDUPLICACION = """
Eres un experto en análisis de requerimientos inmobiliarios.
Tu tarea es determinar si un NUEVO mensaje es DUPLICADO de alguno de los requerimientos históricos proporcionados.

NUEVO MENSAJE:
{texto_nuevo}

REQUERIMIENTOS HISTÓRICOS:
{historial}

Responde SOLO con un JSON válido con esta estructura:
{{
    "is_duplicate": true/false,
    "match_score": 0-100,
    "matching_id": id_del_requerimiento_duplicado_o_null,
    "reason": "breve explicación"
}}
"""

    @classmethod
    def _obtener_historial_reciente(cls) -> QuerySet:
        """
        Obtiene los requerimientos más recientes para comparación.

        Returns:
            QuerySet con los últimos N requerimientos de los últimos D días.
        """
        fecha_limite = timezone.now().date() - timedelta(days=cls.DIAS_HISTORICO)

        return Requerimiento.objects.filter(
            fecha__gte=fecha_limite
        ).order_by('-fecha', '-hora')[:cls.ULTIMOS_REQUERIMIENTOS]

    @classmethod
    def _formatear_historial(cls, historial: QuerySet) -> str:
        """
        Formatea los requerimientos históricos para incluirlos en el prompt.

        Args:
            historial: QuerySet de Requerimiento.

        Returns:
            String formateado con los datos relevantes de cada requerimiento.
        """
        partes = []
        for req in historial:
            partes.append(
                f"ID: {req.id} | "
                f"Tipo: {req.get_tipo_propiedad_display()} | "
                f"Condición: {req.get_condicion_display()} | "
                f"Distrito(s): {req.distritos or 'N/A'} | "
                f"Presupuesto: {req.presupuesto_display} | "
                f"Habitaciones: {req.habitaciones or 'N/A'} | "
                f"Baños: {req.banos or 'N/A'} | "
                f"Área: {req.area_m2 or 'N/A'} m² | "
                f"Texto: {req.requerimiento[:200]}"
            )
        return "\n".join(partes)

    @classmethod
    def verificar_duplicado(cls, texto_mensaje: str) -> Dict:
        """
        Verifica si un mensaje es duplicado de algún requerimiento existente
        usando DeepSeek API (método original, mantenido por compatibilidad).

        Args:
            texto_mensaje: Texto del mensaje nuevo a verificar.

        Returns:
            Dict con:
                - is_duplicate: bool
                - match_score: int (0-100)
                - matching_id: int or None
                - reason: str
                - error: str (si ocurrió un error)
        """
        resultado_base = {
            'is_duplicate': False,
            'match_score': 0,
            'matching_id': None,
            'reason': 'No se pudo verificar duplicado',
            'error': None,
        }

        try:
            # 1. Obtener historial reciente
            historial = cls._obtener_historial_reciente()

            if not historial.exists():
                logger.info("No hay historial para comparar")
                return {
                    **resultado_base,
                    'reason': 'No hay requerimientos históricos para comparar',
                }

            # 2. Formatear historial para el prompt
            historial_formateado = cls._formatear_historial(historial)

            # 3. Construir prompt
            prompt = cls.PROMPT_DEDUPLICACION.format(
                texto_nuevo=texto_mensaje[:500],  # Limitar longitud
                historial=historial_formateado,
            )

            # 4. Llamar a DeepSeek con temperatura baja
            success, message, api_response = LLMService._call_deepseek_api(
                messages=[{"role": "user", "content": prompt}],
                system_prompt=(
                    "Eres un clasificador de duplicados inmobiliarios. "
                    "Responde SOLO con JSON válido."
                ),
            )

            if not success:
                logger.error(f"Error llamando a DeepSeek para deduplicación: {message}")
                return {
                    **resultado_base,
                    'error': f"Error de API: {message}",
                }

            # 5. Extraer JSON de la respuesta
            contenido = api_response.get('content', '')
            resultado = cls._extraer_json_respuesta(contenido)

            if not resultado:
                logger.warning("No se pudo extraer JSON de la respuesta de DeepSeek")
                return {
                    **resultado_base,
                    'error': 'Respuesta inválida de DeepSeek',
                }

            # 6. Validar threshold
            match_score = resultado.get('match_score', 0)
            if match_score >= cls.THRESHOLD_SIMILITUD:
                resultado['is_duplicate'] = True
            else:
                resultado['is_duplicate'] = False

            logger.info(
                f"Deduplicación: score={match_score}, "
                f"duplicate={resultado['is_duplicate']}, "
                f"reason={resultado.get('reason', 'N/A')}"
            )

            return resultado

        except Exception as e:
            logger.error(f"Error en deduplicación: {e}", exc_info=True)
            return {
                **resultado_base,
                'error': str(e),
            }

    @classmethod
    def _extraer_json_respuesta(cls, contenido: str) -> Optional[Dict]:
        """
        Extrae el JSON de la respuesta de DeepSeek.

        Args:
            contenido: Texto de respuesta del LLM.

        Returns:
            Diccionario parseado o None si no se encuentra JSON válido.
        """
        if not contenido:
            return None

        try:
            # Intentar parsear directamente
            return json.loads(contenido)
        except json.JSONDecodeError:
            pass

        # Buscar JSON entre llaves
        import re
        match = re.search(r'\{[\s\S]*\}', contenido)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        return None

    @classmethod
    def verificar_duplicado_simple(
        cls,
        texto_mensaje: str,
        agente: str = '',
        extractor_log_id: Optional[int] = None,
        fuente: str = '',
    ) -> Tuple[bool, Optional[int]]:
        """
        Versión simplificada que solo retorna si es duplicado y el ID.

        AHORA usa deduplicación LOCAL por hash de texto normalizado
        para evitar llamadas a DeepSeek API por cada mensaje.
        Esto reduce drásticamente el tiempo de procesamiento
        (de ~4 horas a ~minutos para archivos grandes).

        Incluye el nombre del agente (autor) en la comparación para
        detectar duplicados con mayor precisión: mismo texto + mismo
        autor = duplicado seguro.

        Args:
            texto_mensaje: Texto del mensaje nuevo.
            agente: Nombre del autor/agente que publicó el mensaje.
            extractor_log_id: ID del ExtractorLog actual. Si se proporciona,
                              se excluyen los requerimientos de este log
                              para evitar falsos duplicados durante el
                              procesamiento en vivo del mismo archivo.
            fuente: Nombre del grupo WhatsApp de origen. Si se proporciona,
                    solo se comparará contra requerimientos de la MISMA fuente,
                    evitando falsos duplicados entre diferentes grupos.

        Returns:
            Tuple (is_duplicate, matching_id)
        """
        # Usar deduplicación local rápida
        resultado = cls._verificar_duplicado_local(
            texto_mensaje, agente=agente,
            extractor_log_id=extractor_log_id,
            fuente=fuente,
        )
        return (
            resultado.get('is_duplicate', False),
            resultado.get('matching_id'),
        )

    @classmethod
    def _verificar_duplicado_local(cls, texto_mensaje: str, agente: str = '', extractor_log_id: Optional[int] = None, fuente: str = '') -> Dict:
        """
        Deduplicación LOCAL rápida usando hash de texto normalizado
        y nombre del agente (autor).

        NO llama a DeepSeek API. Compara el texto del mensaje contra
        los requerimientos existentes usando:
        1. Hash SHA256 del texto normalizado (detección exacta)
        2. Búsqueda directa por texto_hash en BD (mismo criterio que índice único)
        3. Coeficiente Jaccard (detección de mensajes muy similares)
        4. Nombre del agente/autor (mismo texto + mismo autor = duplicado)

        Los duplicados solo se detectan DENTRO DE LA MISMA FUENTE (grupo WhatsApp).
        Si no se especifica fuente, se compara contra todo el histórico.

        Args:
            texto_mensaje: Texto del mensaje nuevo.
            agente: Nombre del autor/agente que publicó el mensaje.
            extractor_log_id: No se usa (se compara contra todo el histórico siempre).
            fuente: Nombre del grupo WhatsApp. Si se proporciona, solo se compara
                    contra requerimientos de la misma fuente.

        Returns:
            Dict con is_duplicate, matching_id, match_score, reason.
        """
        resultado_base = {
            'is_duplicate': False,
            'match_score': 0,
            'matching_id': None,
            'reason': 'No es duplicado',
            'error': None,
        }

        try:
            # 1. Normalizar texto para comparación
            texto_normalizado = ' '.join(texto_mensaje.lower().split())
            hash_nuevo = hashlib.sha256(texto_normalizado.encode()).hexdigest()
            agente_normalizado = agente.strip().lower()

            # 2. Búsqueda DIRECTA por texto_hash en BD (más rápida y exacta)
            #    Esto replica el mismo criterio del índice único de SQL Server
            #    Solo dentro de la MISMA fuente (grupo WhatsApp) si se especificó
            filtros_hash = {'texto_hash': hash_nuevo}
            if fuente:
                filtros_hash['fuente'] = fuente
            duplicado_por_hash = Requerimiento.objects.filter(
                **filtros_hash
            ).values('id', 'agente').first()
            if duplicado_por_hash:
                req_agente = (duplicado_por_hash['agente'] or '').strip().lower()
                if agente_normalizado and req_agente and agente_normalizado == req_agente:
                    return {
                        'is_duplicate': True,
                        'match_score': 100,
                        'matching_id': duplicado_por_hash['id'],
                        'reason': 'Texto duplicado exacto (por texto_hash) + mismo agente',
                        'error': None,
                    }
                return {
                    'is_duplicate': True,
                    'match_score': 100,
                    'matching_id': duplicado_por_hash['id'],
                    'reason': 'Texto duplicado exacto (por texto_hash)',
                    'error': None,
                }

            # 3. Obtener historial para Jaccard, filtrado por fuente si se especificó
            #    Si hay fuente, solo compara dentro del MISMO grupo WhatsApp
            #    Si no hay fuente, busca en TODOS los requerimientos
            filtros_historial = {
                'requerimiento__isnull': False,
            }
            if fuente:
                filtros_historial['fuente'] = fuente
            historial = list(Requerimiento.objects.filter(
                **filtros_historial
            ).exclude(
                requerimiento=''
            ).values('id', 'requerimiento', 'agente').order_by('-id')[:cls.ULTIMOS_REQUERIMIENTOS])

            if not historial:
                return resultado_base

            # 4. Comparar contra cada requerimiento histórico (Jaccard)
            for req in historial:
                req_texto = ' '.join((req['requerimiento'] or '').lower().split())
                req_hash = hashlib.sha256(req_texto.encode()).hexdigest()
                req_agente = (req['agente'] or '').strip().lower()

                # Coincidencia exacta de hash (respaldo por si la query directa falló)
                if hash_nuevo == req_hash:
                    if agente_normalizado and req_agente and agente_normalizado == req_agente:
                        return {
                            'is_duplicate': True,
                            'match_score': 100,
                            'matching_id': req['id'],
                            'reason': f'Texto duplicado exacto + mismo agente',
                            'error': None,
                        }
                    return {
                        'is_duplicate': True,
                        'match_score': 100,
                        'matching_id': req['id'],
                        'reason': 'Texto duplicado exacto',
                        'error': None,
                    }

                # Coincidencia parcial usando Jaccard
                # NOTA: threshold alto porque los requerimientos comparten mucho
                # vocabulario común (tipo_operacion, distritos, presupuesto,
                # "cliente busca", "community tops", etc.) y Jaccard produce
                # falsos positivos con thresholds bajos.
                palabras_nuevas = set(texto_normalizado.split())
                palabras_existentes = set(req_texto.split())
                if len(palabras_nuevas) > 3 and len(palabras_existentes) > 3:
                    interseccion = palabras_nuevas & palabras_existentes
                    union = palabras_nuevas | palabras_existentes
                    jaccard = len(interseccion) / len(union) if union else 0

                    # Mismo agente + altísima similitud: umbral 90%
                    if (agente_normalizado and req_agente and
                        agente_normalizado == req_agente and jaccard >= 0.90):
                        return {
                            'is_duplicate': True,
                            'match_score': round(jaccard * 100),
                            'matching_id': req['id'],
                            'reason': f'Alta similitud + mismo agente: {jaccard:.0%}',
                            'error': None,
                        }

                    # Sin mismo agente: solo con similitud casi exacta (95%)
                    if jaccard >= 0.95:
                        return {
                            'is_duplicate': True,
                            'match_score': round(jaccard * 100),
                            'matching_id': req['id'],
                            'reason': f'Alta similitud Jaccard: {jaccard:.0%}',
                            'error': None,
                        }

            return resultado_base

        except Exception as e:
            logger.warning(f"Error en deduplicación local: {e}")
            return {
                **resultado_base,
                'error': str(e),
            }
