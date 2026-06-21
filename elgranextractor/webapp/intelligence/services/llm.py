"""
Servicio LLM integrado con RAG para generación de respuestas enriquecidas con contexto.

Este módulo integra el sistema RAG con DeepSeek API para proporcionar respuestas
enriquecidas con información contextual de propiedades, noticias y datos del mercado.

Integración con Skills:
- extract_skill_params(): extrae parámetros estructurados del mensaje del usuario
  usando el schema de una skill, para alimentar la ejecución de la skill.
- generate_rag_response(): modificado para consultar primero el SkillRegistry
  y ejecutar la skill adecuada antes de caer en RAG puro.
"""

import os
import json
import re
import logging
import time
import inspect
from typing import Dict, List, Optional, Tuple, Any, Generator
from datetime import datetime

import requests
from django.conf import settings
from django.utils import timezone

from .rag import RAGService
from ..models import IntelligenceCollection, AIConsumptionLog
from ..skills.registry import SkillRegistry
from ..skills.base import SkillResult

logger = logging.getLogger(__name__)


class LLMService:
    """
    Servicio para integración con LLM (DeepSeek) y RAG.
    
    Proporciona:
    1. Generación de respuestas enriquecidas con contexto RAG
    2. Extracción estructurada de información
    3. Análisis de consultas y routing a colecciones apropiadas
    """
    
    # Configuración de DeepSeek API
    DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
    DEEPSEEK_MODEL = "deepseek-chat"
    
    # Configuración desde variables de entorno
    API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
    MAX_TOKENS = int(os.environ.get('DEEPSEEK_MAX_TOKENS', 2000))
    TEMPERATURE = float(os.environ.get('DEEPSEEK_TEMPERATURE', 0.1))
    
    # Límites de contexto RAG
    MAX_RAG_CONTEXT_DOCUMENTS = int(os.environ.get('MAX_RAG_CONTEXT_DOCUMENTS', 5))
    MIN_SIMILARITY_THRESHOLD = float(os.environ.get('MIN_SIMILARITY_THRESHOLD', 0.6))
    
    @classmethod
    def _get_headers(cls) -> Dict[str, str]:
        """Obtiene headers para la API de DeepSeek."""
        return {
            "Authorization": f"Bearer {cls.API_KEY}",
            "Content-Type": "application/json"
        }
    
    @classmethod
    def _call_deepseek_api(
        cls,
        messages: List[Dict[str, str]],
        system_prompt: str = "",
        stream: bool = False,
        caller_app: str = "",
        endpoint: str = ""
    ) -> Tuple[bool, str, Optional[Dict]]:
        """
        Llama a la API de DeepSeek.
        
        Args:
            messages: Lista de mensajes en formato OpenAI
            system_prompt: Prompt del sistema (opcional)
            stream: Si es True, devuelve un generador de streaming
            caller_app: App Django que origina la llamada (para logging)
            endpoint: Endpoint o función que llamó a la API (para logging)
            
        Returns:
            Tuple (success, message, response_data) o generador para streaming
        """
        if not cls.API_KEY:
            return False, "API key de DeepSeek no configurada", None
        
        # ── Auto-detección de caller_app y endpoint ──
        if not caller_app or not endpoint:
            try:
                stack = inspect.stack()
                # stack[0] = _call_deepseek_api, stack[1] = método público que llama
                # stack[2] = quien llamó al método público
                for frame_info in stack[2:]:
                    frame = frame_info.frame
                    module = inspect.getmodule(frame)
                    if module and module.__file__:
                        fpath = module.__file__.replace('\\', '/')
                        # Detectar app por la ruta del archivo
                        if 'intelligence/services/' in fpath:
                            caller_app = 'intelligence.services'
                            endpoint = frame_info.function
                            break
                        elif 'intelligence/skills/' in fpath:
                            caller_app = f'intelligence.skills.{frame_info.function}'
                            endpoint = frame_info.function
                            break
                        elif 'intelligence/views.py' in fpath:
                            caller_app = 'intelligence.views'
                            endpoint = frame_info.function
                            break
                        elif 'whatsapp_extractor/' in fpath:
                            caller_app = 'whatsapp_extractor'
                            endpoint = frame_info.function
                            break
                        elif 'ingestas/' in fpath:
                            caller_app = 'ingestas'
                            endpoint = frame_info.function
                            break
                        elif 'chat_processor' in fpath:
                            caller_app = 'intelligence.chat_processor'
                            endpoint = frame_info.function
                            break
                        elif 'episodic_memory' in fpath:
                            caller_app = 'intelligence.episodic_memory'
                            endpoint = frame_info.function
                            break
                        elif 'memory' in fpath:
                            caller_app = 'intelligence.memory'
                            endpoint = frame_info.function
                            break
                    del frame
                del stack
            except Exception:
                pass
        
        # Preparar mensajes con system prompt si se proporciona
        api_messages = []
        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})
        api_messages.extend(messages)
        
        payload = {
            "model": cls.DEEPSEEK_MODEL,
            "messages": api_messages,
            "temperature": cls.TEMPERATURE,
            "max_tokens": cls.MAX_TOKENS,
            "stream": stream
        }
        
        start_time = time.time()
        
        try:
            logger.info(f"Llamando a DeepSeek API con {len(messages)} mensajes, stream={stream}")
            
            if stream:
                # Para streaming, devolvemos el response directamente
                response = requests.post(
                    cls.DEEPSEEK_API_URL,
                    headers=cls._get_headers(),
                    json=payload,
                    timeout=60,
                    stream=True
                )
                
                duration_ms = int((time.time() - start_time) * 1000)
                
                if response.status_code != 200:
                    logger.error(f"Error API DeepSeek (streaming): {response.status_code} - {response.text}")
                    # Registrar consumo fallido
                    try:
                        AIConsumptionLog.registrar_llamada(
                            model_name=cls.DEEPSEEK_MODEL,
                            endpoint=endpoint or 'stream',
                            caller_app=caller_app,
                            duration_ms=duration_ms,
                            success=False,
                            status_code=response.status_code,
                            error_message=response.text[:500],
                        )
                    except Exception as log_err:
                        logger.warning(f"No se pudo registrar consumo IA: {log_err}")
                    return False, f"Error API: {response.status_code}", None
                
                # Registrar consumo exitoso (sin datos de tokens porque streaming no los devuelve)
                try:
                    AIConsumptionLog.registrar_llamada(
                        model_name=cls.DEEPSEEK_MODEL,
                        endpoint=endpoint or 'stream',
                        caller_app=caller_app,
                        duration_ms=duration_ms,
                        success=True,
                        status_code=response.status_code,
                    )
                except Exception as log_err:
                    logger.warning(f"No se pudo registrar consumo IA: {log_err}")
                
                # Devolvemos el response para que el llamador pueda procesar el streaming
                return True, "OK", {"stream_response": response}
            
            else:
                # Modo normal (no streaming)
                response = requests.post(
                    cls.DEEPSEEK_API_URL,
                    headers=cls._get_headers(),
                    json=payload,
                    timeout=30
                )
                
                duration_ms = int((time.time() - start_time) * 1000)
                
                if response.status_code != 200:
                    logger.error(f"Error API DeepSeek: {response.status_code} - {response.text}")
                    # Registrar consumo fallido
                    try:
                        AIConsumptionLog.registrar_llamada(
                            model_name=cls.DEEPSEEK_MODEL,
                            endpoint=endpoint or 'unknown',
                            caller_app=caller_app,
                            duration_ms=duration_ms,
                            success=False,
                            status_code=response.status_code,
                            error_message=response.text[:500],
                        )
                    except Exception as log_err:
                        logger.warning(f"No se pudo registrar consumo IA: {log_err}")
                    return False, f"Error API: {response.status_code}", None
                
                data = response.json()
                # Proteger contra respuestas inesperadas de la API
                choices = data.get("choices", [{}])
                prompt_tokens = data.get("usage", {}).get("prompt_tokens", 0)
                completion_tokens = data.get("usage", {}).get("completion_tokens", 0)
                total_tokens = data.get("usage", {}).get("total_tokens", 0)
                
                if choices and isinstance(choices, list) and len(choices) > 0:
                    first_choice = choices[0]
                    if isinstance(first_choice, dict):
                        content = first_choice.get("message", {}).get("content", "")
                    else:
                        logger.error(f"Formato inesperado en choices[0]: type={type(first_choice)}")
                        content = ""
                else:
                    content = ""
                
                if not content:
                    # Registrar consumo con datos parciales
                    try:
                        AIConsumptionLog.registrar_llamada(
                            model_name=cls.DEEPSEEK_MODEL,
                            endpoint=endpoint or 'unknown',
                            caller_app=caller_app,
                            prompt_tokens=prompt_tokens,
                            completion_tokens=completion_tokens,
                            total_tokens=total_tokens,
                            duration_ms=duration_ms,
                            success=False,
                            status_code=response.status_code,
                            error_message="Respuesta vacía de la API",
                        )
                    except Exception as log_err:
                        logger.warning(f"No se pudo registrar consumo IA: {log_err}")
                    return False, "Respuesta vacía de la API", None
                
                # Registrar consumo exitoso con datos de tokens
                try:
                    AIConsumptionLog.registrar_llamada(
                        model_name=cls.DEEPSEEK_MODEL,
                        endpoint=endpoint or 'unknown',
                        caller_app=caller_app,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=total_tokens,
                        duration_ms=duration_ms,
                        success=True,
                        status_code=response.status_code,
                    )
                except Exception as log_err:
                    logger.warning(f"No se pudo registrar consumo IA: {log_err}")
                
                logger.info(
                    f"Respuesta DeepSeek recibida ({len(content)} caracteres, "
                    f"{total_tokens} tokens, {duration_ms}ms)"
                )
                return True, "OK", {"content": content, "raw_response": data}
            
        except requests.exceptions.Timeout:
            duration_ms = int((time.time() - start_time) * 1000)
            try:
                AIConsumptionLog.registrar_llamada(
                    model_name=cls.DEEPSEEK_MODEL,
                    endpoint=endpoint or 'unknown',
                    caller_app=caller_app,
                    duration_ms=duration_ms,
                    success=False,
                    error_message="Timeout en la llamada a la API",
                )
            except Exception as log_err:
                logger.warning(f"No se pudo registrar consumo IA: {log_err}")
            logger.error("Timeout llamando a DeepSeek API")
            return False, "Timeout en la llamada a la API", None
        except requests.exceptions.RequestException as e:
            duration_ms = int((time.time() - start_time) * 1000)
            try:
                AIConsumptionLog.registrar_llamada(
                    model_name=cls.DEEPSEEK_MODEL,
                    endpoint=endpoint or 'unknown',
                    caller_app=caller_app,
                    duration_ms=duration_ms,
                    success=False,
                    error_message=f"Error de conexión: {str(e)[:500]}",
                )
            except Exception as log_err:
                logger.warning(f"No se pudo registrar consumo IA: {log_err}")
            logger.error(f"Error de conexión con DeepSeek API: {e}")
            return False, f"Error de conexión: {str(e)}", None
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            try:
                AIConsumptionLog.registrar_llamada(
                    model_name=cls.DEEPSEEK_MODEL,
                    endpoint=endpoint or 'unknown',
                    caller_app=caller_app,
                    duration_ms=duration_ms,
                    success=False,
                    error_message=f"Error inesperado: {str(e)[:500]}",
                )
            except Exception as log_err:
                logger.warning(f"No se pudo registrar consumo IA: {log_err}")
            logger.error(f"Error inesperado llamando a DeepSeek API: {e}")
            return False, f"Error inesperado: {str(e)}", None
    
    @classmethod
    def _extract_json_from_response(cls, content: str) -> Optional[Dict]:
        """
        Extrae JSON de la respuesta del LLM.
        
        Args:
            content: Texto de respuesta del LLM
            
        Returns:
            Diccionario JSON extraído o None si no se encuentra
        """
        try:
            # Buscar JSON en la respuesta
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                return json.loads(json_match.group())
        except (json.JSONDecodeError, re.error) as e:
            logger.warning(f"Error extrayendo JSON de respuesta: {e}")
        
        return None
    
    @classmethod
    def _build_rag_context(
        cls,
        query: str,
        user_access_level: int = 1,
        collection_names: Optional[List[str]] = None
    ) -> Tuple[str, List[Dict]]:
        """
        Construye contexto RAG para una consulta.
        Usa search_dynamic para compatibilidad con field_values (colecciones dinámicas).
        
        Args:
            query: Consulta del usuario
            user_access_level: Nivel de acceso del usuario
            collection_names: Nombres específicos de colecciones (None = todas)
            
        Returns:
            Tuple (context_text, retrieved_documents)
        """
        if not collection_names:
            # Si no se especifican colecciones, buscar en todas las activas
            collections = IntelligenceCollection.objects.filter(
                is_active=True,
                min_level__lte=user_access_level
            )
            collection_names = list(collections.values_list('name', flat=True))
        
        if not collection_names:
            logger.info("No hay colecciones disponibles para búsqueda")
            return "", []
        
        # Usar search_dynamic que es compatible con field_values
        results = RAGService.search_dynamic(
            query=query,
            collection_names=collection_names,
            top_k=cls.MAX_RAG_CONTEXT_DOCUMENTS
        )
        
        if not results:
            logger.info(f"No se encontraron documentos RAG para la consulta: {query}")
            return "", []
        
        # Construir texto de contexto
        context_parts = []
        for i, doc in enumerate(results, 1):
            collection_name = doc.get('collection_name', 'Desconocida')
            similarity = doc.get('similarity', 0)
            field_values = doc.get('field_values', {})
            
            # Formatear información según el tipo de colección
            if 'propiedades' in collection_name.lower() or 'propifai' in collection_name.lower():
                # Mapeo de nombres de campo (inglés de BD → español para el prompt)
                titulo = field_values.get('title') or field_values.get('titulo', 'Sin título')
                descripcion = field_values.get('description') or field_values.get('descripcion', 'Sin descripción')
                direccion = field_values.get('map_address') or field_values.get('display_address') or field_values.get('real_address') or field_values.get('exact_address') or field_values.get('direccion', 'Sin dirección')
                distrito = field_values.get('district_name') or field_values.get('district') or field_values.get('distrito', 'Sin distrito')
                precio = field_values.get('price') or field_values.get('precio', 'N/A')
                moneda = field_values.get('currency_name') or field_values.get('currency_id') or field_values.get('moneda', '')
                area_construida = field_values.get('built_area') or field_values.get('area_construida', 'N/A')
                tipo = field_values.get('property_type_name') or field_values.get('property_type_id') or field_values.get('tipo_propiedad', 'Sin tipo')
                habitaciones = field_values.get('bedrooms', 'N/A')
                banos = field_values.get('bathrooms', 'N/A')
                terreno = field_values.get('land_area', 'N/A')
                estado = field_values.get('property_status_name') or field_values.get('property_condition_name') or ''
                
                context_parts.append(
                    f"[Documento {i} - Propiedad - Similitud: {similarity:.2f}]\n"
                    f"Título: {titulo}\n"
                    f"Descripción: {descripcion}\n"
                    f"Dirección: {direccion}\n"
                    f"Distrito: {distrito}\n"
                    f"Tipo: {tipo}\n"
                    f"Precio: {precio} {moneda}\n"
                    f"Área construida: {area_construida} m²\n"
                    f"Habitaciones: {habitaciones}\n"
                    f"Baños: {banos}\n"
                    f"Área de terreno: {terreno} m²\n"
                    + (f"Estado: {estado}\n" if estado else "")
                )
            elif 'noticias' in collection_name.lower():
                # Información de noticia
                context_parts.append(
                    f"[Documento {i} - Noticia - Similitud: {similarity:.2f}]\n"
                    f"Título: {field_values.get('titulo', 'Sin título')}\n"
                    f"Contenido: {field_values.get('contenido', 'Sin contenido')[:500]}...\n"
                    f"Fuente: {field_values.get('fuente', 'Desconocida')}\n"
                    f"Fecha: {field_values.get('fecha_publicacion', 'Desconocida')}\n"
                )
            else:
                # Documento genérico
                context_parts.append(
                    f"[Documento {i} - {collection_name} - Similitud: {similarity:.2f}]\n"
                    f"Contenido: {doc.get('content', 'Sin contenido')}\n"
                )
        
        context_text = "\n\n".join(context_parts)
        logger.info(f"Contexto RAG construido con {len(results)} documentos")
        
        return context_text, results
    
    @classmethod
    def extract_skill_params(
        cls,
        message: str,
        parameters_schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extrae parámetros estructurados del mensaje del usuario usando el LLM.

        Usa DeepSeek para analizar el mensaje en lenguaje natural y extraer
        los valores correspondientes al schema de parámetros de una skill.

        Args:
            message: Mensaje del usuario en lenguaje natural
            parameters_schema: Schema de parámetros de la skill (ver BaseSkill.parameters_schema)

        Returns:
            Dict con los parámetros extraídos (solo los que se encontraron en el mensaje)
        """
        if not message or not message.strip():
            return {}

        # Construir descripción de campos para el prompt
        campos_desc = []
        for param_name, param_info in parameters_schema.items():
            req = "REQUERIDO" if param_info.get('required') else "OPCIONAL"
            tipo = param_info.get('type', 'string')
            desc = param_info.get('description', '')
            campos_desc.append(f"- {param_name} ({tipo}, {req}): {desc}")

        campos_str = "\n".join(campos_desc)

        system_prompt = f"""Eres un extractor de parámetros para búsqueda de propiedades inmobiliarias.

Analiza el mensaje del usuario y extrae SOLO los parámetros que están explícitamente mencionados.

CAMPOS A EXTRAER:
{campos_str}

REGLAS DE EXTRACCIÓN:
1. Extrae SOLO lo que el usuario menciona explícitamente. No inventes valores.
2. Normaliza tipos de propiedad: "depa"/"dpto"/"departamento" → "Departamento", "casa"/"vivienda" → "Casa", "terreno"/"lote" → "Terreno"
3. Normaliza distritos: primera letra mayúscula, tildes correctas. Ej: "cayma" → "Cayma"
4. Precios: "80 mil" → 80000, "1.2 millones" → 1200000. Detecta si es USD o PEN.
5. semantic_query: TODO lo que sea subjetivo o descriptivo que NO sea un filtro exacto.
   Ej: "amplio", "luminoso", "cerca de parques", "buena zona", "acogedor"
6. Si el usuario menciona "amplios ambientes" o similar, ponerlo en semantic_query.
7. condicion: Si el usuario menciona "vendidas"/"vendido" → "Vendida". Si menciona "reservadas"/"reservado" → "Reservada". Si menciona "disponibles"/"en venta" → "Disponible". Por defecto NO extraer este campo (la skill asume Disponible automáticamente).
8. Si el usuario pregunta por propiedades en general sin filtros específicos, NO extraer nada.

Responde SOLO con un objeto JSON válido. Si no hay parámetros extraíbles, responde {{}}."""

        messages = [
            {"role": "user", "content": f"Mensaje del usuario: {message}"}
        ]

        try:
            success, api_message, api_response = cls._call_deepseek_api(
                messages=messages,
                system_prompt=system_prompt
            )

            if not success:
                logger.warning(f"Error extrayendo parámetros de skill: {api_message}")
                return {}

            # Extraer JSON de la respuesta
            extracted = cls._extract_json_from_response(api_response["content"])

            if not extracted:
                logger.warning("No se pudo extraer JSON de la respuesta de extracción de parámetros")
                return {}

            # Limpiar: remover claves con None o vacío
            cleaned = {
                k: v for k, v in extracted.items()
                if v is not None and v != '' and v != []
            }

            # ── Fallback: si no se extrajo nada, reintentar con prompt simplificado ──
            if not cleaned:
                logger.info(
                    "[extract_skill_params] Fallback: sin parámetros en primer intento, "
                    "reintentando con prompt simplificado"
                )
                simplified_prompt = (
                    "Extrae del siguiente mensaje del usuario SOLO estos campos "
                    "si aparecen explícitamente:\n"
                    "- distrito: nombre del distrito (ej: Cayma, Yanahuara, Cercado)\n"
                    "- tipo_propiedad: tipo (Departamento, Casa, Terreno, "
                    "Local Comercial, Oficina)\n"
                    "- operacion: tipo de operación (venta, alquiler)\n\n"
                    "Si el usuario pregunta por propiedades en general sin filtros "
                    "específicos, responde SOLO con un JSON vacío: {}\n\n"
                    "NO agregues explicaciones. SOLO responde con el JSON.\n\n"
                    f"Mensaje: {message}"
                )
                success2, _, content2 = cls._call_deepseek_api(
                    messages=[{"role": "user", "content": message}],
                    system_prompt=simplified_prompt,
                )
                if success2 and content2:
                    # content2 es un dict con 'content' si es respuesta normal
                    response_content = content2.get('content', '') if isinstance(content2, dict) else str(content2)
                    extracted2 = cls._extract_json_from_response(response_content)
                    if extracted2:
                        cleaned = {
                            k: v for k, v in extracted2.items()
                            if v is not None and v != '' and v != []
                        }
                        logger.info(
                            f"[extract_skill_params] Fallback exitoso: {cleaned}"
                        )

            logger.info(
                f"Parámetros extraídos para skill: {cleaned}"
            )
            return cleaned

        except Exception as e:
            logger.error(f"Error en extract_skill_params: {e}")
            return {}

    @classmethod
    def generate_rag_response(
        cls,
        query: str,
        conversation_history: Optional[List[Dict]] = None,
        user_access_level: int = 1,
        collection_names: Optional[List[str]] = None,
        include_sources: bool = True
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Genera una respuesta enriquecida con contexto RAG o ejecutando una skill.

        Flujo:
        1. Consultar SkillRegistry.find_best_skill(intent, user_level)
        2a. Si hay skill → extract_skill_params() → skill.execute()
        2b. Si no hay skill → _build_rag_context() como antes
        3. LLM formatea la respuesta con el SkillResult o el contexto RAG

        Args:
            query: Consulta del usuario
            conversation_history: Historial de conversación (opcional)
            user_access_level: Nivel de acceso del usuario
            collection_names: Nombres específicos de colecciones
            include_sources: Si incluir referencias a fuentes

        Returns:
            Tuple (success, message, response_data)
        """
        logger.info(f"Generando respuesta RAG para: '{query}' (nivel: {user_access_level})")

        # ── 1. Intentar ejecutar skill ──
        registry = SkillRegistry()
        best_skill = registry.find_best_skill(query, user_level=user_access_level)

        skill_result: Optional[SkillResult] = None
        rag_context = ""
        retrieved_docs = []

        if best_skill:
            logger.info(f"Skill seleccionada: '{best_skill.name}' para query: '{query}'")

            # Extraer parámetros del mensaje usando el schema de la skill
            params = cls.extract_skill_params(query, best_skill.parameters_schema)

            if best_skill.validate_params(params):
                # Ejecutar skill con contexto del usuario
                skill_result = best_skill.execute(
                    params=params,
                    context={'user_level': user_access_level}
                )

                if skill_result.success:
                    logger.info(
                        f"Skill '{best_skill.name}' ejecutada exitosamente: "
                        f"{skill_result.message}"
                    )
                else:
                    logger.warning(
                        f"Skill '{best_skill.name}' falló: {skill_result.message}"
                    )
            else:
                logger.info(
                    f"Parámetros insuficientes para skill '{best_skill.name}'. "
                    f"Usando RAG puro."
                )

        # ── 2a. Si hay resultado de skill, construir prompt con ese resultado ──
        if skill_result and skill_result.success:
            # Construir contexto a partir del resultado de la skill
            skill_context = cls._format_skill_context(skill_result)

            messages = []
            if conversation_history:
                for msg in conversation_history[-6:]:
                    messages.append(msg)

            system_prompt = cls._build_skill_system_prompt(skill_result, skill_context)

            user_message = f"Consulta del usuario: {query}"
            messages.append({"role": "user", "content": user_message})

            success, api_message, api_response = cls._call_deepseek_api(
                messages=messages,
                system_prompt=system_prompt
            )

            if not success:
                return False, api_message, {}

            response_content = api_response["content"]

            response_data = {
                "query": query,
                "response": response_content,
                "timestamp": timezone.now().isoformat(),
                "skill_used": skill_result.skill_name,
                "skill_result": {
                    "success": skill_result.success,
                    "message": skill_result.message,
                    "metadata": skill_result.metadata,
                    "total_resultados": len(skill_result.data) if isinstance(skill_result.data, list) else 0,
                },
                "rag_context_used": False,
                "retrieved_documents_count": 0
            }

            logger.info(
                f"Respuesta generada vía skill '{skill_result.skill_name}' "
                f"({len(response_content)} caracteres)"
            )
            return True, "Respuesta generada exitosamente", response_data

        # ── 2b. RAG puro (sin skill) ──
        rag_context, retrieved_docs = cls._build_rag_context(
            query=query,
            user_access_level=user_access_level,
            collection_names=collection_names
        )

        messages = []

        if conversation_history:
            for msg in conversation_history[-6:]:
                messages.append(msg)

        system_prompt = """Eres Propifai Assistant, un experto asistente inmobiliario especializado en el mercado de Arequipa, Perú.

Tu conocimiento incluye:
- Propiedades disponibles (propias y de competencia)
- Noticias y análisis del mercado inmobiliario
- Información sobre zonas, precios y tendencias

INSTRUCCIONES CRÍTICAS:
1. Usa EXCLUSIVAMENTE la información del CONTEXTO DISPONIBLE para responder.
2. SIEMPRE que el contexto contenga propiedades, responde con la información real: precios, distritos, tipos, áreas.
3. NUNCA digas que no tienes información si el contexto SÍ contiene datos relevantes.
4. Sé preciso con precios, ubicaciones y características.
5. Para propiedades, menciona siempre: precio, ubicación (distrito), tipo de propiedad y características principales.
6. Para noticias, menciona la fuente y fecha si están disponibles.
7. Responde en español claro y profesional.
8. Si se te pide comparar o analizar, usa solo los datos del contexto.

CONTEXTO DISPONIBLE:"""

        if rag_context:
            system_prompt += f"\n\n{rag_context}"
        else:
            system_prompt += "\n\nNo hay información específica disponible en este momento."

        user_message = f"Consulta del usuario: {query}"
        messages.append({"role": "user", "content": user_message})

        success, api_message, api_response = cls._call_deepseek_api(
            messages=messages,
            system_prompt=system_prompt
        )

        if not success:
            return False, api_message, {}

        response_content = api_response["content"]

        response_data = {
            "query": query,
            "response": response_content,
            "timestamp": timezone.now().isoformat(),
            "rag_context_used": bool(rag_context),
            "retrieved_documents_count": len(retrieved_docs)
        }

        if include_sources and retrieved_docs:
            sources = []
            for doc in retrieved_docs:
                sources.append({
                    "collection": doc.get("collection_name"),
                    "similarity": doc.get("similarity"),
                    "metadata": doc.get("metadata", {})
                })
            response_data["sources"] = sources

        logger.info(f"Respuesta RAG generada exitosamente ({len(response_content)} caracteres)")
        return True, "Respuesta generada exitosamente", response_data

    @classmethod
    def _format_skill_context(cls, skill_result: SkillResult) -> str:
        """
        Formatea el resultado de una skill como contexto para el LLM.

        Convierte los datos estructurados de la skill en texto legible
        para que el LLM lo use en su respuesta.
        """
        if not skill_result.data:
            return skill_result.message

        data = skill_result.data
        if isinstance(data, list):
            partes = []
            for i, item in enumerate(data, 1):
                field_values = item.get('field_values', {})
                if field_values:
                    titulo = field_values.get('title') or field_values.get('titulo', 'Sin título')
                    distrito = field_values.get('district_name') or field_values.get('distrito', 'Sin distrito')
                    precio = field_values.get('price') or field_values.get('precio', 'N/A')
                    moneda = field_values.get('currency_name') or field_values.get('currency_id', '')
                    tipo = field_values.get('property_type_name') or field_values.get('property_type_id') or field_values.get('tipo_propiedad', 'Sin tipo')
                    habitaciones = field_values.get('bedrooms', 'N/A')
                    banos = field_values.get('bathrooms', 'N/A')
                    area = field_values.get('built_area') or field_values.get('area_construida', 'N/A')
                    descripcion = field_values.get('description') or field_values.get('descripcion', '')
                    operacion = field_values.get('operation_type_name') or field_values.get('operation_type_id', '')
                    estado = field_values.get('property_status_name') or field_values.get('property_condition_name', '')

                    partes.append(
                        f"[Propiedad {i}]\n"
                        f"Título: {titulo}\n"
                        f"Descripción: {descripcion}\n"
                        f"Distrito: {distrito}\n"
                        f"Tipo: {tipo}\n"
                        f"Precio: {precio} {moneda}\n"
                        f"Área construida: {area} m²\n"
                        f"Habitaciones: {habitaciones}\n"
                        f"Baños: {banos}\n"
                        + (f"Operación: {operacion}\n" if operacion else "")
                        + (f"Estado: {estado}\n" if estado else "")
                    )
            return "\n\n".join(partes)

        return str(data)

    @classmethod
    def _build_skill_system_prompt(cls, skill_result: SkillResult, skill_context: str) -> str:
        """
        Construye el system prompt cuando se usó una skill.

        Incluye el contexto de la skill y metadatos para que el LLM
        pueda responder con precisión.
        """
        modo = skill_result.metadata.get('modo', 'desconocido')
        total = skill_result.metadata.get('total_encontrados_sql', 0)
        filtros = skill_result.metadata.get('filtros_aplicados', {})

        prompt = f"""Eres Propifai Assistant, un experto asistente inmobiliario especializado en el mercado de Arequipa, Perú.

Has ejecutado una búsqueda de propiedades con los siguientes detalles:
- Modo de búsqueda: {modo}
- Total de propiedades encontradas: {total}
- Filtros aplicados: {json.dumps(filtros, ensure_ascii=False)}

INSTRUCCIONES CRÍTICAS:
1. Usa EXCLUSIVAMENTE la información de las propiedades listadas abajo para responder.
2. Responde en español claro y profesional.
3. Para cada propiedad, menciona: título, precio, ubicación (distrito), tipo y características principales.
4. Si no hay propiedades en los resultados, indícalo claramente al usuario.
5. Si el usuario preguntó por un distrito específico y hay propiedades de ese distrito, resáltalo.
6. NUNCA inventes propiedades que no estén en la lista.
7. Sé preciso con precios y características.

RESULTADOS DE LA BÚSQUEDA:
{skill_context}"""

        return prompt
    
    @classmethod
    def analyze_query_intent(
        cls,
        query: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Analiza la intención de una consulta para determinar qué colecciones buscar.
        
        Args:
            query: Consulta del usuario
            
        Returns:
            Tuple (success, message, intent_data)
        """
        system_prompt = """Eres un clasificador de intenciones para consultas inmobiliarias.

Analiza la consulta del usuario y determina:
1. Tipo de información solicitada (propiedades, noticias, datos de mercado, general)
2. Colecciones RAG relevantes (propiedades_propifai, propiedades_competencia, noticias_mercado)
3. Parámetros de búsqueda sugeridos

Responde SOLO con un objeto JSON en este formato:
{
  "intent": "propiedades|noticias|mercado|general",
  "collections": ["propiedades_propifai", "propiedades_competencia", "noticias_mercado"],
  "parameters": {
    "property_type": "Departamento|Casa|Terreno|Local|Oficina",
    "location": "Distrito o zona",
    "budget_min": número o null,
    "budget_max": número o null,
    "currency": "PEN|USD"
  },
  "confidence": 0.0 a 1.0
}"""
        
        messages = [
            {"role": "user", "content": f"Consulta: {query}"}
        ]
        
        success, api_message, api_response = cls._call_deepseek_api(
            messages=messages,
            system_prompt=system_prompt
        )
        
        if not success:
            return False, api_message, {}
        
        # Extraer JSON de la respuesta
        intent_data = cls._extract_json_from_response(api_response["content"])
        
        if not intent_data:
            # Datos por defecto si no se puede extraer JSON
            intent_data = {
                "intent": "general",
                "collections": [],
                "parameters": {},
                "confidence": 0.0
            }
        
        return True, "Intención analizada", intent_data
    
    @classmethod
    def extract_structured_data(
        cls,
        text: str,
        schema: Dict[str, Any]
    ) -> Tuple[bool, str, Optional[Dict]]:
        """
        Extrae datos estructurados de un texto usando el LLM.
        
        Args:
            text: Texto a analizar
            schema: Esquema de datos a extraer
            
        Returns:
            Tuple (success, message, extracted_data)
        """
        # Construir prompt para extracción
        fields_description = "\n".join([
            f"- {field}: {desc}" for field, desc in schema.items()
        ])
        
        system_prompt = f"""Eres un experto en extracción estructurada de datos de textos inmobiliarios.

Extrae la información solicitada del texto y devuélvela en formato JSON válido.

CAMPOS A EXTRAER:
{fields_description}

INSTRUCCIONES:
1. Extrae solo los datos que aparecen explícitamente en el texto.
2. Si un campo no está presente, omítelo del JSON.
3. Convierte valores monetarios a números.
4. Normaliza tipos de propiedad: "Departamento", "Casa", "Terreno", "Local", "Oficina".
5. Para ubicaciones, extrae distrito, ciudad, departamento si están mencionados.
6. Devuelve SOLO el objeto JSON, sin explicaciones."""

        messages = [
            {"role": "user", "content": f"Texto a analizar:\n{text}"}
        ]
        
        success, api_message, api_response = cls._call_deepseek_api(
            messages=messages,
            system_prompt=system_prompt
        )
        
        if not success:
            return False, api_message, None
        
        # Extraer JSON
        extracted_data = cls._extract_json_from_response(api_response["content"])
        
        if not extracted_data:
            return False, "No se pudo extraer datos estructurados", None
        
        return True, "Datos extraídos exitosamente", extracted_data
    
    @classmethod
    def generate_streaming_response(
        cls,
        query: str,
        context: Optional[Dict] = None,
        system_prompt: str = "",
        max_tokens: int = 1000,
        temperature: float = 0.7
    ) -> Generator[str, None, None]:
        """
        Genera una respuesta en streaming desde DeepSeek API.
        
        Args:
            query: Consulta del usuario
            context: Contexto adicional (opcional)
            system_prompt: Prompt del sistema (opcional)
            max_tokens: Máximo de tokens en la respuesta
            temperature: Temperatura para la generación
            
        Yields:
            Fragmentos de texto de la respuesta en streaming
        """
        if not cls.API_KEY:
            yield json.dumps({
                "error": "API key de DeepSeek no configurada",
                "type": "error"
            })
            return
        
        # Construir mensajes
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # Agregar contexto si está disponible
        if context:
            context_text = f"Contexto adicional:\n{json.dumps(context, indent=2, ensure_ascii=False)}"
            messages.append({"role": "system", "content": context_text})
        
        messages.append({"role": "user", "content": query})
        
        # Llamar a la API en modo streaming
        success, message, api_response = cls._call_deepseek_api(
            messages=messages,
            system_prompt="",  # Ya incluido en messages
            stream=True
        )
        
        if not success:
            yield json.dumps({
                "error": f"Error al llamar a la API: {message}",
                "type": "error"
            })
            return
        
        # Procesar respuesta de streaming
        stream_response = api_response.get("stream_response")
        if not stream_response:
            yield json.dumps({
                "error": "Respuesta de streaming no disponible",
                "type": "error"
            })
            return
        
        try:
            # Procesar cada línea del stream
            for line in stream_response.iter_lines():
                if line:
                    line = line.decode('utf-8').strip()
                    
                    # Saltar líneas vacías o de keep-alive
                    if not line or line == "data: [DONE]":
                        continue
                    
                    # Las líneas de datos de DeepSeek vienen como "data: {...}"
                    if line.startswith("data: "):
                        data_str = line[6:]  # Remover "data: "
                        
                        try:
                            data = json.loads(data_str)
                            
                            # Extraer contenido del chunk
                            choices = data.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                
                                if content:
                                    yield json.dumps({
                                        "content": content,
                                        "type": "chunk"
                                    })
                                    
                        except json.JSONDecodeError:
                            # Ignorar líneas que no son JSON válido
                            continue
            
            # Señal de finalización
            yield json.dumps({
                "type": "complete",
                "message": "Streaming completado"
            })
            
        except Exception as e:
            yield json.dumps({
                "error": f"Error procesando stream: {str(e)}",
                "type": "error"
            })
    
    @classmethod
    def test_connection(cls) -> Tuple[bool, str]:
        """
        Prueba la conexión con DeepSeek API.
        
        Returns:
            Tuple (success, message)
        """
        if not cls.API_KEY:
            return False, "API key de DeepSeek no configurada"
        
        # Mensaje de prueba simple
        messages = [
            {
                "role": "user",
                "content": "Responde con 'OK' si estás funcionando correctamente."
            }
        ]
        
        try:
            success, message, _ = cls._call_deepseek_api(messages)
            if success:
                return True, "Conexión con DeepSeek API establecida correctamente"
            else:
                return False, f"Error en la conexión: {message}"
                
        except Exception as e:
            logger.error(f"Error probando conexión con DeepSeek: {e}")
            return False, f"Error probando conexión: {str(e)}"