"""
WhatsAppAgent — Extracción de requerimientos desde mensajes WhatsApp.

F4-001 (11.6): Agente especializado en procesar mensajes de WhatsApp
para extraer requerimientos de clientes inmobiliarios.

Detecta:
- Tipo de propiedad buscada (casa, depa, terreno)
- Ubicación/distrito
- Rango de precio
- Características (dormitorios, baños, área)
- Operación (compra, alquiler)
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class WhatsAppAgent:
    """
    Procesa mensajes de WhatsApp para extraer requerimientos.
    
    Usa DeepSeek para entender el lenguaje natural y extraer
    parámetros estructurados del requerimiento del cliente.
    """

    @classmethod
    def run(cls, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ejecuta extracción de requerimiento.

        Args:
            state: PILAgentState con message

        Returns:
            state actualizado con requerimiento_extraido
        """
        start = time.time()
        message = state.get('message', '')

        try:
            from ..services.llm import LLMService

            # Prompt para extraer requerimiento
            prompt = (
                "Extrae los siguientes datos de este mensaje de WhatsApp "
                "de un cliente buscando propiedad. "
                "Responde SOLO con JSON válido.\n\n"
                f"Mensaje: {message}\n\n"
                "Formato JSON:\n"
                "{\n"
                '  "tipo_propiedad": "casa|departamento|terreno|local|oficina|null",\n'
                '  "distrito": "nombre_distrito|null",\n'
                '  "operacion": "compra|alquiler|null",\n'
                '  "precio_max": numero|null,\n'
                '  "precio_min": numero|null,\n'
                '  "dormitorios": numero|null,\n'
                '  "area_min": numero|null,\n'
                '  "caracteristicas": ["lista", "de", "caracteristicas"],\n'
                '  "urgencia": "alta|media|baja|null",\n'
                '  "nombre_cliente": "string|null",\n'
                '  "contacto": "string|null"\n'
                "}\n\n"
                "Si no hay datos para un campo, usa null."
            )

            llm = LLMService()
            response = llm.generate_response(prompt)

            # Parsear JSON de la respuesta
            try:
                # Buscar JSON en la respuesta
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    requerimiento = json.loads(json_match.group())
                else:
                    requerimiento = json.loads(response)
            except (json.JSONDecodeError, AttributeError):
                logger.warning(
                    f"[F4-001] WhatsAppAgent: no se pudo parsear JSON "
                    f"de respuesta DeepSeek"
                )
                requerimiento = {'error': 'parse_error', 'raw': response[:200]}

            state['requerimiento_extraido'] = requerimiento
            state['skill_detectada'] = 'extraer_requerimientos_whatsapp'

            elapsed = (time.time() - start) * 1000
            campos = [k for k, v in requerimiento.items() if v is not None and k != 'error']
            logger.info(
                f"[F4-001] WhatsAppAgent: {len(campos)} campos extraídos | "
                f"tipo={requerimiento.get('tipo_propiedad')} | "
                f"distrito={requerimiento.get('distrito')} | "
                f"latencia={elapsed:.1f}ms"
            )

        except Exception as e:
            logger.error(f"[F4-001] WhatsAppAgent error: {e}")
            state['requerimiento_extraido'] = {'error': str(e)}

        return state
