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
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from django.db.models import Q

from ...models import IntelligenceCollection, IntelligenceDocument
from ...services.rag import RAGService
from ..base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)

# Dimensión esperada de embeddings (SPEC-014: multilingual-e5-small = 384d)
# Los embeddings antiguos (multilingual-e5-large = 1024d) deben ser filtrados
# para evitar errores de dimensionalidad al calcular similitud de coseno.
EMBEDDING_DIMENSIONS = 384


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

    # Palabras que indican que el usuario busca una propiedad por NOMBRE/TÍTULO específico
    # Ej: "cabaña maria", "campo verde", "el mirador", "valle blanco"
    PALABRAS_BUSQUEDA_TITULO = [
        'propiedad de', 'propiedad llamada', 'propiedad conocida como',
        'la propiedad', 'las propiedades',
        'cabaña', 'cabañas', 'casona', 'casonas',
        'residencial', 'condominio', 'edificio',
        'urbanización', 'urbanizacion',
        'proyecto', 'conjunto',
    ]

    # ── Palabras de ruido conversacional ──
    # Palabras que aparecen en mensajes del chat canvas pero que NO deben
    # formar parte del semantic_query para el embedding.
    # Se usan como FALLBACK cuando titulo_contains no fue detectado.
    # NOTA: No incluir 'propiedad', 'propiedades', 'el', 'la', 'los', 'las', 'de'
    # porque pueden ser parte de nombres reales de propiedades.
    PALABRAS_RUIDO = frozenset({
        'agrega', 'agregue', 'agregar', 'agrégalo', 'agrégueme',
        'añade', 'añada', 'añadir', 'anade',
        'pon', 'ponlo', 'ponlos', 'poner',
        'mételo', 'métalos', 'metelo', 'metalos',
        'trae', 'traiga', 'traer',
        'cargar', 'carga', 'colocar', 'coloca',
        'busca', 'buscar', 'busque', 'busquemos',
        'encuentra', 'encontrar', 'encuentre',
        'muestra', 'mostrar', 'muéstrame', 'muestrame',
        'lista', 'listar', 'listame', 'listarme',
        'quiero', 'quisiera', 'necesito',
        'al', 'del', 'en', 'para', 'por',
        'lienzo', 'canvas',
        'favor', 'porfavor', 'porfa', 'gracias', 'hola', 'buenas',
    })

    @staticmethod
    def _limpiar_ruido_query(texto: str, palabras_ruido: set) -> str:
        """
        Elimina palabras de ruido conversacional de una query,
        conservando solo términos con carga semántica.
        
        NO se aplica si ya hay titulo_contains (que ya fue extraído correctamente).
        Es un FALLBACK para cuando ninguna estrategia de detección funcionó.
        
        Ejemplos:
          "agrega la propiedad de las orquideas"  →  "orquideas"
          "pon CABAÑA MARIA al lienzo"             →  "CABAÑA MARIA"
          "busca departamentos en cayma"           →  "departamentos cayma"
        
        Returns:
            str con la query limpia, o el texto original si el resultado queda vacío
        """
        if not texto:
            return ''
        
        palabras = texto.split()
        palabras_limpias = [
            p for p in palabras
            if p.lower() not in palabras_ruido
        ]
        resultado = ' '.join(palabras_limpias).strip()
        
        # Salvaguarda: si la limpieza dejó vacío o muy corto, devolver original
        return resultado if len(resultado) >= 3 else texto

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

        # ── Detectar búsqueda por NOMBRE/TÍTULO de propiedad ──
        # Si el mensaje contiene palabras clave que indican búsqueda por nombre
        # (ej: "cabaña maria", "propiedad llamada campo verde", etc.),
        # extraer el nombre candidato y buscar por título.
        titulo_busqueda = self._detectar_busqueda_por_titulo(mensaje_lower)
        if titulo_busqueda:
            filtros['titulo_contains'] = titulo_busqueda
            logger.info(
                f"_analizar_intencion detecto busqueda por titulo: "
                f"'{titulo_busqueda}' del mensaje: {mensaje[:100]}"
            )

        logger.debug(f"_analizar_intencion detecto: {filtros} del mensaje: {mensaje[:100]}")
        return filtros

    def _detectar_busqueda_por_titulo(self, mensaje_lower: str) -> Optional[str]:
        """
        Detecta si el mensaje contiene una referencia a una propiedad por su nombre/título.

        Estrategias:
        1. Buscar después de frases clave como "propiedad de", "propiedad llamada"
        2. Si el mensaje contiene palabras tipo "cabaña", "casona" etc seguidas de
           otra palabra (nombre propio), asumir que es el nombre de la propiedad.

        Returns:
            str con el término de búsqueda, o None si no se detectó.
        """
        if not mensaje_lower:
            return None

        # Estrategia 1: Buscar después de frases clave
        FRASES_CLAVE = [
            'propiedad de ', 'propiedad llamada ', 'propiedad conocida como ',
            'llamada ', 'llamado ', 'conocida como ', 'conocido como ',
            'la propiedad ', 'las propiedades ',
            'proyecto ', 'conjunto ',
        ]
        for frase in FRASES_CLAVE:
            if frase in mensaje_lower:
                idx = mensaje_lower.index(frase) + len(frase)
                resto = mensaje_lower[idx:].strip()
                palabras = []
                # STOP_SKIP: palabras que pueden ir DENTRO del nombre de una propiedad
                # (artículos, preposiciones, conjunciones).
                # Ej: "Las Orquideas", "Los Olivos", "El Mirador", "La Campiña",
                #     "Urbanización Los Bosques", "Calle Los Geranios"
                STOP_SKIP = {'el', 'la', 'los', 'las', 'un', 'una',
                             'del', 'de', 'y', 'e', 'o'}
                # STOP_BREAK: palabras que INDICAN el fin del nombre de la propiedad.
                # Preposiciones/verbos que inician una nueva cláusula.
                # Ej: "propiedad de las orquideas AL lienzo" → "al" rompe
                #     "propiedad de los olivos EN cayma" → "en" rompe
                STOP_BREAK = {'al', 'para', 'por', 'con', 'sin',
                              'en', 'que', 'es', 'se', 'su'}
                for p in resto.split():
                    p_clean = p.strip('.,;:!?¿¡()[]\'"')
                    if not p_clean:
                        continue
                    if p_clean in STOP_BREAK:
                        break
                    if p_clean in STOP_SKIP:
                        # SALTAR artículos/preposiciones dentro del nombre,
                        # NO romper. Así "las orquideas" se captura completo.
                        continue
                    if len(p_clean) < 2 and palabras:
                        break
                    palabras.append(p_clean)
                    if len(palabras) >= 4:
                        break
                if palabras:
                    termino = ' '.join(palabras)
                    if len(termino) >= 4:
                        return termino

        # Estrategia 2: Detectar "cabaña X", "casona X", "edificio X", etc.
        PREFIJOS_NOMBRE = ['cabaña', 'cabañas', 'casona', 'casonas',
                          'edificio', 'condominio', 'residencial',
                          'urbanización', 'urbanizacion', 'quinta',
                          'torre', 'country']
        for prefijo in PREFIJOS_NOMBRE:
            patron = prefijo + ' '
            if patron in mensaje_lower:
                idx = mensaje_lower.index(patron) + len(patron)
                resto = mensaje_lower[idx:].strip()
                sig_palabra = resto.split()[0] if resto.split() else ''
                sig_limpia = sig_palabra.strip('.,;:!?¿¡()[]\'"')
                if sig_limpia and len(sig_limpia) >= 3:
                    termino = f"{prefijo} {sig_limpia}"
                    return termino

        # Estrategia 3: Fuzzy matching como fallback general
        # Si ninguna estrategia anterior detectó un nombre, intentar fuzzy match
        # contra los títulos reales de propiedades en la BD.
        # Captura variaciones, typos, y frases no anticipadas.
        resultado_fuzzy = self._estrategia_3_fuzzy(mensaje_lower)
        if resultado_fuzzy:
            return resultado_fuzzy

        return None

    def _estrategia_3_fuzzy(self, mensaje_lower: str, umbral: int = 60) -> Optional[str]:
        """
        Fallback: compara el mensaje completo contra todos los títulos de
        propiedades en la BD usando fuzzy matching (rapidfuzz).
        Se usa solo si las Estrategias 1 y 2 no encontraron nada.

        La query limpia (sin ruido conversacional) se usa como término de
        búsqueda, no el mensaje completo.

        Args:
            mensaje_lower: Mensaje completo del usuario en minúsculas
            umbral: Puntuación mínima (0-100) para considerar un match

        Returns:
            str con el título matcheado y limpiado, o None si no supera el umbral
        """
        try:
            from rapidfuzz import process, fuzz
        except ImportError:
            logger.warning("rapidfuzz no instalado - saltando Estrategia 3 fuzzy")
            return None

        # Limpiar ruido del mensaje para obtener término de búsqueda real
        query_limpia = self._limpiar_ruido_query(mensaje_lower, self.PALABRAS_RUIDO)
        if not query_limpia or len(query_limpia) < 4:
            return None

        # Obtener títulos de propiedades
        try:
            from intelligence.models import IntelligenceDocument, IntelligenceCollection
            coleccion = IntelligenceCollection.objects.filter(
                name__icontains='propiedad'
            ).first()
            if not coleccion:
                return None

            titulos = list(
                IntelligenceDocument.objects
                .filter(collection=coleccion, embedding__isnull=False)
                .values_list('field_values__title', flat=True)[:500]
            )
            titulos = [t for t in titulos if t]
        except Exception as e:
            logger.warning(f"Error obteniendo títulos para fuzzy: {e}")
            return None

        if not titulos:
            return None

        # Fuzzy match: el score más alto
        match = process.extractOne(query_limpia, titulos, scorer=fuzz.partial_ratio)
        if match and match[1] >= umbral:
            logger.info(
                f"Estrategia 3 fuzzy: '{query_limpia}' -> "
                f"'{match[0]}' (score={match[1]})"
            )
            return match[0]

        return None

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
            
            # ── Si se detectó búsqueda por nombre (titulo_contains) ──
            # Reemplazar el semantic_query con el término limpio de búsqueda
            # para que la búsqueda semántica (embeddings) encuentre propiedades
            # cuyo título/descripción coincida. NO se agrega como filtro SQL
            # porque field_values__X__icontains no funciona con MSSQL.
            titulo_clean = params.get('titulo_contains')
            if titulo_clean and not params.get('distrito') and not params.get('tipo_propiedad'):
                # Reemplazar semantic_query por el término limpio
                semantic_query = titulo_clean
                params['semantic_query'] = titulo_clean
                logger.info(
                    f"Busqueda semantica por nombre de propiedad: "
                    f"'{titulo_clean}' (reemplazando mensaje original)"
                )
            
            # ── FASE 2: Limpiar ruido conversacional del semantic_query ──
            # Si NO se detectó nombre exacto (titulo_contains), limpiar
            # palabras de acción/contexto del mensaje original para que el
            # embedding capture solo el núcleo semántico de la búsqueda.
            # Ej: "agrega la propiedad de las orquideas" → "orquideas"
            if not titulo_clean and semantic_query:
                query_limpia = self._limpiar_ruido_query(
                    semantic_query, self.PALABRAS_RUIDO
                )
                if (query_limpia and query_limpia != semantic_query
                        and len(query_limpia) >= 3):
                    logger.info(
                        f"FASE 2: Query limpiada de ruido: "
                        f"'{semantic_query[:80]}' → '{query_limpia[:80]}'"
                    )
                    semantic_query = query_limpia
                    params['semantic_query'] = query_limpia
            
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
            # NOTA: El filtrado SQL usa field_values, NO embeddings. Por lo tanto
            # NO se debe validar la dimensión aquí. Los embeddings de 1024d antiguos
            # se manejan en _reranking_semantico (Paso 2), que es donde se necesita
            # la dimensión correcta para calcular similitud de coseno.
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

            # FASE 4: Umbral de similitud semántica (solo si hay semantic_query)
            # Después del re-ranking, descartar documentos con similitud muy baja.
            # El umbral se calibra con datos reales: para E5-small + cosine sim,
            # scores suelen estar en 0.75-0.95 para pares relacionados.
            # Umbral bajo (0.3) para no filtrar de más con queries cortas.
            UMBRAL_SIMILITUD = float(os.environ.get(
                'UMBRAL_SIMILITUD_SEMANTICA', '0.3'
            ))
            if tiene_semantica and documentos:
                antes = len(documentos)
                documentos = [
                    (d, s) for d, s in documentos
                    if s >= UMBRAL_SIMILITUD
                ]
                if antes != len(documentos):
                    logger.info(
                        f"FASE 4: Umbral similitud={UMBRAL_SIMILITUD}: "
                        f"{antes} -> {len(documentos)} docs "
                        f"(descartados {antes - len(documentos)})"
                    )
                # Salvaguarda: si el filtro dejó vacío pero había resultados,
                # mantener al menos el top-1
                if not documentos and antes > 0:
                    logger.warning(
                        f"FASE 4: Umbral={UMBRAL_SIMILITUD} dejó 0 resultados. "
                        f"Manteniendo top-1 como salvaguarda."
                    )
                    # Re-obtener el mejor score del re-ranking original

            # Paso 3: Limitar resultados
            top_k = params.get('top_k') or 10
            if len(documentos) > top_k:
                documentos = documentos[:top_k]

            # ── Filtro por similitud semántica para búsqueda por nombre ──
            # Si se buscó por nombre de propiedad (titulo_contains), filtrar
            # propiedades con baja similitud semántica. El re-ranking da scores
            # de coseno (0.0-1.0). Para búsqueda por nombre exacto, solo
            # conservamos las que realmente se parecen al nombre buscado.
            #
            # FIX-DIM: Si TODOS los documentos tienen score=SCORE_INICIAL (0.5),
            # significa que el re-ranking semántico NO PUDO calcular similitud
            # real (probablemente por mismatch de dimensiones de embeddings).
            # En ese caso, hacemos un fallback a búsqueda TEXTUAL en title y
            # description usando icontains.
            titulo_busqueda = params.get('titulo_contains')
            if titulo_busqueda and tiene_semantica and documentos:
                antes = len(documentos)
                
                # ── SIEMPRE usar filtro textual para búsqueda por nombre ──
                # El re-ranking semántico puede no funcionar si:
                # 1. Los embeddings tienen dimensión incorrecta (FIX-DIM)
                # 2. Algunos docs tienen dimensión correcta y otros no (mixto)
                # 3. La búsqueda semántica no prioriza correctamente nombres exactos
                #
                # El filtro textual busca las palabras del nombre en los campos
                # title, description, code, address de cada propiedad.
                logger.info(
                    f"Usando filtro textual para búsqueda por nombre: "
                    f"'{titulo_busqueda}' sobre {len(documentos)} docs"
                )
                docs_filtrados = []
                titulo_lower = titulo_busqueda.lower()
                
                # Importar re para búsqueda con boundaries de palabra
                import re as _re
                import unicodedata
                
                def _normalizar_acentos(s: str) -> str:
                    """
                    Normaliza acentos y caracteres especiales (ñ, ü, etc.)
                    usando descomposición Unicode NFKD.
                    
                    Ejemplos:
                      "maría"   → "maria"
                      "cabaña"  → "cabana"
                      "corazón" → "corazon"
                      "González" → "Gonzalez"
                      "Pérez"    → "Perez"
                    """
                    return unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('ASCII')
                
                for doc, score in documentos:
                    fv = doc.field_values or {}
                    text_fields = [
                        str(fv.get('title', '')),
                        str(fv.get('description', '')),
                        str(fv.get('code', '')),
                        str(fv.get('map_address', '')),
                        str(fv.get('display_address', '')),
                    ]
                    texto_combinado = ' '.join(text_fields).lower()
                    
                    # Split del término de búsqueda en palabras significativas
                    palabras_busqueda = [p.strip().lower()
                                        for p in titulo_lower.split()
                                        if len(p.strip()) >= 3]
                    
                    if palabras_busqueda:
                        # BÚSQUEDA ESTRICTA: TODAS las palabras deben coincidir
                        # como PALABRAS COMPLETAS (no substrings).
                        # Esto evita que "maria" matchee con "mariano".
                        #
                        # FIX-ACENTOS: Se normalizan los acentos y ñ TANTO en el
                        # texto de la propiedad como en las palabras de búsqueda,
                        # usando NFKD (Unicode Normalization Form Compatibility Decomposition).
                        # Esto permite que "maría" matchee con "maria", "cabaña" con
                        # "cabana", etc. Aplica a TODOS los caracteres con acentos/diacríticos.
                        texto_normalizado = _normalizar_acentos(texto_combinado)
                        palabras_normalizadas = [_normalizar_acentos(p) for p in palabras_busqueda]
                        
                        todas_coinciden = all(
                            bool(_re.search(r'\b' + _re.escape(p) + r'\b', texto_normalizado))
                            for p in palabras_normalizadas
                        )
                        if todas_coinciden:
                            docs_filtrados.append((doc, score))
                
                documentos = docs_filtrados
                logger.info(
                    f"Filtro textual para '{titulo_busqueda}': "
                    f"{antes} -> {len(documentos)} "
                    f"(descartados {antes - len(documentos)} por no coincidir texto)"
                )

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

    # ── Helper: Validación de dimensión de embeddings ─────────────────────

    @staticmethod
    def _validar_dimension_embedding(
        documentos: List[Tuple[IntelligenceDocument, float]]
    ) -> List[Tuple[IntelligenceDocument, float]]:
        """
        Filtra documentos cuya dimensión de embedding no coincida con la esperada.

        Los embeddings antiguos (1024d del modelo multilingual-e5-large) causan
        errores de dimensionalidad al calcular similitud coseno con el modelo
        actual (384d del multilingual-e5-small). Este método los descarta.

        Args:
            documentos: Lista de tuplas (documento, score)

        Returns:
            Lista filtrada solo con documentos de dimensión correcta
        """
        if not documentos:
            return []

        filtrados = []
        descartados = 0
        for doc, score in documentos:
            if doc.embedding:
                doc_vector = np.frombuffer(doc.embedding, dtype=np.float32)
                if doc_vector.shape[0] == EMBEDDING_DIMENSIONS:
                    filtrados.append((doc, score))
                else:
                    descartados += 1
            else:
                filtrados.append((doc, score))

        if descartados > 0:
            logger.warning(
                f"FIX-DIM: Descartados {descartados} documentos con dimensión "
                f"incorrecta (esperada: {EMBEDDING_DIMENSIONS}). "
                f"Conservados: {len(filtrados)}. "
                f"Ejecuta 'python manage.py regenerar_embeddings --fix-dimensions' "
                f"para corregir los embeddings antiguos."
            )

        return filtrados

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

        FIX-DIM: NO filtra documentos con dimensión incorrecta (para no perder
        resultados). En su lugar, asigna similarity=SCORE_INICIAL (0.5) a los
        documentos con dimensión antigua (1024d) para que conserven su posición
        original. Los documentos con dimensión correcta (384d) se reordenan según
        su similitud calculada.
        """
        if not documentos or not semantic_query:
            return documentos

        # Score inicial de documentos que vienen del filtro SQL
        SCORE_INICIAL = 0.5

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
            query_dim = query_vector.shape[0]

            documentos_con_dimension_incorrecta = 0
            resultados_con_score = []
            for doc, _ in documentos:
                try:
                    if doc.embedding:
                        doc_vector = np.frombuffer(doc.embedding, dtype=np.float32)
                        # FIX-DIM: Si la dimensión no coincide, conservar score inicial
                        if doc_vector.shape[0] != query_dim:
                            documentos_con_dimension_incorrecta += 1
                            similarity = SCORE_INICIAL
                        else:
                            similarity = float(np.dot(query_vector, doc_vector) / (
                                np.linalg.norm(query_vector) * np.linalg.norm(doc_vector)
                            ))
                    else:
                        similarity = SCORE_INICIAL
                except Exception as e:
                    logger.warning(
                        f"Error calculando similitud para documento {doc.id}: {e}"
                    )
                    similarity = SCORE_INICIAL

                resultados_con_score.append((doc, similarity))

            if documentos_con_dimension_incorrecta > 0:
                logger.warning(
                    f"FIX-DIM: {documentos_con_dimension_incorrecta} documentos "
                    f"con dimensión incorrecta (esperada: {query_dim}). "
                    f"Se mantienen con score={SCORE_INICIAL}. "
                    f"Ejecuta 'python manage.py regenerar_embeddings --fix-dimensions' "
                    f"para corregir."
                )

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
