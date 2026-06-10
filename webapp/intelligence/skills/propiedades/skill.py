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
        "Busca propiedades usando búsqueda semántica (embeddings) combinada "
        "con filtros exactos (distrito, tipo, precio). Detecta automáticamente "
        "la intención del usuario: si describe características o propósito, "
        "usa los embeddings; si da valores concretos, aplica filtros exactos. "
        "Soporta cualquier consulta en lenguaje natural."
    )
    category = "busqueda"
    access_level = 1
    is_active = True

    parameters_schema = {
        'distrito': {
            'type': 'string',
            'description': 'Filtro exacto por distrito. Ej: Cayma, Yanahuara, Cercado, Cerro Colorado',
            'required': False,
        },
        'tipo_propiedad': {
            'type': 'string',
            'description': 'Filtro exacto por tipo. Ej: Departamento, Casa, Terreno, Local Comercial, Oficina',
            'required': False,
        },
        'operacion': {
            'type': 'string',
            'description': 'Filtro exacto por operación: venta, alquiler',
            'required': False,
        },
        'precio_min': {
            'type': 'number',
            'description': 'Filtro exacto: precio mínimo',
            'required': False,
        },
        'precio_max': {
            'type': 'number',
            'description': 'Filtro exacto: precio máximo',
            'required': False,
        },
        'habitaciones': {
            'type': 'integer',
            'description': 'Filtro exacto: número mínimo de habitaciones',
            'required': False,
        },
        'area_min': {
            'type': 'number',
            'description': 'Filtro exacto: área mínima en m²',
            'required': False,
        },
        'semantic_query': {
            'type': 'string',
            'description': 'BÚSQUEDA SEMÁNTICA: cualquier texto en lenguaje natural que describa el PROPÓSITO, USO, CARACTERÍSTICAS, UBICACIÓN o cualquier aspecto de la propiedad. El sistema busca por SIGNIFICADO usando embeddings, no por palabras exactas. Ejemplos: "para poner un colegio", "donde acepten perros", "cerca de un colegio", "para negocio", "ambientes amplios y luminosos", "para construir", "frente a parque", "esquinero", "cerca de universidad", "para taller mecánico", "para consultorio médico", "zona tranquila", "para familia grande", "con vista", "para oficina", "todo incluido". USA SIEMPRE este parámetro cuando el usuario describa lo que busca en lenguaje natural, aunque también mencione distritos o tipos específicos (se pueden COMBINAR con los filtros exactos de arriba).',
            'required': False,
        },
        'top_k': {
            'type': 'integer',
            'description': 'Máximo de resultados a retornar. 0 = sin límite',
            'required': False,
        },
        'condicion': {
            'type': 'string',
            'description': 'Filtro exacto por estado: Disponible, Vendida, Reservada',
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

    # ── Analizador de intención ──────────────────────────────────────────

    # Lista de distritos conocidos de Arequipa para detección en mensajes
    DISTRITOS_AREQUIPA = [
        'alto selva alegre', 'arequipa', 'camaná', 'camana', 'cayma',
        'cerro colorado', 'cerrocolorado', 'characato',
        'jacobo hunter', 'jose luis bustamante', 'bustamante', 'rivero',
        'mariano melgar', 'miraflores', 'mollebaya',
        'paucarpata', 'sachaca', 'samuel pastor',
        'socabaya', 'tiabaya', 'uchumayo', 'yanahuara',
        'cercado', 'la joya', 'sabandia', 'yura',
    ]

    def _analizar_intencion(self, mensaje: str) -> Dict[str, Any]:
        """
        Analiza el mensaje del usuario y extrae filtros estructurados
        sin depender de DeepSeek orquestador.

        Detecta:
        - Distritos mencionados
        - Tipos de propiedad (casa, departamento, terreno, local)
        - Operaciones (venta, alquiler)
        - Condiciones (disponible, vendida)
        - Intención de conteo (cuantas, cuantas hay)
        - Intención de ordenamiento (mas caro, mas grande)

        Args:
            mensaje: Mensaje completo del usuario

        Returns:
            Dict con filtros detectados
        """
        if not mensaje:
            return {}

        mensaje_lower = mensaje.lower().strip()
        filtros = {}

        # Detectar distritos
        for distrito in self.DISTRITOS_AREQUIPA:
            if distrito in mensaje_lower:
                # Normalizar: capitalizar primera letra
                filtros['distrito'] = distrito.title()
                break

        # Detectar tipos de propiedad
        for tipo_normalizado, variantes in [
            ('Casa', ['casa', 'casas', 'vivienda', 'viviendas']),
            ('Departamento', ['departamento', 'departamentos', 'depa', 'depas', 'dpto', 'flat']),
            ('Terreno', ['terreno', 'terrenos', 'lote', 'lotes']),
            ('Local Comercial', ['local', 'locales', 'local comercial']),
            ('Oficina', ['oficina', 'oficinas']),
        ]:
            if any(v in mensaje_lower for v in variantes):
                filtros['tipo_propiedad'] = tipo_normalizado
                break

        # Detectar operación
        if any(p in mensaje_lower for p in ['alquiler', 'alquilo', 'alquilar', 'renta']):
            filtros['operacion'] = 'Alquiler'
        elif any(p in mensaje_lower for p in ['venta', 'vendo', 'vende', 'compro', 'compra']):
            filtros['operacion'] = 'Venta'

        # Detectar condición
        if any(p in mensaje_lower for p in ['disponible', 'disponibles']):
            filtros['condicion'] = 'Disponible'
        elif any(p in mensaje_lower for p in ['vendida', 'vendido', 'vendidas']):
            filtros['condicion'] = 'Vendida'

        logger.debug(f"_analizar_intencion detecto: {filtros} del mensaje: {mensaje[:100]}")
        return filtros

    # ── Ejecución principal ───────────────────────────────────────────────

    def execute(
        self,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> SkillResult:
        """
        Búsqueda híbrida inteligente de propiedades.

        FLUJO:
        1. Analizar el mensaje del usuario para extraer filtros automáticamente
        2. Si NO hay parámetros → mostrar conteo general
        3. Si hay semantic_query → búsqueda por EMBEDDINGS (FAISS) primero
        4. Si hay filtros exactos → aplicar sobre resultados semánticos o BD
        5. Siempre ordenar por relevancia (semántica si aplica)

        Args:
            params: Parámetros de búsqueda
            context: Contexto opcional

        Returns:
            SkillResult con resultados
        """
        try:
            # ── Extraer parámetros ──
            semantic_query = (params.get('semantic_query') or '').strip()
            
            # ANALIZAR el mensaje para extraer filtros automáticamente
            # Esto funciona aunque DeepSeek no haya extraído los filtros
            filtros_auto = self._analizar_intencion(semantic_query)
            
            # Combinar filtros automáticos con los que DeepSeek haya extraído
            # Los filtros explícitos de DeepSeek tienen prioridad
            for key, value in filtros_auto.items():
                if key not in params or not params.get(key):
                    params[key] = value
            
            tiene_semantica = bool(semantic_query)
            tiene_filtros_exactos = any(
                params.get(k) is not None and params.get(k) != ''
                for k in ('distrito', 'tipo_propiedad', 'operacion',
                          'precio_min', 'precio_max', 'habitaciones', 'area_min',
                          'condicion')
            )

            # ── Sin parámetros: conteo general ──
            if not tiene_semantica and not tiene_filtros_exactos:
                try:
                    from propifai.models import PropifaiProperty
                    total = PropifaiProperty.objects.count()
                    disponibles = PropifaiProperty.objects.filter(
                        property_status_id__in=[1, 2]
                    ).count()
                    mensaje = (
                        f"Actualmente hay {disponibles} propiedades disponibles "
                        f"(de {total} registradas). "
                        "¿Qué tipo de propiedad buscas o en qué distrito?"
                    )
                    return SkillResult.ok(
                        data=[],
                        message=mensaje,
                        metadata={'total': total, 'disponibles': disponibles},
                        skill_name=self.name
                    )
                except Exception:
                    return SkillResult.ok(
                        data=[],
                        message="Indica qué tipo de propiedad buscas.",
                        metadata={},
                        skill_name=self.name
                    )

            # ── Obtener colecciones ──
            user_level = self._get_user_level(context)
            colecciones = self._obtener_colecciones(params.get('colecciones'), user_level)
            if not colecciones:
                return SkillResult.ok(
                    data=[],
                    message="No hay colecciones de propiedades disponibles.",
                    metadata={'filtros_aplicados': self._extract_filters(params)},
                    skill_name=self.name
                )

            # ── FLUJO ÚNICO: Filtro SQL duro + re-ranking semántico ──
            #
            # 1. SIEMPRE aplicar filtros SQL duros primero (a nivel BD)
            # 2. SI hay semantic_query → re-rank semántico sobre resultados filtrados
            # 3. Si NO → ordenar por defecto

            # Paso 1: Obtener documentos con filtros SQL (si hay)
            if tiene_filtros_exactos:
                documentos = self._filtrar_por_sql(params, colecciones)
                if not documentos:
                    mensaje = "No se encontraron propiedades"
                    if params.get('distrito'):
                        mensaje += f" en {params['distrito']}"
                    if params.get('tipo_propiedad'):
                        mensaje += f" de tipo {params['tipo_propiedad']}"
                    mensaje += "."
                    return SkillResult.ok(
                        data=[], message=mensaje,
                        metadata={'filtros_aplicados': self._extract_filters(params)},
                        skill_name=self.name
                    )
            else:
                # Sin filtros: todos los documentos con embedding
                documentos = [(doc, 0.5) for doc in
                    IntelligenceDocument.objects.filter(
                        collection__in=colecciones, embedding__isnull=False
                    ).select_related('collection')]

            # Paso 2: Re-ranking semántico (si hay semantic_query)
            if tiene_semantica and documentos:
                documentos = self._reranking_semantico(documentos, semantic_query)

            # Paso 3: Limitar resultados
            top_k = params.get('top_k') or 50
            if len(documentos) > top_k:
                documentos = documentos[:top_k]

            # ── Construir resultado ──
            top_k_limit = params.get('top_k', 0)
            if top_k_limit and top_k_limit > 0:
                documentos = documentos[:top_k_limit]

            resultados = []
            for doc, score in documentos:
                field_values = self._build_field_values_to_display(doc)
                resultados.append({
                    'document_id': str(doc.id),
                    'collection_name': doc.collection.name,
                    'source_id': doc.source_id,
                    'similarity': round(score, 4),
                    'field_values': field_values,
                    'created_at': doc.created_at.isoformat() if doc.created_at else None,
                })

            if tiene_semantica:
                mensaje = (
                    f"Se encontraron {len(documentos)} propiedades relacionadas con: {semantic_query}"
                )
            else:
                mensaje = f"Se encontraron {len(documentos)} propiedades"
                if params.get('distrito'):
                    mensaje += f" en {params['distrito']}"
                if params.get('tipo_propiedad'):
                    mensaje += f" de tipo {params['tipo_propiedad']}"
                mensaje += "."

            return SkillResult.ok(
                data=resultados,
                message=mensaje,
                metadata={
                    'total_encontrados': len(resultados),
                    'semantic_query': semantic_query if tiene_semantica else None,
                    'filtros_exactos': self._extract_filters(params) if tiene_filtros_exactos else None,
                    'busqueda_semantica': tiene_semantica,
                },
                skill_name=self.name
            )

        except Exception as e:
            logger.error(f"Error en busqueda_propiedades: {e}", exc_info=True)
            return SkillResult.error(
                message=f"Error al buscar propiedades: {str(e)}",
                skill_name=self.name
            )

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

    @staticmethod
    def _get_user_level(context) -> int:
        """Extrae el nivel de usuario del contexto."""
        if context is None:
            return 1
        if hasattr(context, 'metadata') and context.metadata:
            return context.metadata.get('user_level', 1)
        if isinstance(context, dict):
            return context.get('user_level', 1)
        return 1

    def _aplicar_filtros_exactos(
        self,
        documentos: List[Tuple[IntelligenceDocument, float]],
        params: Dict[str, Any],
    ) -> List[Tuple[IntelligenceDocument, float]]:
        """
        Aplica filtros exactos sobre documentos ya obtenidos por búsqueda semántica.
        Filtra en Python (no en SQL) porque los documentos ya están en memoria.
        """
        if not documentos:
            return []

        resultado = []
        for doc, score in documentos:
            fv = doc.field_values or {}
            if not self._doc_cumple_filtros(fv, params):
                continue
            resultado.append((doc, score))

        return resultado

    def _doc_cumple_filtros(
        self,
        field_values: Dict[str, Any],
        params: Dict[str, Any],
    ) -> bool:
        """Verifica si un documento (field_values) cumple todos los filtros exactos."""
        # Distrito
        distrito = params.get('distrito')
        if distrito:
            coincide = False
            for campo in FIELD_MAP['distrito']:
                val = field_values.get(campo)
                if val and str(val).lower() == distrito.lower():
                    coincide = True
                    break
            if not coincide:
                return False

        # Tipo propiedad
        tipo = params.get('tipo_propiedad')
        if tipo:
            tipo_norm = self._normalizar_tipo(tipo)
            coincide = False
            for campo in FIELD_MAP['tipo_propiedad']:
                val = field_values.get(campo)
                if val and str(val).lower() == tipo_norm.lower():
                    coincide = True
                    break
            if not coincide:
                return False

        # Operación
        operacion = params.get('operacion')
        if operacion:
            op_norm = self._normalizar_operacion(operacion)
            if op_norm:
                coincide = False
                for campo in FIELD_MAP['operacion']:
                    val = field_values.get(campo)
                    if val and str(val).lower() == op_norm.lower():
                        coincide = True
                        break
                if not coincide:
                    return False

        # Precio mínimo
        precio_min = params.get('precio_min')
        if precio_min is not None:
            coincide = False
            for campo in FIELD_MAP['precio']:
                val = field_values.get(campo)
                if val is not None:
                    try:
                        if float(val) >= float(precio_min):
                            coincide = True
                            break
                    except (ValueError, TypeError):
                        pass
            if not coincide:
                return False

        # Precio máximo
        precio_max = params.get('precio_max')
        if precio_max is not None:
            coincide = False
            for campo in FIELD_MAP['precio']:
                val = field_values.get(campo)
                if val is not None:
                    try:
                        if float(val) <= float(precio_max):
                            coincide = True
                            break
                    except (ValueError, TypeError):
                        pass
            if not coincide:
                return False

        # Condición
        condicion = params.get('condicion')
        if condicion:
            valor_busqueda = STATUS_MAP.get(condicion.lower().strip(), condicion)
            coincide = False
            for campo in FIELD_MAP['condicion']:
                val = field_values.get(campo)
                if val and str(val).lower() == valor_busqueda.lower():
                    coincide = True
                    break
            if not coincide:
                return False

        return True

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
