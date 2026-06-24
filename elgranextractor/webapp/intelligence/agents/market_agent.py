"""
MarketAgent — Análisis de mercado inmobiliario.

F4-001 (11.5): Agente especializado en análisis de mercado.
Procesa datos de propiedades para generar reportes de:
- Precio promedio por zona
- Tendencias de precios
- Comparativas de distritos
- Recomendaciones de inversión
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class MarketAgent:
    """
    Analiza el mercado inmobiliario usando datos RAG.
    
    Este agente se activa cuando el usuario pregunta sobre:
    - "cómo está el mercado en..."
    - "precio promedio de..."
    - "análisis de mercado"
    - "tendencias de precios"
    """

    @classmethod
    def run(cls, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ejecuta análisis de mercado.

        Args:
            state: PILAgentState con message, resultados_busqueda

        Returns:
            state actualizado con analisis_mercado
        """
        start = time.time()
        message = state.get('message', '')
        resultados = state.get('resultados_busqueda', [])

        try:
            if not resultados:
                # Buscar propiedades si no hay resultados previos
                from ..services.rag import RAGService
                resultados = RAGService.search_dynamic(
                    query=message,
                    collection_names=['propiedadespropify'],
                    top_k=100,
                )
                state['resultados_busqueda'] = resultados

            # Calcular métricas de mercado
            precios = []
            tipos = {}
            distritos = {}

            for r in resultados:
                fv = r.get('field_values', {})
                precio = fv.get('price')
                if precio:
                    try:
                        precios.append(float(precio))
                    except (ValueError, TypeError):
                        pass

                tipo = fv.get('property_type_name', 'No especificado')
                tipos[tipo] = tipos.get(tipo, 0) + 1

                distrito = fv.get('district_name', 'No especificado')
                distritos[distrito] = distritos.get(distrito, 0) + 1

            # Construir análisis
            analysis = {
                'total_propiedades': len(resultados),
                'precio_promedio': round(sum(precios) / len(precios), 2) if precios else None,
                'precio_minimo': min(precios) if precios else None,
                'precio_maximo': max(precios) if precios else None,
                'distribucion_tipos': dict(sorted(tipos.items(), key=lambda x: x[1], reverse=True)[:5]),
                'distribucion_distritos': dict(sorted(distritos.items(), key=lambda x: x[1], reverse=True)[:5]),
                'total_con_precio': len(precios),
            }

            state['analisis_mercado'] = analysis
            state['skill_detectada'] = 'analizar_mercado'

            elapsed = (time.time() - start) * 1000
            logger.info(
                f"[F4-001] MarketAgent: {len(resultados)} propiedades | "
                f"precio_prom={analysis['precio_promedio']} | "
                f"latencia={elapsed:.1f}ms"
            )

        except Exception as e:
            logger.error(f"[F4-001] MarketAgent error: {e}")
            state['analisis_mercado'] = {
                'error': str(e),
                'total_propiedades': 0,
            }

        return state
