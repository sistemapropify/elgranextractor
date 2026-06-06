"""
BusquedaPropiedadesSkill — Skill de búsqueda híbrida (SQL + semántica) de propiedades.

Implementa los 4 pasos de SPEC-015:
  Paso 1: Determinar modo de búsqueda (solo_sql, solo_semantico, hibrido, sin_parametros)
  Paso 2: Filtrado SQL sobre field_values de IntelligenceDocument
  Paso 3: Re-ranking semántico (solo en modo hibrido o solo_semantico)
  Paso 4: Construir SkillResult estandarizado

No modifica RAGService ni los embeddings existentes.
Usa generate_embedding() de RAGService y accede a IntelligenceDocument directamente.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from django.db.models import Q

from ...models import IntelligenceCollection, IntelligenceDocument
from ...services.rag import RAGService
from ..base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)


# ── Normalizaciones ──────────────────────────────────────────────────────────

TIPO_PROPIEDAD_MAP = {
    'depa': 'Departamento',
    'departamento': 'Departamento',
    'dpto': 'Departamento',
    'casa': 'Casa',
    'vivienda': 'Casa',
    'terreno': 'Terreno',
    'lote': 'Terreno',
    'local': 'Local Comercial',
    'local comercial': 'Local Comercial',
    'oficina': 'Oficina',
}

OPERACION_MAP = {
    'venta': 'venta',
    'vendo': 'venta',
    'compro': 'venta',
    'alquiler': 'alquiler',
    'alquilo': 'alquiler',
    'renta': 'alquiler',
}

# Colecciones que contienen propiedades (por naming)
COLECCIONES_PROPIEDADES_KEYWORDS = ['propiedad', 'propifai', 'inmueble']


class BusquedaPropiedadesSkill(BaseSkill):
    """
    Skill de búsqueda híbrida (SQL + semántica) de propiedades.

    Busca en las colecciones IntelligenceCollection que contengan propiedades
    y aplica filtros exactos + re-ranking semántico según los parámetros.
    """

    name = "busqueda_propiedades"
    description = (
        "Busca propiedades en la base de datos usando filtros exactos "
        "(distrito, tipo, precio, habitaciones, área) y búsqueda semántica "
        "(descripciones, ambientes, características). Ideal para cuando el "
        "usuario pregunta por propiedades disponibles con características específicas."
    )
    category = "busqueda"
    access_level = 1
    is_active = True

    parameters_schema = {
        'distrito': {
            'type': 'string',
            'description': 'Nombre del distrito. Ej: Cayma, Yanahuara, Cercado',
            'required': False,
        },
        'tipo_propiedad': {
            'type': 'string',
            'description': 'Tipo de propiedad: Departamento, Casa, Terreno, Local Comercial, Oficina',
            'required': False,
        },
        'operacion': {
            'type': 'string',
            'description': 'Tipo de operación: venta, alquiler',
            'required': False,
        },
        'precio_min': {
            'type': 'number',
            'description': 'Precio mínimo en la moneda detectada',
            'required': False,
        },
        'precio_max': {
            'type': 'number',
            'description': 'Precio máximo en la moneda detectada',
            'required': False,
        },
        'habitaciones': {
            'type': 'integer',
            'description': 'Número mínimo de habitaciones',
            'required': False,
        },
        'area_min': {
            'type': 'number',
            'description': 'Área mínima en m²',
            'required': False,
        },
        'semantic_query': {
            'type': 'string',
            'description': 'Parte semántica/subjetiva del mensaje. Ej: ambientes amplios y luminosos',
            'required': False,
        },
        'top_k': {
            'type': 'integer',
            'description': 'Máximo de resultados a retornar. 0 = sin límite',
            'required': False,
        },
        'condicion': {
            'type': 'string',
            'description': 'Condición/estado de la propiedad: Disponible, Vendida, Reservada. Por defecto se filtran solo las Disponibles.',
            'required': False,
        },
        'colecciones': {
            'type': 'array',
            'description': 'Nombres de colecciones a buscar. Vacío = todas las de propiedades',
            'required': False,
        },
    }

    # ── Validación ────────────────────────────────────────────────────────

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """
        Valida que al menos haya un parámetro de búsqueda.

        Returns:
            True si hay al menos un filtro o semantic_query
        """
        if not params:
            return False

        # Verificar que no esté completamente vacío
        has_filter = any(
            params.get(k) is not None and params.get(k) != ''
            for k in ('distrito', 'tipo_propiedad', 'operacion',
                      'precio_min', 'precio_max', 'habitaciones', 'area_min',
                      'semantic_query')
        )
        return has_filter

    # ── Ejecución principal ───────────────────────────────────────────────

    def execute(
        self,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> SkillResult:
        """
        Ejecuta la búsqueda híbrida de propiedades.

        Args:
            params: Parámetros de búsqueda (ver parameters_schema)
            context: Contexto opcional con user_level, profile, etc.

        Returns:
            SkillResult con los resultados de la búsqueda
        """
        try:
            # ── Paso 1: Determinar modo de búsqueda ──
            modo = self._determinar_modo(params)
            logger.info(
                f"Ejecutando busqueda_propiedades (modo: {modo}) "
                f"con params: {self._sanitize_params(params)}"
            )

            if modo == 'sin_parametros':
                # Intentar obtener conteo de propiedades disponibles
                try:
                    from propifai.models import PropifaiProperty
                    total_props = PropifaiProperty.objects.count()
                    return SkillResult.ok(
                        data=[],
                        message=f"Hay {total_props} propiedades disponibles en la base de datos. "
                                "Por favor indica qué tipo de propiedad buscas, "
                                "en qué distrito, o qué características debe tener para mostrarte las mejores opciones.",
                        metadata={'modo': modo, 'total_properties': total_props},
                        skill_name=self.name
                    )
                except Exception:
                    return SkillResult.ok(
                        data=[],
                        message="No se especificaron criterios de búsqueda. "
                                "Por favor indica qué tipo de propiedad buscas, "
                                "en qué distrito, o qué características debe tener.",
                        metadata={'modo': modo},
                        skill_name=self.name
                    )

            # ── Paso 2: Filtrado SQL sobre field_values ──
            # context puede ser dict (legacy) o ExecutionContext (nuevo orchestrator)
            if hasattr(context, 'permissions'):
                # Es ExecutionContext — extraer nivel desde metadata o default
                user_level = context.metadata.get('user_level', 1) if hasattr(context, 'metadata') else 1
            else:
                user_level = (context or {}).get('user_level', 1)
            colecciones = self._obtener_colecciones(params.get('colecciones'), user_level)

            if not colecciones:
                return SkillResult.ok(
                    data=[],
                    message="No hay colecciones de propiedades disponibles.",
                    metadata={
                        'modo': modo,
                        'total_encontrados': 0,
                        'total_retornados': 0,
                        'filtros_aplicados': self._extract_filters(params),
                    },
                    skill_name=self.name
                )

            documentos = self._filtrar_por_sql(params, colecciones)
            total_sql = len(documentos)

            if total_sql == 0:
                return SkillResult.ok(
                    data=[],
                    message="No se encontraron propiedades con los filtros especificados.",
                    metadata={
                        'modo': modo,
                        'total_encontrados': 0,
                        'total_retornados': 0,
                        'filtros_aplicados': self._extract_filters(params),
                    },
                    skill_name=self.name
                )

            # ── Paso 3: Re-ranking semántico ──
            if modo in ('hibrido', 'solo_semantico'):
                documentos = self._reranking_semantico(
                    documentos, params.get('semantic_query', '')
                )

            # ── Paso 4: Construir resultado ──
            top_k = params.get('top_k', 0)
            if top_k and top_k > 0:
                documentos_retornados = documentos[:top_k]
            else:
                documentos_retornados = documentos  # Sin límite

            # Extraer field_values para la respuesta
            resultados = []
            for doc, score in documentos_retornados:
                field_values = self._build_field_values_to_display(doc)
                resultados.append({
                    'document_id': str(doc.id),
                    'collection_name': doc.collection.name,
                    'source_id': doc.source_id,
                    'similarity': score,
                    'field_values': field_values,
                    'created_at': doc.created_at.isoformat() if doc.created_at else None,
                })

            mensaje = (
                f"Se encontraron {total_sql} propiedades"
                f"{f', mostrando {len(resultados)}' if top_k and top_k < total_sql else ''}"
                f"{' en ' + params.get('distrito', '') if params.get('distrito') else ''}"
                f"{' de tipo ' + params.get('tipo_propiedad', '') if params.get('tipo_propiedad') else ''}"
                f"."
            )

            return SkillResult.ok(
                data=resultados,
                message=mensaje,
                metadata={
                    'modo': modo,
                    'total_encontrados_sql': total_sql,
                    'total_retornados': len(resultados),
                    'filtros_aplicados': self._extract_filters(params),
                    'semantic_query': params.get('semantic_query'),
                },
                skill_name=self.name
            )

        except Exception as e:
            logger.error(f"Error en busqueda_propiedades: {e}", exc_info=True)
            return SkillResult.error(
                message=f"Error interno al buscar propiedades: {str(e)}",
                skill_name=self.name
            )

    # ── Paso 1: Determinar modo ───────────────────────────────────────────

    def _determinar_modo(self, params: Dict[str, Any]) -> str:
        """
        Determina el modo de búsqueda según los parámetros recibidos.

        Returns:
            'solo_sql' | 'solo_semantico' | 'hibrido' | 'sin_parametros'
        """
        tiene_filtros = any(
            params.get(k) is not None and params.get(k) != ''
            for k in ('distrito', 'tipo_propiedad', 'operacion',
                      'precio_min', 'precio_max', 'habitaciones', 'area_min')
        )
        tiene_semantica = bool(
            params.get('semantic_query') and
            params['semantic_query'].strip()
        )

        if tiene_filtros and tiene_semantica:
            return 'hibrido'
        elif tiene_filtros:
            return 'solo_sql'
        elif tiene_semantica:
            return 'solo_semantico'
        else:
            return 'sin_parametros'

    # ── Paso 2: Filtrado SQL ──────────────────────────────────────────────

    def _obtener_colecciones(
        self,
        colecciones_nombres: Optional[List[str]],
        user_level: int
    ) -> List[IntelligenceCollection]:
        """
        Obtiene las colecciones a buscar.

        Si no se especifican nombres, detecta automáticamente las colecciones
        que contienen propiedades por su nombre.
        """
        queryset = IntelligenceCollection.objects.filter(
            is_active=True,
            min_level__lte=user_level
        )

        if colecciones_nombres:
            queryset = queryset.filter(name__in=colecciones_nombres)
        else:
            # Detectar colecciones de propiedades por nombre
            q = Q()
            for keyword in COLECCIONES_PROPIEDADES_KEYWORDS:
                q |= Q(name__icontains=keyword)
            queryset = queryset.filter(q)

        return list(queryset)

    def _filtrar_por_sql(
        self,
        params: Dict[str, Any],
        colecciones: List[IntelligenceCollection]
    ) -> List[Tuple[IntelligenceDocument, float]]:
        """
        Aplica filtros SQL sobre field_values de IntelligenceDocument.

        Returns:
            Lista de tuplas (documento, similarity_score_inicial)
            similarity_score_inicial = 0.5 para modo solo_sql
        """
        # Query base: documentos de las colecciones seleccionadas
        queryset = IntelligenceDocument.objects.filter(
            collection__in=colecciones,
            embedding__isnull=False  # Solo documentos con embedding
        ).select_related('collection')

        # Aplicar filtros usando JSONField key transforms de Django
        filter_q = Q()

        # Filtro por distrito (case-insensitive via field_values)
        distrito = params.get('distrito')
        if distrito:
            # Buscar en varios campos posibles donde puede estar el distrito
            distrito_q = Q()
            for campo_distrito in ('district_name', 'district', 'distrito'):
                distrito_q |= Q(**{
                    f'field_values__{campo_distrito}__iexact': distrito
                })
            filter_q &= distrito_q

        # Filtro por tipo de propiedad (normalizado)
        tipo = params.get('tipo_propiedad')
        if tipo:
            tipo_normalizado = self._normalizar_tipo(tipo)
            tipo_q = Q()
            for campoTipo in ('property_type_id', 'tipo_propiedad', 'property_type'):
                tipo_q |= Q(**{
                    f'field_values__{campoTipo}__iexact': tipo_normalizado
                })
            filter_q &= tipo_q

        # Filtro por operación (venta/alquiler)
        operacion = params.get('operacion')
        if operacion:
            op_normalizada = self._normalizar_operacion(operacion)
            if op_normalizada:
                op_q = Q()
                for campoOp in ('operation_type', 'operacion', 'tipo_operacion'):
                    op_q |= Q(**{
                        f'field_values__{campoOp}__iexact': op_normalizada
                    })
                filter_q &= op_q

        # Filtros de precio (rango numérico)
        precio_min = params.get('precio_min')
        precio_max = params.get('precio_max')
        if precio_min is not None or precio_max is not None:
            # Los precios pueden estar en varios campos
            precio_q = Q()
            for campo_precio in ('price', 'precio', 'precio_venta', 'precio_alquiler', 'sale_price'):
                campo_q = Q()
                if precio_min is not None:
                    campo_q &= Q(**{f'field_values__{campo_precio}__gte': precio_min})
                if precio_max is not None:
                    campo_q &= Q(**{f'field_values__{campo_precio}__lte': precio_max})
                precio_q |= campo_q
            filter_q &= precio_q

        # Filtro por habitaciones (mayor o igual)
        habitaciones = params.get('habitaciones')
        if habitaciones is not None:
            hab_q = Q()
            for campo_hab in ('bedrooms', 'habitaciones', 'num_habitaciones', 'dormitorios'):
                hab_q |= Q(**{f'field_values__{campo_hab}__gte': habitaciones})
            filter_q &= hab_q

        # Filtro por área mínima
        area_min = params.get('area_min')
        if area_min is not None:
            area_q = Q()
            for campo_area in ('built_area', 'area_construida', 'area', 'total_area', 'land_area'):
                area_q |= Q(**{f'field_values__{campo_area}__gte': area_min})
            filter_q &= area_q

        # ── Filtro por availability_status ──
        # El campo real en field_values es 'availability_status'
        # Valores: available (disponible), sold (vendida), paused, unavailable, catchment
        # Por defecto (sin condicion explícita) → solo 'available'
        # Si el usuario pide "vendidas" → 'sold'
        condicion = params.get('condicion')
        if condicion:
            # Mapear valores español → inglés
            cond_map = {
                'disponible': 'available',
                'vendida': 'sold',
                'vendido': 'sold',
                'reservada': 'catchment',
                'reservado': 'catchment',
                'pausada': 'paused',
                'pausado': 'paused',
                'no disponible': 'unavailable',
            }
            valor_busqueda = cond_map.get(condicion.lower().strip(), condicion.lower().strip())
            condicion_q = Q()
            for campo_cond in ('availability_status', 'condicion', 'estado', 'status'):
                condicion_q |= Q(**{
                    f'field_values__{campo_cond}__iexact': valor_busqueda
                })
            filter_q &= condicion_q
        else:
            # Por defecto: SOLO propiedades 'available' (disponibles en venta)
            condicion_q = Q()
            for campo_cond in ('availability_status', 'condicion', 'estado', 'status'):
                condicion_q |= Q(**{
                    f'field_values__{campo_cond}__iexact': 'available'
                })
            filter_q &= condicion_q

        # Ejecutar query
        if filter_q:
            queryset = queryset.filter(filter_q)

        documentos = list(queryset)

        # En modo solo_sql, asignar similarity=0.5 (neutro)
        return [(doc, 0.5) for doc in documentos]

    # ── Paso 3: Re-ranking semántico ──────────────────────────────────────

    def _reranking_semantico(
        self,
        documentos: List[Tuple[IntelligenceDocument, float]],
        semantic_query: str
    ) -> List[Tuple[IntelligenceDocument, float]]:
        """
        Re-ordena documentos por similitud semántica con la query.

        Genera embedding de la semantic_query y calcula similitud coseno
        contra el embedding de cada documento.

        Args:
            documentos: Lista de (documento, score_actual)
            semantic_query: Texto semántico para comparar

        Returns:
            Lista re-ordenada por similitud descendente
        """
        if not documentos or not semantic_query:
            return documentos

        try:
            # Generar embedding de la query semántica (modo query)
            query_embedding = RAGService.generate_embedding(
                semantic_query, mode='query'
            )
            if not query_embedding:
                logger.warning(
                    "No se pudo generar embedding para reranking semántico. "
                    "Usando orden original."
                )
                return documentos

            query_vector = np.frombuffer(query_embedding, dtype=np.float32)

            # Calcular similitud para cada documento
            resultados_con_score = []
            for doc, _ in documentos:
                try:
                    if doc.embedding:
                        doc_vector = np.frombuffer(doc.embedding, dtype=np.float32)
                        similarity = float(np.dot(query_vector, doc_vector) / (
                            np.linalg.norm(query_vector) * np.linalg.norm(doc_vector)
                        ))
                    else:
                        similarity = 0.0  # Sin embedding, score 0 pero no excluir
                except Exception as e:
                    logger.warning(
                        f"Error calculando similitud para documento {doc.id}: {e}"
                    )
                    similarity = 0.0

                resultados_con_score.append((doc, similarity))

            # Ordenar por similitud descendente
            resultados_con_score.sort(key=lambda x: x[1], reverse=True)

            logger.info(
                f"Re-ranking semántico completado: "
                f"{len(resultados_con_score)} documentos re-ordenados"
            )

            return resultados_con_score

        except Exception as e:
            logger.error(f"Error en re-ranking semántico: {e}")
            return documentos

    # ── Helpers ───────────────────────────────────────────────────────────

    def _normalizar_tipo(self, tipo: str) -> str:
        """Normaliza el tipo de propiedad."""
        if not tipo:
            return ''
        tipo_lower = tipo.lower().strip()
        return TIPO_PROPIEDAD_MAP.get(tipo_lower, tipo)

    def _normalizar_operacion(self, operacion: str) -> str:
        """Normaliza la operación."""
        if not operacion:
            return ''
        op_lower = operacion.lower().strip()
        return OPERACION_MAP.get(op_lower, op_lower)

    def _extract_filters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Extrae solo los filtros aplicados (sin semantic_query ni top_k)."""
        return {
            k: v for k, v in params.items()
            if k not in ('semantic_query', 'top_k', 'colecciones')
            and v is not None and v != ''
        }

    def _sanitize_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitiza params para logging (oculta valores sensibles)."""
        return {
            k: v for k, v in params.items()
            if v is not None and v != ''
        }

    def _build_field_values_to_display(self, doc: IntelligenceDocument) -> Dict[str, Any]:
        """
        Extrae field_values del documento, limitados a display_fields de la colección.

        Similar a RAGService._build_field_values_to_display pero independiente.
        """
        try:
            collection = doc.collection
            display_fields = getattr(collection, 'display_fields', None)

            if not doc.field_values:
                return {}

            if display_fields and isinstance(display_fields, list):
                return {
                    k: v for k, v in doc.field_values.items()
                    if k in display_fields
                }

            # Si no hay display_fields, retornar todo
            return dict(doc.field_values)

        except Exception as e:
            logger.warning(f"Error extrayendo field_values del documento {doc.id}: {e}")
            return {}
