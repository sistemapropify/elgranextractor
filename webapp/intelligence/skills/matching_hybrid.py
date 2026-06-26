"""
HybridMatchingSkill — Skill única de matching híbrido v4.

Pipeline: FAISS semántico → post-filtrado (scoring.aplicar_filtros_duros) →
          scoring estructural (scoring.calcular_scoring_total) →
          filtrado final (scoring.filtrar_resultados_finales).

Usa el módulo compartido matching.scoring para toda la lógica de filtros y scoring.
Opera 100% sobre IntelligenceDocument + FAISS. No consulta dbpropify_be directamente.

Basado en: ESPECIFICACION_MATCHING_v3.md
"""

from __future__ import annotations

import logging
import numpy as np
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from .base import BaseSkill, SkillResult
from matching import scoring

logger = logging.getLogger(__name__)


# ── HybridMatchingSkill ──────────────────────────────────────────────────────

class HybridMatchingSkill(BaseSkill):
    """
    Skill única de matching híbrido v4.

    Pipeline:
    1. Obtener requerimiento desde IntelligenceDocument (colección requerimientos_enbedados)
    2. Extraer su embedding precomputado
    3. Buscar en FAISS propiedadespropify (top-K=500)
    4. Post-filtrar por field_values (via scoring.aplicar_filtros_duros)
    5. Scoring estructural desde field_values (via scoring.calcular_scoring_total)
    6. Scoring semántico desde FAISS similarity (via scoring._score_semantico)
    7. Combinar scores: score_final = score_estructural + score_semantico
    8. Filtrado final: umbral 70% + top-10 + ranking (via scoring.filtrar_resultados_finales)
    """

    name = "matching_hibrido"
    description = (
        "Matching híbrido oferta-demanda v4: busca propiedades compatibles con un requerimiento "
        "usando búsqueda semántica FAISS + 10 filtros duros + scoring estructural (8 factores) "
        "+ scoring semántico escalonado (peso 15) + filtrado final (umbral 70%, top-10). "
        "Recibe requerimiento_id y retorna propiedades rankeadas."
    )
    category = "crm"
    access_level = 1
    is_active = True

    parameters_schema = {
        'requerimiento_id': {
            'type': 'integer',
            'description': 'ID del requerimiento en la tabla requerimiento',
            'required': True,
        },
        'top_n': {
            'type': 'integer',
            'description': 'Número máximo de resultados a retornar. Default 10 (usa scoring.TOP_K_MATCHES)',
            'required': False,
        },
        'umbral_minimo': {
            'type': 'number',
            'description': 'Score mínimo (0-100) para incluir un match. Default 70 (usa scoring.UMBRAL_MINIMO_SCORE)',
            'required': False,
        },
    }

    FAISS_TOP_K = 500
    FAISS_DIMENSION = 1024

    # ── Validación ─────────────────────────────────────────────────────────

    def validate_params(self, params: Dict[str, Any]) -> bool:
        if not params:
            return False
        requerimiento_id = params.get('requerimiento_id')
        if requerimiento_id is None:
            return False
        try:
            int(str(requerimiento_id))
            return True
        except (ValueError, TypeError):
            return False

    # ── Ejecución principal ────────────────────────────────────────────────

    def execute(
        self,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> SkillResult:
        """
        Ejecuta matching híbrido v4 completo.

        Args:
            params: {
                'requerimiento_id': int,
                'top_n': int (opcional, default scoring.TOP_K_MATCHES),
                'umbral_minimo': float (opcional, default scoring.UMBRAL_MINIMO_SCORE),
            }
            context: Contexto opcional

        Returns:
            SkillResult con matches rankeados
        """
        try:
            if not self.validate_params(params):
                return SkillResult.error(
                    message="Parámetro requerido: requerimiento_id",
                    skill_name=self.name,
                )

            requerimiento_id = int(params['requerimiento_id'])
            top_n = int(params.get('top_n', scoring.TOP_K_MATCHES))
            umbral_minimo = float(params.get('umbral_minimo', scoring.UMBRAL_MINIMO_SCORE))

            # ── Paso 1: Obtener requerimiento embeddeado ────────────────
            req_doc, req_data = self._get_requerimiento_doc(requerimiento_id)
            if req_doc is None:
                return SkillResult.error(
                    message=f"Requerimiento {requerimiento_id} no encontrado en colección requerimientos_enbedados",
                    skill_name=self.name,
                )

            # ── Paso 2-5: Búsqueda híbrida ─────────────────────────────
            matches = self._hybrid_search(
                req_embedding=req_doc.embedding,
                req_data=req_data,
            )

            if not matches:
                return SkillResult.ok(
                    data={'matches': [], 'total': 0},
                    message=f"No se encontraron propiedades compatibles para requerimiento {requerimiento_id}",
                    metadata={
                        'requerimiento_id': requerimiento_id,
                        'modo': 'hybrid_v4',
                    },
                    skill_name=self.name,
                )

            # ── Paso 6-8: Filtrado final ──────────────────────────────
            # Preparar para filtrado final
            resultados_para_filtrar = []
            for m in matches:
                score_total = m['score_structural'] + m['score_semantico']
                score_total = max(0.0, min(100.0, score_total))
                resultados_para_filtrar.append({
                    'score_total': score_total,
                    'propiedad_dict': m,
                    'propiedad_id': m['property_id'],
                    'fase_eliminada': None,
                    'porcentaje_compatibilidad': score_total,
                })

            # Aplicar filtrado final (umbral + top-K + ranking)
            final = scoring.filtrar_resultados_finales(
                resultados_para_filtrar,
                umbral_minimo=int(umbral_minimo),
                top_k=top_n,
            )

            # Reconstruir matches con ranking
            top_matches = []
            for item in final:
                m = item['propiedad_dict']
                m['ranking'] = item['ranking']
                m['score_total'] = item['score_total']
                top_matches.append(m)

            return SkillResult.ok(
                data={
                    'matches': top_matches,
                    'total': len(top_matches),
                    'requerimiento_id': requerimiento_id,
                },
                message=(
                    f"Matching híbrido v4 completado: {len(matches)} propiedades pasaron filtros, "
                    f"mostrando las {len(top_matches)} mejores (umbral {umbral_minimo}%)."
                ),
                metadata={
                    'requerimiento_id': requerimiento_id,
                    'modo': 'hybrid_v4',
                    'faiss_k': self.FAISS_TOP_K,
                    'total_after_filters': len(matches),
                    'top_n': top_n,
                    'umbral_minimo': umbral_minimo,
                },
                skill_name=self.name,
            )

        except Exception as e:
            logger.exception(f"[HybridMatchingSkill] Error: {e}")
            return SkillResult.error(
                message=f"Error interno: {str(e)}",
                skill_name=self.name,
            )

    # ── Paso 1: Obtener requerimiento ─────────────────────────────────────

    def _get_requerimiento_doc(
        self, requerimiento_id: int
    ) -> Tuple[Optional[Any], Optional[Dict]]:
        """
        Obtiene el IntelligenceDocument del requerimiento y req_data.

        Returns:
            Tuple[IntelligenceDocument|None, Dict|None]
        """
        from ..models import IntelligenceDocument

        try:
            doc = IntelligenceDocument.objects.get(
                collection__name='requerimientos_enbedados',
                source_id=str(requerimiento_id),
            )

            # Obtener datos del requerimiento usando scoring.preparar_req_data
            from requerimientos.models import Requerimiento
            try:
                req = Requerimiento.objects.get(id=requerimiento_id)
                req_data = scoring.preparar_req_data(req)
            except Requerimiento.DoesNotExist:
                req_data = {}

            return doc, req_data

        except IntelligenceDocument.DoesNotExist:
            logger.warning(
                f"Requerimiento {requerimiento_id} no tiene IntelligenceDocument "
                f"en colección requerimientos_enbedados"
            )
            return None, None

    # ── Pasos 2-5: Búsqueda híbrida ───────────────────────────────────────

    def _hybrid_search(
        self,
        req_embedding: bytes,
        req_data: Dict[str, Any],
    ) -> List[Dict]:
        """
        Búsqueda FAISS + post-filtrado + scoring estructural + scoring semántico.

        Args:
            req_embedding: Embedding precomputado del requerimiento (bytes)
            req_data: Datos del requerimiento (de scoring.preparar_req_data)

        Returns:
            Lista de matches con score estructural y semántico
        """
        from ..services.faiss_index import FAISSIndexManager

        # ── Paso 2: Búsqueda FAISS ─────────────────────────────────────
        faiss_idx = FAISSIndexManager.get_instance(
            'propiedadespropify', self.FAISS_DIMENSION
        )
        if not faiss_idx.is_loaded:
            logger.warning("[HybridMatchingSkill] FAISS no cargado para propiedadespropify")
            return []

        query_vector = np.frombuffer(req_embedding, dtype=np.float32)
        faiss_results = faiss_idx.search(query_vector, top_k=self.FAISS_TOP_K)

        if not faiss_results:
            logger.info("[HybridMatchingSkill] Sin resultados FAISS")
            return []

        # ── Batch load: todos los documentos FAISS de una sola vez ─────
        from ..models import IntelligenceDocument

        doc_ids = [r['document_id'] for r in faiss_results]
        docs_qs = IntelligenceDocument.objects.filter(id__in=doc_ids).only(
            'id', 'source_id', 'field_values'
        )
        docs_map = {str(d.id): d for d in docs_qs}

        # ── Post-filtrado + scoring ────────────────────────────────────
        matches = []
        for fr in faiss_results:
            doc = docs_map.get(fr['document_id'])
            if not doc:
                continue

            fv = doc.field_values or {}

            # FAISS retorna distancia L2. Para vectores normalizados: cos_sim = 1 - l2²/2
            l2_dist = fr['similarity']
            score_sem = 1.0 - (l2_dist * l2_dist) / 2.0
            if score_sem < 0:
                score_sem = 0.0

            # ── Paso 3: Filtros duros sobre field_values ────────────────
            # field_values tiene la misma estructura que los dicts de engine.py
            # Campos esperados: price, currency_id, bedrooms, bathrooms, built_area,
            # has_elevator, garage_spaces, antiquity_years, district_id, district_name,
            # operation_type_id, operation_type_name, property_type_id, property_type_name
            fase_eliminada = scoring.aplicar_filtros_duros(fv, req_data)
            if fase_eliminada:
                continue

            # ── Paso 4: Scoring estructural desde field_values ──────────
            score_struct_total, score_detalle = scoring.calcular_scoring_total(fv, req_data)

            # ── Paso 5: Scoring semántico (función escalonada) ──────────
            score_sem_value = scoring._score_semantico(score_sem)

            matches.append({
                'property_id': self._safe_int(doc.source_id),
                'property_doc_id': str(doc.id),
                'field_values': fv,
                'score_total': round(score_struct_total + score_sem_value, 2),
                'score_structural': round(score_struct_total, 2),
                'score_semantico': round(score_sem_value, 2),
                'score_detalle': {
                    **score_detalle,
                    'semantico': {
                        'score': round(score_sem_value, 2),
                        'peso_maximo': scoring.PESOS['semantico'],
                        'detalle': f"Similaridad semántica: {score_sem:.4f} -> escalonada: {score_sem_value:.2f}",
                    },
                },
                'ranking': None,
            })

        return matches

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _safe_int(val: Any) -> int:
        """Convierte un valor a int de forma segura."""
        try:
            return int(float(str(val)))
        except (ValueError, TypeError):
            return 0
