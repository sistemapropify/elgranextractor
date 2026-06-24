"""
FormatterAgent — Genera respuesta en lenguaje natural usando DeepSeek.

F2-001 (6.6): Nodo final del grafo LangGraph.
Toma los resultados de búsqueda y contexto, y genera respuesta formateada.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict

logger = logging.getLogger(__name__)


class FormatterAgent:
    """
    Genera la respuesta final del asistente.
    
    Toma los resultados del SearchAgent y el contexto del ContextAgent,
    construye un prompt y llama a DeepSeek para generar la respuesta natural.
    """

    @classmethod
    def run(cls, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Genera respuesta formateada.

        Args:
            state: Dict con resultados_busqueda, contexto, mensaje original

        Returns:
            state actualizado con respuesta_generada, documentos_referencia
        """
        start = time.time()
        message = state.get('message', '')
        resultados = state.get('resultados_busqueda', [])
        skill_name = state.get('skill_detectada')

        try:
            from ..services.llm import LLMService
            from ..services.prompts import PromptManager

            # Construir contexto para el prompt
            prompt_manager = PromptManager()

            # Si hay una skill detectada y resultados, formatear como skill
            if skill_name and resultados:
                response_text = cls._format_skill_response(
                    skill_name, resultados, state
                )
            else:
                # RAG puro: construir prompt con resultados
                response_text = cls._format_rag_response(
                    message, resultados, state, prompt_manager
                )

            state['respuesta_generada'] = response_text
            state['documentos_referencia'] = [
                {
                    'id': r.get('document_id'),
                    'collection': r.get('collection_name'),
                    'similarity': r.get('similarity'),
                    'source_id': r.get('source_id'),
                }
                for r in resultados[:3]  # Top 3 documentos
            ]

            elapsed = (time.time() - start) * 1000
            logger.info(
                f"[F2-001] FormatterAgent: skill={skill_name} | "
                f"resultados={len(resultados)} | "
                f"respuesta_len={len(response_text)} | "
                f"latencia={elapsed:.1f}ms"
            )

        except Exception as e:
            logger.error(f"[F2-001] FormatterAgent error: {e}")
            state['respuesta_generada'] = (
                "Lo siento, ocurrió un error al generar la respuesta. "
                "Por favor intenta de nuevo."
            )
            state['documentos_referencia'] = []

        return state

    @classmethod
    def _build_memory_context(cls, state: Dict[str, Any]) -> str:
        """
        Construye contexto de memoria del usuario para incluirlo en el prompt.
        Consulta hechos conocidos (Fact) y episodios recientes de la conversación.
        """
        user_id = state.get('user_id') if isinstance(state, dict) else None
        if not user_id:
            return ""
        
        memory_parts = []
        
        try:
            # 1. Hechos del usuario (preferencias, datos personales)
            from ..models import Fact, Conversation
            facts = Fact.objects.filter(
                user_id=user_id,
                is_active=True
            ).order_by('-confidence', '-created_at')[:15]
            
            if facts:
                facts_text = "\n".join(
                    f"- {f.subject} {f.relation} {f.object}"
                    for f in facts
                )
                memory_parts.append(f"INFORMACIÓN CONOCIDA DEL USUARIO:\n{facts_text}")
            
            # 2. Última conversación del usuario (para contexto entre turnos)
            conversations = Conversation.objects.filter(
                user_id=user_id
            ).order_by('-last_message_at')[:1]
            
            for conv in conversations:
                messages = conv.messages or []
                if messages:
                    # Últimos 3 intercambios (6 mensajes)
                    recent = messages[-6:] if len(messages) > 6 else messages
                    historia = []
                    for msg in recent:
                        role = msg.get('role', 'unknown')
                        content = msg.get('content', '')[:200]
                        if role == 'user':
                            historia.append(f"Usuario: {content}")
                        elif role == 'assistant':
                            historia.append(f"Asistente: {content}")
                    if historia:
                        memory_parts.append(
                            "HISTORIAL RECIENTE DE LA CONVERSACIÓN:\n" +
                            "\n".join(historia[-4:])  # Ultimos 2 intercambios
                        )
                        
        except Exception as e:
            logger.debug(f"Error consultando memoria: {e}")
        
        return "\n\n".join(memory_parts)

    @classmethod
    def _detectar_formato(cls, message: str) -> str:
        """Detecta el formato solicitado en el mensaje del usuario."""
        if not message:
            return 'carrusel'
        msg = message.lower()
        if any(p in msg for p in ['en matriz', 'en tabla', 'matriz', 'tabla comparativa', 'comparacion', 'comparación']):
            return 'matriz'
        if any(p in msg for p in ['en lista', 'en listado', 'lista', 'listado', 'numerados', 'numeradas']):
            return 'lista'
        # Por defecto: carrusel (es el más visual)
        return 'carrusel'

    @classmethod
    def _generar_html_propiedades(cls, resultados: list, formato: str = 'carrusel') -> str:
        """
        Genera HTML formateado para propiedades usando FormatearPropiedadesSkill.
        
        Args:
            resultados: Lista de resultados de búsqueda
            formato: 'lista', 'carrusel', o 'matriz'
            
        Returns:
            HTML formateado del skill
        """
        try:
            from ..skills.formatear_propiedades import FormatearPropiedadesSkill
            skill = FormatearPropiedadesSkill()
            # Se pasan TODAS las propiedades sin límite
            result = skill.execute({
                'propiedades': resultados,
                'formato': formato,
            })
            if result.success and result.data:
                return result.data.get('html', '')
        except Exception as e:
            logger.debug(f"Error generando HTML de propiedades: {e}")
        return ""

    @classmethod
    def _format_skill_response(
        cls, skill_name: str, resultados: list, state: Dict[str, Any]
    ) -> str:
        """Formatea respuesta cuando se detectó una skill."""
        from ..services.llm import LLMService

        if skill_name == 'busqueda_propiedades':
            prompt = cls._build_propiedades_prompt(resultados, state)
        elif skill_name == 'acm_analisis':
            prompt = cls._build_acm_prompt(resultados, state)
        else:
            prompt = cls._build_generic_skill_prompt(skill_name, resultados, state)

        memory_context = cls._build_memory_context(state)

        try:
            success, api_message, api_response = LLMService._call_deepseek_api(
                messages=[{"role": "user", "content": prompt}],
                system_prompt=(
                    "Eres un asistente inmobiliario especializado en el mercado "
                    "de Arequipa, Perú. Responde de forma natural y amigable.\n\n"
                    f"{memory_context}\n\n"
                    "INSTRUCCIONES:\n"
                    "- Si el usuario pregunta quién es o cómo se llama, revisa la "
                    "INFORMACIÓN CONOCIDA DEL USUARIO arriba.\n"
                    "- Si hay información del usuario, úsala para personalizar la respuesta.\n"
                    "- Si no hay información, responde amablemente que no tienes ese dato aún."
                ),
                caller_app="formatter_agent",
                endpoint="_format_skill_response",
            )
            if success and api_response:
                return api_response.get('content', '') or api_message
            else:
                logger.warning(f"DeepSeek falló en formatter: {api_message}")
                user_msg = state.get('message', '') if isinstance(state, dict) else ''
                return cls._build_fallback_response(resultados, message=user_msg)
        except Exception as e:
            logger.error(f"Error generando respuesta para skill {skill_name}: {e}")
            user_msg = state.get('message', '') if isinstance(state, dict) else ''
            return cls._build_fallback_response(resultados, message=user_msg)

    @classmethod
    def _format_rag_response(
        cls,
        message: str,
        resultados: list,
        state: Dict[str, Any],
        prompt_manager,
    ) -> str:
        """Formatea respuesta RAG pura (sin skill específica)."""
        from ..services.llm import LLMService
        from ..services.prompts import format_rag_context

        # Agregar contexto de memoria del usuario
        memory_context = cls._build_memory_context(state)

        # Construir contexto RAG si hay resultados
        rag_context = ""
        if resultados:
            rag_context = format_rag_context([
                {
                    'field_values': r.get('field_values', {}),
                    'collection_name': r.get('collection_name', ''),
                    'similarity': r.get('similarity', 0),
                    'content': r.get('content', ''),
                }
                for r in resultados
            ])

        # Construir el prompt para DeepSeek
        prompt_parts = [f"Mensaje del usuario: {message}"]
        if rag_context:
            prompt_parts.append(f"\n\nContexto de propiedades:\n{rag_context}")
        prompt = "\n".join(prompt_parts)

        try:
            success, api_message, api_response = LLMService._call_deepseek_api(
                messages=[{"role": "user", "content": prompt}],
                system_prompt=(
                    "Eres un asistente inmobiliario especializado en el mercado "
                    "de Arequipa, Perú. Responde de forma natural y amigable.\n\n"
                    f"{memory_context}\n\n"
                    "INSTRUCCIONES:\n"
                    "- Si el usuario te pregunta quién es o datos personales, "
                    "revisa la INFORMACIÓN CONOCIDA DEL USUARIO.\n"
                    "- Si hay resultados de propiedades, menciónalos.\n"
                    "- Si no hay resultados, responde de forma conversacional.\n"
                    "- Si es un saludo, saluda amablemente."
                ),
                caller_app="formatter_agent",
                endpoint="_format_rag_response",
            )
            if success and api_response:
                return api_response.get('content', '') or api_message
            else:
                logger.warning(f"DeepSeek falló en RAG response: {api_message}")
                user_msg = state.get('message', '') if isinstance(state, dict) else message
                return cls._build_fallback_response(resultados, message=user_msg)
        except Exception as e:
            logger.error(f"Error generando respuesta RAG: {e}")
            user_msg = state.get('message', '') if isinstance(state, dict) else message
            return cls._build_fallback_response(resultados, message=user_msg)

    @classmethod
    def _build_propiedades_prompt(
        cls, resultados: list, state: Dict[str, Any]
    ) -> str:
        """Construye prompt para búsqueda de propiedades."""
        context_info = ""
        if state.get('contexto_activo'):
            context_info = (
                f"\nContexto de la conversación: {state['contexto_activo']}"
            )

        propiedades_text = ""
        for i, r in enumerate(resultados, 1):
            fv = r.get('field_values', {})
            props = [f"{k}: {v}" for k, v in fv.items()]
            propiedades_text += f"\n{i}. {' | '.join(props)}"
            propiedades_text += f"\n   Score: {r.get('similarity', 0):.2f}\n"

        return (
            f"Eres un asistente inmobiliario que ayuda a buscar propiedades.\n"
            f"El usuario preguntó: {state.get('message', '')}\n"
            f"{context_info}"
            f"\n\nPropiedades encontradas:\n{propiedades_text}"
            f"\n\nResponde de forma natural y amigable. "
            f"Menciona las propiedades más relevantes con sus detalles clave "
            f"(distrito, tipo, precio, área). "
            f"Si hay filtros aplicados, menciónalos."
        )

    @classmethod
    def _build_acm_prompt(
        cls, resultados: list, state: Dict[str, Any]
    ) -> str:
        """Construye prompt para análisis comparativo de mercado."""
        propiedades_text = ""
        for i, r in enumerate(resultados, 1):
            fv = r.get('field_values', {})
            props = [f"{k}: {v}" for k, v in fv.items()]
            propiedades_text += f"\n{i}. {' | '.join(props)}"

        return (
            f"Eres un analista de mercado inmobiliario.\n"
            f"El usuario preguntó: {state.get('message', '')}\n"
            f"\nDatos de propiedades comparables:\n{propiedades_text}"
            f"\n\nProporciona un análisis comparativo de mercado. "
            f"Incluye: precio promedio, rango de precios, "
            f"y recomendaciones basadas en los datos."
        )

    @classmethod
    def _build_generic_skill_prompt(
        cls, skill_name: str, resultados: list, state: Dict[str, Any]
    ) -> str:
        """Construye prompt genérico para cualquier skill."""
        resultados_text = ""
        for i, r in enumerate(resultados, 1):
            fv = r.get('field_values', {})
            props = [f"{k}: {v}" for k, v in fv.items()]
            resultados_text += f"\n{i}. {' | '.join(props)}"

        return (
            f"Eres un asistente inteligente del sistema Propifai.\n"
            f"Skill activa: {skill_name}\n"
            f"Usuario: {state.get('message', '')}\n"
            f"\nResultados:\n{resultados_text}"
            f"\n\nResponde de forma útil y natural basada en los resultados."
        )

    @classmethod
    def _build_fallback_response(cls, resultados: list, message: str = "") -> str:
        """
        Genera respuesta de fallback cuando DeepSeek no está disponible.
        
        Detecta si la consulta pide un conteo ("cuántas", "cuántos", "cuantas")
        y responde con el número en lugar de listar todas las propiedades.
        """
        if not resultados:
            return (
                "No encontré propiedades que coincidan con tu búsqueda. "
                "¿Quieres intentar con otros criterios?"
            )

        # Detectar si la consulta pide un conteo
        msg_lower = message.lower()
        es_consulta_conteo = any(
            palabra in msg_lower
            for palabra in ['cuantas', 'cuántas', 'cuantos', 'cuántos',
                          'cuanta', 'cuánta', 'cuanto', 'cuánto',
                          'hay', 'total', 'cantidad', 'numero', 'número',
                          'listado', 'listar', 'lista', 'listame', 'listáme']
        )

        if es_consulta_conteo:
            # Extraer filtros del mensaje para dar contexto
            filtros = []
            distritos_hint = ['cayma', 'yanahuara', 'cercado', 'miraflores',
                            'sachaca', 'cerro colorado', 'bustamante', 'paucarpata',
                            'mariano melgar', 'zamacola', 'socabaya', 'characato',
                            'jose luis bustamante']
            for d in distritos_hint:
                if d in msg_lower:
                    filtros.append(d.title())
                    break
            
            tipo_hint = ['departamento', 'casa', 'terreno', 'local', 'oficina',
                        'departamentos', 'casas', 'terrenos', 'locales', 'oficinas',
                        'depa', 'depas']
            for t in tipo_hint:
                if t in msg_lower:
                    tipo_clean = t.replace('departamentos', 'Departamento')\
                                   .replace('departamento', 'Departamento')\
                                   .replace('depas', 'Departamento')\
                                   .replace('depa', 'Departamento')\
                                   .replace('casas', 'Casa')\
                                   .replace('casa', 'Casa')\
                                   .replace('terrenos', 'Terreno')\
                                   .replace('terreno', 'Terreno')\
                                   .replace('locales', 'Local Comercial')\
                                   .replace('local', 'Local Comercial')\
                                   .replace('oficinas', 'Oficina')\
                                   .replace('oficina', 'Oficina')
                    filtros.append(tipo_clean)
                    break

            ctx = f" en {filtros[0]}" if filtros else ""
            total = len(resultados)
            
            # Contar por tipo si hay suficientes resultados
            if total <= 50:
                from collections import Counter
                tipos = Counter()
                for r in resultados:
                    fv = r.get('field_values', {})
                    tipo = fv.get('tipo_propiedad') or fv.get('property_type_name') or 'Sin tipo'
                    tipos[tipo] += 1
                
                resumen_tipos = " | ".join(f"{k}: {v}" for k, v in tipos.most_common(5))
                return (
                    f"📊 Encontré **{total} propiedades{ctx}**:\n"
                    f"{resumen_tipos}\n\n"
                    f"¿Quieres que te muestre alguna en particular?"
                )
            else:
                return (
                    f"📊 Encontré **{total} propiedades{ctx}** en total.\n\n"
                    f"¿Quieres que te muestre alguna en particular o "
                    f"necesitas más detalles?"
                )

        # Si NO es consulta de conteo, mostrar todas las propiedades separadas
        response_parts = [
            f"Estas son las propiedades que encontré ({len(resultados)} en total):\n"
        ]
        for r in resultados:
            fv = r.get('field_values', {})
            campos_visibles = []
            for key in ['titulo', 'direccion', 'precio', 'distrito', 'tipo_propiedad',
                        'area_construida', 'area_terreno', 'dormitorios', 'operacion',
                        'moneda', 'descripcion']:
                val = fv.get(key)
                if val is not None and val != '':
                    campos_visibles.append(f"{key}: {val}")
            
            if not campos_visibles and fv:
                for k, v in fv.items():
                    if v is not None and v != '':
                        campos_visibles.append(f"{k}: {v}")
            
            if campos_visibles:
                response_parts.append(f"• {' | '.join(campos_visibles[:6])}")
            else:
                response_parts.append("• Propiedad (sin detalles disponibles)")

        response_parts.append(
            "<br>¿Te gusta alguna? Puedo darte más detalles."
        )
        # Separar cada propiedad con <br> (HTML line break para frontend)
        return "<br><br>".join(response_parts)
