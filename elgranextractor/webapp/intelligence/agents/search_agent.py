"""
SearchAgent — Ejecuta búsqueda RAG con FAISS + SQL pre-filtering.

F2-001 (6.4): Nodo de búsqueda del grafo LangGraph.
Usa RAGService.search_dynamic() para búsqueda semántica con filtros SQL.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict

logger = logging.getLogger(__name__)


class SearchAgent:
    """
    Ejecuta búsqueda semántica sobre colecciones RAG.
    
    Integra:
    - F1-002: SQL pre-filtering en BD
    - FAISS HNSW para búsqueda vectorial O(log n)
    - Fallback a búsqueda por texto si es necesario
    - Extracción básica de intención si RouterAgent no detectó skill
    """

    # Palabras clave por tipo de propiedad
    _TIPO_KEYWORDS = {
        'Terreno': ['terreno', 'terrenos', 'lote', 'lotes', 'parcela'],
        'Casa': ['casa', 'casas', 'vivienda', 'chalet'],
        'Departamento': ['departamento', 'departamentos', 'depa', 'depas', 'depto', 'deptos'],
        'Local Comercial': ['local', 'locales', 'comercial'],
        'Oficina': ['oficina', 'oficinas'],
    }

    _DISTRITOS = [
        'Cayma', 'Yanahuara', 'Cercado', 'Miraflores',
        'Jose Luis Bustamante', 'Bustamante', 'Sachaca',
        'Cerro Colorado', 'Mariano Melgar', 'Paucarpata',
    ]

    @classmethod
    def run(cls, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ejecuta búsqueda RAG según la skill detectada.

        Args:
            state: Dict con message, skill_detectada, params_extraidos

        Returns:
            state actualizado con resultados_busqueda, filtros_aplicados
        """
        start = time.time()
        message = state.get('message', '')
        skill_name = state.get('skill_detectada')
        params = state.get('params_extraidos', {})

        try:
            from ..services.rag import RAGService

            # Determinar colecciones según la skill
            collections = cls._get_collections_for_skill(skill_name)

            # Si no hay skill detectada ni params extraidos, extraer del mensaje
            if not params and not skill_name:
                params = cls._extract_basic_intent(message)
                state['params_extraidos'] = params
                # Asignar skill basado en la extracción
                if params:
                    state['skill_detectada'] = 'busqueda_propiedades'
                    skill_name = 'busqueda_propiedades'

            # Construir filtros desde parámetros extraídos
            filters = cls._build_filters(params, skill_name)

            # Ejecutar búsqueda semántica con pre-filtrado SQL
            # Sin límite de resultados para encontrar TODAS las propiedades
            # que coincidan con los filtros (distrito, tipo, etc.)
            results = RAGService.search_dynamic(
                query=message,
                collection_names=collections,
                filters=filters or None,
            )

            state['resultados_busqueda'] = results
            state['filtros_aplicados'] = filters
            state['total_resultados'] = len(results)

            elapsed = (time.time() - start) * 1000
            logger.info(
                f"[F2-001] SearchAgent: skill={skill_name} | "
                f"colecciones={collections} | filtros={filters} | "
                f"resultados={len(results)} | latencia={elapsed:.1f}ms"
            )

        except Exception as e:
            logger.error(f"[F2-001] SearchAgent error: {e}")
            state['resultados_busqueda'] = []
            state['filtros_aplicados'] = {}
            state['total_resultados'] = 0

        return state

    @classmethod
    def _extract_basic_intent(cls, message: str) -> Dict[str, str]:
        """
        Extrae intención básica del mensaje cuando el RouterAgent no detectó skill.

        Analiza palabras clave en el mensaje para detectar:
        - Tipo de propiedad (terreno, casa, departamento)
        - Distrito (Cayma, Yanahuara, etc.)
        """
        params = {}
        msg_lower = message.lower()

        # Detectar tipo de propiedad
        for tipo, keywords in cls._TIPO_KEYWORDS.items():
            if any(kw in msg_lower for kw in keywords):
                params['tipo_propiedad'] = tipo
                break

        # Detectar distrito
        for distrito in cls._DISTRITOS:
            if distrito.lower() in msg_lower:
                params['distrito'] = distrito
                break

        return params

    @classmethod
    def _get_collections_for_skill(cls, skill_name: str) -> list:
        """Determina qué colecciones RAG consultar según la skill."""
        collection_map = {
            'busqueda_propiedades': ['propiedadespropify'],
            'acm_analisis': ['propiedadespropify'],
            'reporte_precios_zona': ['propiedadespropify'],
            'matching_oferta_demanda': ['propiedadespropify', 'requerimientos'],
        }
        return collection_map.get(skill_name, ['propiedadespropify'])

    @classmethod
    def _build_filters(cls, params: dict, skill_name: str) -> dict:
        """Construye filtros SQL desde parámetros extraídos por DeepSeek."""
        filters = {}
        if not params:
            return filters

        # Mapeo de parámetros extraídos a field_values reales en BD
        # Los nombres reales vienen de la vista vwd_propiedades_propify_listado
        field_mapping = {
            'distrito': 'district_name',
            'tipo_propiedad': 'property_type_name',
            'operacion': 'operation_type_name',
            'precio': 'price',
            'precio_min': 'price',
            'precio_max': 'price',
        }

        for param_key, field_name in field_mapping.items():
            value = params.get(param_key)
            if value is not None and value != '':
                filters[field_name] = value

        return filters
