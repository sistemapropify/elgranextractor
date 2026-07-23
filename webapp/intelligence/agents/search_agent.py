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
        'Local': ['local', 'locales', 'comercial', 'tienda', 'negocio'],
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

        Para skill 'matching_hibrido', delega en HybridMatchingSkill via SkillOrchestrator.
        Para las demás, usa RAGService.search_dynamic() con filtros SQL.

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
            # ── Skill híbrida: delegar en HybridMatchingSkill ──────────
            if skill_name == 'matching_hibrido':
                return cls._run_hybrid_matching(state, params, start)

            # ── Skills tradicionales: RAG + filtros SQL ────────────────
            from ..services.rag import RAGService

            # Determinar colecciones según la skill
            collections = cls._get_collections_for_skill(skill_name)

            from ..search.executor import apply_conditions
            from ..search.contracts import SearchPlan
            from ..search.normalizer import SearchPlanNormalizer

            existing_plan = state.get('search_plan')
            if existing_plan:
                search_plan = SearchPlan.from_dict(existing_plan)
                params = search_plan.to_params()
                state['params_extraidos'] = params
                state['fallback_plan_reused'] = True
                expected_hash = state.get('search_plan_hash')
                if expected_hash and expected_hash != search_plan.fingerprint():
                    raise ValueError('FALLBACK_PLAN_DIVERGENCE')
            else:
                # Extraer parámetros del mensaje para construir filtros SQL.
                params_from_message = cls._extract_basic_intent(message)
                if params_from_message:
                    params.update(params_from_message)
                    state['params_extraidos'] = params
                    if not skill_name:
                        state['skill_detectada'] = 'busqueda_propiedades'
                        skill_name = 'busqueda_propiedades'

                search_plan = SearchPlanNormalizer.from_params(
                    query=message,
                    params=params,
                    collections=collections,
                )

            collections = search_plan.collections or collections
            filters = search_plan.equality_filters()

            # Ejecutar búsqueda semántica con pre-filtrado SQL
            results = RAGService.search_dynamic(
                query=message,
                collection_names=collections,
                filters=filters or None,
            )
            results, applied_filters = apply_conditions(
                results,
                search_plan.conditions,
            )

            state['resultados_busqueda'] = results
            state['search_plan'] = search_plan.to_dict()
            state['search_plan_hash'] = search_plan.fingerprint()
            state['filtros_aplicados'] = [
                applied_filter.to_dict() for applied_filter in applied_filters
            ]
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
            state['filtros_aplicados'] = []
            state['total_resultados'] = 0
            state['search_failed'] = True
            state['error'] = str(e)
            state['search_error_code'] = (
                'FALLBACK_PLAN_DIVERGENCE'
                if 'FALLBACK_PLAN_DIVERGENCE' in str(e)
                else 'SEARCH_EXECUTION_FAILED'
            )

        return state

    @classmethod
    def _run_hybrid_matching(
        cls, state: Dict[str, Any], params: Dict[str, Any], start: float
    ) -> Dict[str, Any]:
        """
        Ejecuta matching híbrido delegando en HybridMatchingSkill.

        Args:
            state: Estado actual del agente
            params: Parámetros extraídos (puede contener requerimiento_id)
            start: Timestamp de inicio para medir latencia

        Returns:
            state actualizado con resultados_busqueda desde HybridMatchingSkill
        """
        try:
            from ..skills.registry import SkillRegistry
            from ..skills.orchestrator import SkillOrchestrator, ExecutionContext
            from ..skills.cache import SkillCache

            # Obtener requerimiento_id desde params o desde el mensaje
            requerimiento_id = params.get('requerimiento_id')
            if not requerimiento_id:
                # Intentar extraer del mensaje
                message = state.get('message', '')
                import re
                match = re.search(r'(?:requerimiento|id|#)\s*(\d+)', message, re.IGNORECASE)
                if match:
                    requerimiento_id = int(match.group(1))
                else:
                    logger.warning("[SearchAgent] matching_hibrido sin requerimiento_id")
                    state['resultados_busqueda'] = []
                    state['filtros_aplicados'] = {}
                    state['total_resultados'] = 0
                    return state

            # Ejecutar skill via SkillOrchestrator
            registry = SkillRegistry()
            cache = SkillCache()  # usa defaults (cache local, sin Redis)
            orchestrator = SkillOrchestrator(registry, cache)

            skill_params = {
                'requerimiento_id': int(requerimiento_id),
                'alpha': params.get('alpha', 0.6),
                'top_n': params.get('top_n', 20),
                'umbral_minimo': params.get('umbral_minimo', 0.0),
            }

            context = ExecutionContext(
                user_id=state.get('user_id'),
                session_id=state.get('conversation_id'),
            )

            result = orchestrator.execute_skill('matching_hibrido', skill_params, context)

            if result.success and result.data:
                matches = result.data.get('matches', [])
                state['resultados_busqueda'] = matches
                state['filtros_aplicados'] = {'modo': 'hybrid', 'alpha': skill_params['alpha']}
                state['total_resultados'] = result.data.get('total', len(matches))

                elapsed = (time.time() - start) * 1000
                logger.info(
                    f"[F2-001] SearchAgent: matching_hibrido | "
                    f"requerimiento_id={requerimiento_id} | "
                    f"resultados={state['total_resultados']} | latencia={elapsed:.1f}ms"
                )
            else:
                logger.warning(
                    f"[SearchAgent] matching_hibrido falló: {result.message}"
                )
                state['resultados_busqueda'] = []
                state['filtros_aplicados'] = {}
                state['total_resultados'] = 0

        except Exception as e:
            logger.error(f"[SearchAgent] Error en matching_hibrido: {e}")
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
            'matching_hibrido': ['propiedadespropify', 'requerimientos_enbedados'],
        }
        return collection_map.get(skill_name, ['propiedadespropify'])

    @classmethod
    def _build_filters(cls, params: dict, skill_name: str) -> dict:
        """Adaptador legacy: solo devuelve igualdades no ambiguas."""
        from ..search.normalizer import SearchPlanNormalizer

        plan = SearchPlanNormalizer.from_params(
            query='',
            params=params,
            collections=cls._get_collections_for_skill(skill_name),
        )
        return plan.equality_filters()
