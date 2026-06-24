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
    def _format_skill_response(
        cls, skill_name: str, resultados: list, state: Dict[str, Any]
    ) -> str:
        """Formatea respuesta cuando se detectó una skill."""
        from ..services.llm import LLMService

        llm = LLMService()

        # Construir prompt específico según la skill
        if skill_name == 'busqueda_propiedades':
            prompt = cls._build_propiedades_prompt(resultados, state)
        elif skill_name == 'acm_analisis':
            prompt = cls._build_acm_prompt(resultados, state)
        else:
            prompt = cls._build_generic_skill_prompt(
                skill_name, resultados, state
            )

        try:
            from ..services.llm import LLMService
            response = LLMService.generate_rag_response([], prompt)
            return response
        except Exception as e:
            logger.error(f"Error generando respuesta para skill {skill_name}: {e}")
            return cls._build_fallback_response(resultados)

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
        from ..services.prompts import format_rag_context, build_full_prompt

        llm = LLMService()

        # Construir contexto RAG
        rag_context = format_rag_context([
            {
                'field_values': r.get('field_values', {}),
                'collection_name': r.get('collection_name', ''),
                'similarity': r.get('similarity', 0),
                'content': r.get('content', ''),
            }
            for r in resultados
        ])

        # Construir prompt completo con funciones existentes
        prompt = build_full_prompt(
            message=message,
            rag_context=rag_context,
            memory_context='',
            episodic_context='',
            system_prompt=(
                "Eres un asistente inmobiliario que ayuda a buscar propiedades. "
                "Responde de forma natural y amigable basándote en los datos proporcionados."
            ),
        )

        try:
            response = llm.generate_response(prompt)
            return response
        except Exception as e:
            logger.error(f"Error generando respuesta RAG: {e}")
            return cls._build_fallback_response(resultados)

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
    def _build_fallback_response(cls, resultados: list) -> str:
        """Genera respuesta de fallback cuando DeepSeek falla."""
        if not resultados:
            return (
                "No encontré propiedades que coincidan con tu búsqueda. "
                "¿Quieres intentar con otros criterios?"
            )

        response_parts = [
            f"Estas son las propiedades que encontré ({len(resultados)} en total):\n"
        ]
        for r in resultados:
            fv = r.get('field_values', {})
            # Mostrar cualquier campo disponible del field_values
            campos_visibles = []
            for key in ['titulo', 'direccion', 'precio', 'distrito', 'tipo_propiedad',
                        'area_construida', 'area_terreno', 'dormitorios', 'operacion',
                        'moneda', 'descripcion']:
                val = fv.get(key)
                if val is not None and val != '':
                    campos_visibles.append(f"{key}: {val}")
            
            # Si no hay campos visibles, mostrar todo lo que tenga field_values
            if not campos_visibles and fv:
                for k, v in fv.items():
                    if v is not None and v != '':
                        campos_visibles.append(f"{k}: {v}")
            
            if campos_visibles:
                response_parts.append(f"• {' | '.join(campos_visibles[:6])}")
            else:
                response_parts.append("• Propiedad (sin detalles disponibles)")

        response_parts.append(
            "\n¿Te gusta alguna? Puedo darte más detalles."
        )
        return "\n".join(response_parts)
