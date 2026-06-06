"""
BusquedaPropiedadesSkill — Skill de búsqueda híbrida (SQL + semántica) de propiedades.

Implementa los 4 pasos de SPEC-015:
  Paso 1: Determinar modo de búsqueda (solo_sql, solo_semantico, hibrido, sin_parametros)
  Paso 2: Filtrado SQL sobre field_values de IntelligenceDocument
  Paso 3: Re-ranking semántico (solo en modo hibrido o solo_semantico)
  Paso 4: Construir SkillResult estandarizado

CAMBIOS v2 — Adaptado a la colección real `propiedadespropify` (tabla `property` en dbpropify_be):
  - Los campos en field_values usan nombres INGLESES reales de la tabla:
    district_id / district_name, property_type_id / property_type_name, price, etc.
  - Se eliminó el filtro automático de disponibilidad (no hay campo availability_status).
  - Soporta tanto valores FK resueltos (_name) como valores raw (_id).
  - Habitaciones/áreas no están en field_values (están en property_specs),
    por lo que solo se filtran si existen en field_values.
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


# ── MAPEO DE NOMBRES DE CAMPO ──────────────────────────────────────────────
# La colección `propiedadespropify` usa la tabla `property` (dbpropify_be).
# Los field_values contienen nombres REALES de columnas (en INGLÉS).
#
# Para filtros por nombre (FK resuelto vía table_relationships):
#   district_id (FK raw) → district_name (resuelto: "Cayma")
#   property_type_id → property_type_name ("Departamento")
#   operation_type_id → operation_type_name ("Venta")
#   property_status_id → property_status_name ("Disponible")
#   property_condition_id → property_condition_name ("Nueva")
#   currency_id → currency_name ("PEN", "USD")
#   urbanization_id → urbanization_name ("San Borja")
#
# Para filtros de precio: price (directo)
# Para filtros de área/habitaciones: NO existen en property, están en property_specs

# Mapeo de parámetro normalizado → campos posibles en field_values
# Orden: preferir nombre resuelto (_name) primero, luego raw (_id), luego otros
FIELD_MAP = {
    'distrito': ['district_name', 'district_id', 'district', 'distrito'],
    'tipo_propiedad': ['property_type_name', 'property_type_id', 'tipo_propiedad', 'property_type'],
    'operacion': ['operation_type_name', 'operation_type_id', 'operacion', 'operation_type', 'tipo_operacion'],
    'precio': ['price', 'precio', 'sale_price', 'precio_venta'],
    'habitaciones': ['bedrooms', 'habitaciones', 'num_habitaciones', 'dormitorios'],
    'area_min': ['built_area', 'area_construida', 'area', 'total_area', 'land_area'],
    'condicion': ['property_status_name', 'property_condition_name', 'condicion', 'estado', 'status', 'availability_status'],
    'moneda': ['currency_name', 'currency_id', 'moneda', 'currency'],
}

# Mapeo de valores de estado (property_status_name) para filtro condicion
STATUS_MAP = {
    'disponible': 'Disponible',
    'disponibles': 'Disponible',
    'vendida': 'Vendida',
    'vendido': 'Vendida',
    'vendidas': 'Vendida',
    'reservada': 'Reservada',
    'reservado': 'Reservada',
    'reservadas': 'Reservada',
    'pausada': 'Pausada',
    'pausado': 'Pausada',
    'alquilada': 'Alquilada',
    'alquilado': 'Alquilada',
}

TIPO_PROPIEDAD_MAP = {
    'depa': 'Departamento',
    'departamento': 'Departamento',
    'departamentos': 'Departamento',
    'dpto': 'Departamento',
    'casa': 'Casa',
    'casas': 'Casa',
    'vivienda': 'Casa',
    'viviendas': 'Casa',
    'terreno': 'Terreno',
    'terrenos': 'Terreno',
    'lote': 'Lote',
    'lotes': 'Lote',
    'local': 'Local Comercial',
    'locales': 'Local Comercial',
    'local comercial': 'Local Comercial',
    'oficina': 'Oficina',
    'oficinas': 'Oficina',
    'suite': 'Suite',
    'penthouse': 'Penthouse',
    'duplex': 'Dúplex',
    'dúplex': 'Dúplex',
    'loft': 'Loft',
    'departamento': 'Departamento',
    'departamentos': 'Departamento',
}

OPERACION_MAP = {
    'venta': 'Venta',
    'vendo': 'Venta',
    'compro': 'Venta',
    'compra': 'Venta',
    'vender': 'Venta',
    'alquiler': 'Alquiler',
    'alquilo': 'Alquiler',
    'renta': 'Alquiler',
    'alquilar': 'Alquiler',
}

# Colecciones que contienen propiedades (por naming)
COLECCIONES_PROPIEDADES_KEYWORDS = ['propiedad', 'propifai', 'inmueble', 'property']


class BusquedaPropiedadesSkill(BaseSkill):
    """
    Skill de búsqueda híbrida (SQL + semántica) de propiedades.

    Busca en las colecciones IntelligenceCollection que contengan propiedades
    y aplica filtros exactos + re-ranking semántico según los parámetros.

    Los filtros SQL usan los nombres REALES de campos en field_values.
    Soporta tanto valores FK resueltos (_name) como raw (_id).
    """

    name = "busqueda_propiedades"
    description = (
        "Busca propiedades en la base de datos usando filtros exactos "
        "(distrito, tipo, precio, operación) y búsqueda semántica "
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
            'description': 'Estado/condición de la propiedad: Disponible, Vendida, Reservada. Si no se especifica, NO se filtra por estado.',
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
                # Mostrar conteo de propiedades activas/disponibles
                try:
                    from propifai.models import PropifaiProperty
                    total = PropifaiProperty.objects.count()
                    disponibles = PropifaiProperty.objects.filter(
                        property_status_id__in=[1, 2]  # Disponible, En venta
                    ).count()
                    mensaje = (
                        f"Actualmente hay {disponibles} propiedades disponibles en el sistema "
                        f"(de {total} registradas). "
                        "Por favor indica qué tipo de propiedad buscas, "
                        "en qué distrito, o qué características debe tener para mostrarte las mejores opciones."
                    )
                    return SkillResult.ok(
                        data=[],
                        message=mensaje,
                        metadata={'modo': modo, 'total': total, 'disponibles': disponibles},
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
            if hasattr(context, 'permissions'):
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
                documentos_retornados = documentos

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

        Usa FIELD_MAP para traducir parámetros normalizados a los nombres
        de campo REALES que existen en field_values de la colección.

        Soporta:
        - Nombres de campo resueltos (_name): district_name, property_type_name
        - Nombres de campo raw (_id): district_id, property_type_id
        - Campos directos: price, title, description

        Returns:
            Lista de tuplas (documento, similarity_score_inicial)
        """
        queryset = IntelligenceDocument.objects.filter(
            collection__in=colecciones,
            embedding__isnull=False
        ).select_related('collection')

        filter_q = Q()

        # ── Filtro por distrito ──
        distrito = params.get('distrito')
        if distrito:
            distrito_q = Q()
            for campo in FIELD_MAP['distrito']:
                distrito_q |= Q(**{f'field_values__{campo}__iexact': distrito})
            filter_q &= distrito_q

        # ── Filtro por tipo de propiedad ──
        tipo = params.get('tipo_propiedad')
        if tipo:
            tipo_normalizado = self._normalizar_tipo(tipo)
            tipo_q = Q()
            for campo in FIELD_MAP['tipo_propiedad']:
                tipo_q |= Q(**{f'field_values__{campo}__iexact': tipo_normalizado})
            filter_q &= tipo_q

        # ── Filtro por operación ──
        operacion = params.get('operacion')
        if operacion:
            op_normalizada = self._normalizar_operacion(operacion)
            if op_normalizada:
                op_q = Q()
                for campo in FIELD_MAP['operacion']:
                    op_q |= Q(**{f'field_values__{campo}__iexact': op_normalizada})
                filter_q &= op_q

        # ── Filtros de precio (rango numérico) ──
        precio_min = params.get('precio_min')
        precio_max = params.get('precio_max')
        if precio_min is not None or precio_max is not None:
            precio_q = Q()
            for campo in FIELD_MAP['precio']:
                campo_q = Q()
                if precio_min is not None:
                    campo_q &= Q(**{f'field_values__{campo}__gte': precio_min})
                if precio_max is not None:
                    campo_q &= Q(**{f'field_values__{campo}__lte': precio_max})
                precio_q |= campo_q
            filter_q &= precio_q

        # ── Filtro por habitaciones (solo si el campo existe en field_values) ──
        # NOTA: bedrooms/áreas están en property_specs, NO en property.
        # Solo se filtran si el campo existe en field_values.
        habitaciones = params.get('habitaciones')
        if habitaciones is not None:
            hab_q = Q()
            for campo in FIELD_MAP['habitaciones']:
                hab_q |= Q(**{f'field_values__{campo}__gte': habitaciones})
            filter_q &= hab_q

        # ── Filtro por área mínima (solo si el campo existe) ──
        area_min = params.get('area_min')
        if area_min is not None:
            area_q = Q()
            for campo in FIELD_MAP['area_min']:
                area_q |= Q(**{f'field_values__{campo}__gte': area_min})
            filter_q &= area_q

        # ── Filtro por condición/estado (SOLO si el usuario lo pide) ──
        # IMPORTANTE: NO se filtra por defecto. El campo 'condicion' en field_values
        # no existe con ese nombre. El estado real está en property_status_name
        # (resuelto desde property_status_id FK).
        # Si el usuario pide "disponibles", "vendidas", etc., se filtra.
        condicion = params.get('condicion')
        if condicion:
            valor_busqueda = STATUS_MAP.get(
                condicion.lower().strip(), condicion
            )
            condicion_q = Q()
            for campo in FIELD_MAP['condicion']:
                condicion_q |= Q(**{
                    f'field_values__{campo}__iexact': valor_busqueda
                })
            filter_q &= condicion_q
        # Si no se especifica condicion, NO filtrar.
        # Cada colección puede tener o no este campo.

        # Ejecutar query
        if filter_q:
            queryset = queryset.filter(filter_q)

        documentos = list(queryset)

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
        """
        if not documentos or not semantic_query:
            return documentos

        try:
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

            resultados_con_score = []
            for doc, _ in documentos:
                try:
                    if doc.embedding:
                        doc_vector = np.frombuffer(doc.embedding, dtype=np.float32)
                        similarity = float(np.dot(query_vector, doc_vector) / (
                            np.linalg.norm(query_vector) * np.linalg.norm(doc_vector)
                        ))
                    else:
                        similarity = 0.0
                except Exception as e:
                    logger.warning(
                        f"Error calculando similitud para documento {doc.id}: {e}"
                    )
                    similarity = 0.0

                resultados_con_score.append((doc, similarity))

            resultados_con_score.sort(key=lambda x: x[1], reverse=True)
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
        """Sanitiza params para logging."""
        return {
            k: v for k, v in params.items()
            if v is not None and v != ''
        }

    def _build_field_values_to_display(self, doc: IntelligenceDocument) -> Dict[str, Any]:
        """
        Extrae field_values del documento para mostrar al usuario.

        Incluye campos relevantes como: title, price, district_name,
        property_type_name, operation_type_name, property_status_name,
        map_address, etc.

        Si display_fields está configurado, lo respeta.
        Además, siempre incluye los campos FK resueltos (_name) y campos clave.
        """
        try:
            collection = doc.collection
            display_fields = getattr(collection, 'display_fields', None)

            if not doc.field_values:
                return {}

            all_values = dict(doc.field_values)

            if display_fields and isinstance(display_fields, list):
                # Respetar display_fields pero siempre incluir campos _name resueltos
                result = {
                    k: v for k, v in all_values.items()
                    if k in display_fields
                }
                # Agregar campos _name (FK resueltos) aunque no estén en display_fields
                for key, value in all_values.items():
                    if key.endswith('_name') and value is not None and value != '':
                        result[key] = value
                # Asegurar campos clave siempre presentes
                for key in ('title', 'price', 'code'):
                    if key in all_values and key not in result:
                        result[key] = all_values[key]
                return result

            return all_values

        except Exception as e:
            logger.warning(f"Error extrayendo field_values del documento {doc.id}: {e}")
            return {}
