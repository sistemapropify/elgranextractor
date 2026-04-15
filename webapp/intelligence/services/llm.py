"""
Servicio LLM integrado con RAG para generación de respuestas enriquecidas con contexto.

Este módulo integra el sistema RAG con DeepSeek API para proporcionar respuestas
enriquecidas con información contextual de propiedades, noticias y datos del mercado.
"""

import os
import json
import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

import requests
from django.conf import settings
from django.utils import timezone

from .rag import RAGService
from ..models import IntelligenceCollection

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
        system_prompt: str = ""
    ) -> Tuple[bool, str, Optional[Dict]]:
        """
        Llama a la API de DeepSeek.
        
        Args:
            messages: Lista de mensajes en formato OpenAI
            system_prompt: Prompt del sistema (opcional)
            
        Returns:
            Tuple (success, message, response_data)
        """
        if not cls.API_KEY:
            return False, "API key de DeepSeek no configurada", None
        
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
            "stream": False
        }
        
        try:
            logger.info(f"Llamando a DeepSeek API con {len(messages)} mensajes")
            response = requests.post(
                cls.DEEPSEEK_API_URL,
                headers=cls._get_headers(),
                json=payload,
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"Error API DeepSeek: {response.status_code} - {response.text}")
                return False, f"Error API: {response.status_code}", None
            
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            if not content:
                return False, "Respuesta vacía de la API", None
            
            logger.info(f"Respuesta DeepSeek recibida ({len(content)} caracteres)")
            return True, "OK", {"content": content, "raw_response": data}
            
        except requests.exceptions.Timeout:
            logger.error("Timeout llamando a DeepSeek API")
            return False, "Timeout en la llamada a la API", None
        except requests.exceptions.RequestException as e:
            logger.error(f"Error de conexión con DeepSeek API: {e}")
            return False, f"Error de conexión: {str(e)}", None
        except Exception as e:
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
        
        Args:
            query: Consulta del usuario
            user_access_level: Nivel de acceso del usuario
            collection_names: Nombres específicos de colecciones (None = todas)
            
        Returns:
            Tuple (context_text, retrieved_documents)
        """
        # Determinar IDs de colecciones si se especifican nombres
        collection_ids = None
        if collection_names:
            collections = IntelligenceCollection.objects.filter(
                name__in=collection_names,
                is_active=True,
                access_level__lte=user_access_level
            )
            collection_ids = list(collections.values_list('id', flat=True))
        
        # Realizar búsqueda RAG
        success, message, results = RAGService.search(
            query=query,
            collection_ids=collection_ids,
            access_level=user_access_level,
            limit=cls.MAX_RAG_CONTEXT_DOCUMENTS,
            similarity_threshold=cls.MIN_SIMILARITY_THRESHOLD
        )
        
        if not success or not results:
            logger.info(f"No se encontraron documentos RAG para la consulta: {query}")
            return "", []
        
        # Construir texto de contexto
        context_parts = []
        for i, doc in enumerate(results, 1):
            # Extraer información relevante del documento
            metadata = doc.get('metadata', {})
            collection_name = doc.get('collection_name', 'Desconocida')
            similarity = doc.get('similarity', 0)
            
            # Formatear información según el tipo de colección
            if 'propiedades' in collection_name.lower():
                # Información de propiedad
                context_parts.append(
                    f"[Documento {i} - Propiedad - Similitud: {similarity:.2f}]\n"
                    f"Título: {metadata.get('titulo', 'Sin título')}\n"
                    f"Descripción: {metadata.get('descripcion', 'Sin descripción')}\n"
                    f"Dirección: {metadata.get('direccion', 'Sin dirección')}\n"
                    f"Distrito: {metadata.get('distrito', 'Sin distrito')}\n"
                    f"Tipo: {metadata.get('tipo_propiedad', 'Sin tipo')}\n"
                    f"Precio: {metadata.get('precio', 'N/A')} {metadata.get('moneda', '')}\n"
                    f"Área construida: {metadata.get('area_construida', 'N/A')} m²\n"
                )
            elif 'noticias' in collection_name.lower():
                # Información de noticia
                context_parts.append(
                    f"[Documento {i} - Noticia - Similitud: {similarity:.2f}]\n"
                    f"Título: {metadata.get('titulo', 'Sin título')}\n"
                    f"Contenido: {metadata.get('contenido', 'Sin contenido')[:500]}...\n"
                    f"Fuente: {metadata.get('fuente', 'Desconocida')}\n"
                    f"Fecha: {metadata.get('fecha_publicacion', 'Desconocida')}\n"
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
    def generate_rag_response(
        cls,
        query: str,
        conversation_history: Optional[List[Dict]] = None,
        user_access_level: int = 1,
        collection_names: Optional[List[str]] = None,
        include_sources: bool = True
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Genera una respuesta enriquecida con contexto RAG.
        
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
        
        # 1. Obtener contexto RAG
        rag_context, retrieved_docs = cls._build_rag_context(
            query=query,
            user_access_level=user_access_level,
            collection_names=collection_names
        )
        
        # 2. Construir prompt del sistema
        system_prompt = """Eres Propifai Assistant, un experto asistente inmobiliario especializado en el mercado de Arequipa, Perú.

Tu conocimiento incluye:
- Propiedades disponibles (propias y de competencia)
- Noticias y análisis del mercado inmobiliario
- Información sobre zonas, precios y tendencias

INSTRUCCIONES CRÍTICAS:
1. Usa EXCLUSIVAMENTE la información proporcionada en el contexto para responder.
2. Si el contexto no contiene información relevante, di claramente "No tengo información sobre eso en mi base de datos actual".
3. Sé preciso con precios, ubicaciones y características.
4. Para propiedades, menciona siempre: precio, ubicación (distrito), tipo de propiedad y características principales.
5. Para noticias, menciona la fuente y fecha si están disponibles.
6. Responde en español claro y profesional.
7. Si se te pide comparar o analizar, usa solo los datos del contexto.

CONTEXTO DISPONIBLE:"""
        
        # 3. Construir mensajes
        messages = []
        
        # Agregar historial de conversación si existe
        if conversation_history:
            for msg in conversation_history[-6:]:  # Últimos 6 mensajes como contexto
                messages.append(msg)
        
        # Agregar contexto RAG y consulta actual
        user_message = f"Consulta del usuario: {query}\n\n"
        
        if rag_context:
            user_message += f"INFORMACIÓN RELEVANTE DE LA BASE DE DATOS:\n{rag_context}\n\n"
            user_message += "Basándote en esta información, responde a la consulta del usuario."
        else:
            user_message += "No tengo información específica en mi base de datos sobre este tema. Responde de manera general si es apropiado."
        
        messages.append({"role": "user", "content": user_message})
        
        # 4. Llamar a la API
        success, api_message, api_response = cls._call_deepseek_api(
            messages=messages,
            system_prompt=system_prompt
        )
        
        if not success:
            return False, api_message, {}
        
        # 5. Procesar respuesta
        response_content = api_response["content"]
        
        # Construir respuesta estructurada
        response_data = {
            "query": query,
            "response": response_content,
            "timestamp": timezone.now().isoformat(),
            "rag_context_used": bool(rag_context),
            "retrieved_documents_count": len(retrieved_docs)
        }
        
        # Incluir fuentes si se solicita y hay documentos recuperados
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