"""
Módulo compartido de scoring para el sistema de matching v3.

Contiene toda la lógica unificada de:
- Filtros duros (10 discriminadores)
- Scoring blando (8 factores ponderados)
- Filtrado final (umbral mínimo + top-K + ranking)

Tanto MatchingEngine (engine.py) como HybridMatchingSkill (matching_hybrid.py)
deben importar y usar las funciones de este módulo.

Basado en: ESPECIFICACION_MATCHING_v3.md
"""

import logging
import math
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ============================================================
# CONSTANTES GLOBALES
# ============================================================

# Umbrales y límites
UMBRAL_MINIMO_SCORE = 70
TOP_K_MATCHES = 10

# Tolerancias
TOLERANCIA_PRECIO = 0.10           # 10% para función gaussiana
TOLERANCIA_PRESUPUESTO_MAX = 0.05  # 5% para filtro duro de presupuesto máximo
TOLERANCIA_PRESUPUESTO_MIN = 0.50  # 50% para filtro duro de presupuesto mínimo

# Penalizaciones para funciones de distancia
PENALIZACION_HABITACIONES = 0.10   # 10% por habitación extra
PENALIZACION_BANOS = 0.15           # 15% por baño extra
PENALIZACION_AREA = 0.50            # 50% por exceso de área

# Tipo de cambio (debe moverse a BD o API externa en el futuro)
TIPO_CAMBIO_USD_PEN = 3.75

# Umbrales semánticos (función escalonada)
SEMANTICO_UMBRALES = {
    'excelente': 0.85,
    'bueno': 0.70,
    'aceptable': 0.55,
    'debil': 0.40,
}

SEMANTICO_MULTIPLICADORES = {
    'excelente': 1.0,
    'bueno': 0.8,
    'aceptable': 0.6,
    'debil': 0.3,
    'muy_debil': 0.0,
}

# Pesos de los factores de scoring (configurables)
PESOS = {
    'distrito': 15,
    'precio': 20,
    'habitaciones': 15,
    'banos': 10,
    'area': 10,
    'amenities': 10,
    'antiguedad': 5,
    'semantico': 15,
}


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def _normalize_str(val: Any) -> str:
    """Normaliza un valor a string limpio en minúsculas."""
    if val is None:
        return ''
    return str(val).lower().strip()


def _to_float(val: Any) -> Optional[float]:
    """Convierte un valor a float de forma segura."""
    if val is None:
        return None
    try:
        return float(str(val))
    except (ValueError, TypeError):
        return None


def _to_int(val: Any) -> Optional[int]:
    """Convierte un valor a int de forma segura."""
    if val is None:
        return None
    try:
        return int(float(str(val)))
    except (ValueError, TypeError):
        return None


def _convertir_moneda(monto: float, moneda_origen: str, moneda_destino: str) -> float:
    """
    Convierte entre PEN y USD usando tipo de cambio fijo.
    """
    if moneda_origen == moneda_destino:
        return monto
    if moneda_origen == 'USD' and moneda_destino == 'PEN':
        return monto * TIPO_CAMBIO_USD_PEN
    elif moneda_origen == 'PEN' and moneda_destino == 'USD':
        return monto / TIPO_CAMBIO_USD_PEN
    return monto


def _extraer_moneda(field_values: Dict) -> str:
    """
    Extrae la moneda de field_values (para HybridMatchingSkill).
    """
    currency_name = _normalize_str(field_values.get('currency_name', ''))
    if currency_name in ('dólares', 'usd', 'dolares', '$'):
        return 'USD'
    if currency_name in ('soles', 'pen', 's/.'):
        return 'PEN'
    currency_id = field_values.get('currency_id')
    if currency_id == 1:
        return 'USD'
    if currency_id == 2:
        return 'PEN'
    return 'PEN'


# ============================================================
# FASE 1: FILTROS DUROS
# ============================================================

# Mapeo de operación a operation_type_id: 1=Venta, 2=Permuta, 3=Alquiler
_OPERATION_TIPO_MAP = {
    'compra': (1, 2),
    'venta': (1, 2),
    'alquiler': (3,),
    'anticresis': (3,),
}


def aplicar_filtros_duros(prop_dict: Dict, req_data: Dict) -> Optional[str]:
    """
    Aplica los 10 filtros duros en orden (del más barato al más caro).

    Args:
        prop_dict: Diccionario con datos de la propiedad.
                   Puede venir de raw SQL (MatchingEngine) o field_values (HybridMatchingSkill).
                   Campos esperados:
                       - condicion / operation_type_id / operation_type_name
                       - tipo_propiedad / property_type_id / property_type_name
                       - forma_pago / payment_method_id (opcional)
                       - price, currency_id
                       - bedrooms, bathrooms, built_area
                       - ascensor / has_elevator
                       - garage_spaces
                       - district_id / district_name
        req_data: Diccionario con datos del requerimiento.
                  Campos esperados:
                      - condicion: str
                      - tipo_propiedad: str
                      - forma_pago: str (opcional)
                      - presupuesto_monto: float
                      - presupuesto_moneda: str ('USD'/'PEN')
                      - habitaciones: int (opcional)
                      - banos: int (opcional)
                      - area_m2: float (opcional)
                      - ascensor: str ('si'/'no'/'indiferente')
                      - cochera: str ('si'/'no'/'indiferente')
                      - distritos_lista: List[str]
                      - distrito_obligatorio: bool (opcional, default False)
                      - antiguedad_max: int (opcional)

    Returns:
        str con nombre del filtro que eliminó la propiedad, o None si pasa todos.
    """
    if not req_data:
        return None

    # ── 1. CONDICIÓN (compra/alquiler) ──────────────────────────────
    condicion_req = _normalize_str(req_data.get('condicion', ''))
    if condicion_req and condicion_req not in ('no_especificado', ''):
        op_id = _get_operation_type_id(prop_dict)
        if op_id is not None:
            op_ids_validos = _OPERATION_TIPO_MAP.get(condicion_req)
            if op_ids_validos and op_id not in op_ids_validos:
                return 'condicion'
        else:
            op_name = _normalize_str(prop_dict.get('operation_type_name', ''))
            if condicion_req in ('compra', 'venta'):
                if op_name and op_name not in ('venta', 'compra', 'permuta'):
                    return 'condicion'
            elif condicion_req in ('alquiler', 'anticresis'):
                if op_name and op_name != 'alquiler':
                    return 'condicion'

    # ── 2. TIPO DE PROPIEDAD ─────────────────────────────────────
    tipo_req = _normalize_str(req_data.get('tipo_propiedad', ''))
    tipo_vals_sin_filtro = {'no_especificado', 'no especificado', 'todos', 'cualquiera', ''}
    if tipo_req and tipo_req not in tipo_vals_sin_filtro:
        if not _coincide_tipo(tipo_req, prop_dict):
            return 'tipo_propiedad'

    # ── 3. FORMA DE PAGO (NUEVO) ─────────────────────────────────
    forma_pago_req = _normalize_str(req_data.get('forma_pago', ''))
    if forma_pago_req == 'credito_hipotecario':
        forma_pago_prop = _normalize_str(prop_dict.get('forma_pago', ''))
        if forma_pago_prop == 'solo_efectivo':
            return 'forma_pago'

    # ── 4. PRESUPUESTO MÁXIMO ─────────────────────────────────────
    presupuesto_monto = _to_float(req_data.get('presupuesto_monto'))
    if presupuesto_monto and presupuesto_monto > 0:
        precio = _to_float(prop_dict.get('price'))
        if precio is not None and precio > 0:
            moneda_req = (req_data.get('presupuesto_moneda') or 'PEN').upper()
            moneda_prop = _extraer_moneda(prop_dict) if prop_dict.get('currency_name') else \
                          ('USD' if prop_dict.get('currency_id') == 1 else 'PEN')
            precio_convertido = _convertir_moneda(precio, moneda_prop, moneda_req)
            limite_maximo = presupuesto_monto * (1.0 + TOLERANCIA_PRESUPUESTO_MAX)
            if precio_convertido > limite_maximo:
                return 'presupuesto_maximo'

    # ── 5. PRESUPUESTO MÍNIMO (NUEVO) ─────────────────────────────
    if presupuesto_monto and presupuesto_monto > 0:
        precio = _to_float(prop_dict.get('price'))
        if precio is not None and precio > 0:
            moneda_req = (req_data.get('presupuesto_moneda') or 'PEN').upper()
            moneda_prop = _extraer_moneda(prop_dict) if prop_dict.get('currency_name') else \
                          ('USD' if prop_dict.get('currency_id') == 1 else 'PEN')
            precio_convertido = _convertir_moneda(precio, moneda_prop, moneda_req)
            limite_minimo = presupuesto_monto * (1.0 - TOLERANCIA_PRESUPUESTO_MIN)
            if precio_convertido < limite_minimo:
                return 'presupuesto_minimo'

    # ── 6. ASCENSOR MUST-HAVE (NUEVO) ─────────────────────────────
    ascensor_req = _normalize_str(req_data.get('ascensor', ''))
    if ascensor_req == 'si':
        has_elevator = prop_dict.get('has_elevator')
        if has_elevator is not True:
            return 'ascensor'

    # ── 7. COCHERAS MUST-HAVE (NUEVO) ─────────────────────────────
    cochera_req = _normalize_str(req_data.get('cochera', ''))
    if cochera_req == 'si':
        garage_spaces = _to_int(prop_dict.get('garage_spaces'))
        if not garage_spaces or garage_spaces < 1:
            return 'cocheras'

    # ── 8. HABITACIONES MÍNIMAS (NUEVO) ───────────────────────────
    hab_req = _to_int(req_data.get('habitaciones'))
    if hab_req and hab_req > 0:
        hab_prop = _to_int(prop_dict.get('bedrooms'))
        if hab_prop is not None and hab_prop < hab_req:
            return 'habitaciones'

    # ── 9. BAÑOS MÍNIMOS (NUEVO) ──────────────────────────────────
    banos_req = _to_int(req_data.get('banos'))
    if banos_req and banos_req > 0:
        banos_prop = _to_int(prop_dict.get('bathrooms'))
        if banos_prop is not None and banos_prop < banos_req:
            return 'banos'

    # ── 10. DISTRITO OBLIGATORIO (NUEVO) ──────────────────────────
    distrito_obligatorio = req_data.get('distrito_obligatorio', False)
    if distrito_obligatorio:
        distritos_req = req_data.get('distritos_lista', [])
        if distritos_req:
            district_id = prop_dict.get('district_id')
            district_name = _normalize_str(prop_dict.get('district_name', ''))
            coincide = False
            for d in distritos_req:
                d_clean = _normalize_str(d)
                if d_clean == district_name or d_clean in district_name or district_name in d_clean:
                    coincide = True
                    break
                if district_id is not None:
                    id_str = str(district_id).strip()
                    if d_clean == id_str:
                        coincide = True
                        break
            if not coincide:
                return 'distrito'

    return None


def _get_operation_type_id(prop_dict: Dict) -> Optional[int]:
    """Obtiene el operation_type_id de un dict de propiedad."""
    op_id = prop_dict.get('operation_type_id')
    if op_id is not None:
        try:
            return int(op_id)
        except (ValueError, TypeError):
            pass
    return None


def _coincide_tipo(tipo_req: str, prop_dict: Dict) -> bool:
    """
    Verifica si el tipo de propiedad coincide.
    Soporta property_type_id y property_type_name.
    """
    tipo_req_norm = _normalize_str(tipo_req)

    # Intentar por property_type_name
    tipo_name = _normalize_str(prop_dict.get('property_type_name', ''))
    if tipo_name and tipo_name == tipo_req_norm:
        return True

    # Intentar por property_type_id
    tipo_id_prop = prop_dict.get('property_type_id')
    if tipo_id_prop is not None:
        tipo_id_req = _tipo_propiedad_name_to_id(tipo_req_norm)
        if tipo_id_req is not None and tipo_id_prop == tipo_id_req:
            return True

    # Fallback: comparación parcial (para variantes como 'depto' vs 'departamento')
    if tipo_name and (tipo_req_norm in tipo_name or tipo_name in tipo_req_norm):
        return True

    return False


# Cache de tipos de propiedad (se carga una vez desde BD)
_TIPO_CACHE: Optional[Dict[str, int]] = None


def _tipo_propiedad_name_to_id(name: str) -> Optional[int]:
    """
    Resuelve nombre de tipo de propiedad a ID desde la BD propifai.
    Cachea resultados para no consultar repetidamente.
    """
    global _TIPO_CACHE
    if _TIPO_CACHE is None:
        try:
            from django.db import connections
            with connections['propifai'].cursor() as cursor:
                cursor.execute("SELECT id, name FROM property_type WHERE is_active = 1")
                rows = cursor.fetchall()
                _TIPO_CACHE = {}
                for pt_id, pt_name in rows:
                    key = _normalize_str(pt_name)
                    _TIPO_CACHE[key] = pt_id
                    # Variantes comunes
                    if key == 'departamento':
                        _TIPO_CACHE['depto'] = pt_id
                        _TIPO_CACHE['dpto'] = pt_id
                    elif key == 'casa':
                        _TIPO_CACHE['casas'] = pt_id
                    elif key == 'terreno':
                        _TIPO_CACHE['terrenos'] = pt_id
                    elif key == 'local':
                        _TIPO_CACHE['local_comercial'] = pt_id
                        _TIPO_CACHE['local comercial'] = pt_id
        except Exception as e:
            logger.warning(f"[scoring] Error cargando property_types: {e}")
            _TIPO_CACHE = {}
    name_norm = _normalize_str(name)
    return _TIPO_CACHE.get(name_norm)


# ============================================================
# FASE 2: SCORING BLANDO
# ============================================================

def calcular_scoring_total(prop_dict: Dict, req_data: Dict) -> Tuple[float, Dict]:
    """
    Calcula el score total (0-100) para una propiedad usando 8 factores ponderados.

    Args:
        prop_dict: Diccionario con datos de la propiedad.
        req_data: Diccionario con datos del requerimiento.

    Returns:
        Tuple[score_total (0-100), score_detalle (dict con desglose)]
    """
    score_detalle = {}
    score_total = 0.0

    # Obtener similarity semántica si está disponible (para el factor semántico)
    similarity = req_data.get('_similarity_semantico')

    scorers = [
        ('distrito', _score_distrito, PESOS['distrito']),
        ('precio', _score_precio, PESOS['precio']),
        ('habitaciones', _score_habitaciones, PESOS['habitaciones']),
        ('banos', _score_banos, PESOS['banos']),
        ('area', _score_area, PESOS['area']),
        ('amenities', _score_amenities, PESOS['amenities']),
        ('antiguedad', _score_antiguedad, PESOS['antiguedad']),
        ('semantico', _score_semantico, PESOS['semantico']),
    ]

    for factor_name, scorer_fn, peso_maximo in scorers:
        try:
            if factor_name == 'semantico':
                s = scorer_fn(similarity)
            else:
                s = scorer_fn(prop_dict, req_data)
        except Exception as e:
            logger.warning(f"[scoring] Error en score '{factor_name}': {e}")
            s = 0.0

        score_detalle[factor_name] = {
            'score': round(s, 2),
            'peso_maximo': peso_maximo,
            'detalle': _generar_detalle(factor_name, s, prop_dict, req_data),
        }
        score_total += s

    # Asegurar rango 0-100
    score_total = max(0.0, min(100.0, score_total))

    return round(score_total, 2), score_detalle


def _generar_detalle(factor_name: str, score: float, prop_dict: Dict, req_data: Dict) -> str:
    """Genera un detalle descriptivo para cada factor de scoring."""
    detalles = {
        'distrito': lambda: (
            f"Distrito propiedad: {prop_dict.get('district_name', prop_dict.get('district_id', 'N/A'))}"
        ),
        'precio': lambda: (
            f"Precio: {prop_dict.get('price', 'N/A')}, "
            f"Presupuesto: {req_data.get('presupuesto_monto', 'N/A')}"
        ),
        'habitaciones': lambda: (
            f"Habitaciones: {prop_dict.get('bedrooms', 'N/A')}, "
            f"Requeridas: {req_data.get('habitaciones', 'N/A')}"
        ),
        'banos': lambda: (
            f"Baños: {prop_dict.get('bathrooms', 'N/A')}, "
            f"Requeridos: {req_data.get('banos', 'N/A')}"
        ),
        'area': lambda: (
            f"Área: {prop_dict.get('built_area', 'N/A')}m2, "
            f"Requerida: {req_data.get('area_m2', 'N/A')}m2"
        ),
        'amenities': lambda: (
            f"Características extra: {req_data.get('caracteristicas_extra', 'N/A')}"
        ),
        'antiguedad': lambda: (
            f"Antigüedad: {prop_dict.get('antiquity_years', 'N/A')} años"
        ),
        'semantico': lambda: (
            f"Similaridad: {req_data.get('_similarity_semantico', 0.0):.2f}"
            if req_data.get('_similarity_semantico')
            else "Semántico no disponible (score neutro)"
        ),
    }
    fn = detalles.get(factor_name)
    return fn() if fn else ''


# ── FACTOR 1: DISTRITO ─────────────────────────────────────────────

def _score_distrito(prop_dict: Dict, req_data: Dict) -> float:
    """
    Score 0-15: Coincidencia con distritos preferidos (ordenados por prioridad).
    El primer distrito en la lista es el más deseado.
    """
    distritos_lista = req_data.get('distritos_lista', [])
    if not distritos_lista:
        return PESOS['distrito'] * 0.5  # Score neutro si no hay distritos

    district_name = _normalize_str(prop_dict.get('district_name', ''))
    district_id = prop_dict.get('district_id')

    for rank, d in enumerate(distritos_lista):
        d_clean = _normalize_str(d)
        # Coincidencia por nombre
        if d_clean == district_name or district_name in d_clean or d_clean in district_name:
            score = PESOS['distrito'] * (1.0 - rank * 0.10)
            return max(0.0, score)
        # Coincidencia por ID
        if district_id is not None:
            id_str = str(district_id).strip()
            if d_clean == id_str:
                score = PESOS['distrito'] * (1.0 - rank * 0.10)
                return max(0.0, score)

    return 0.0


# ── FACTOR 2: PRECIO (GAUSSIANA) ───────────────────────────────────

def _score_precio(prop_dict: Dict, req_data: Dict) -> float:
    """
    Score 0-20: Proximidad al presupuesto usando función gaussiana.

    Fórmula:
        diff_pct = abs(precio - presupuesto) / presupuesto
        score = PESO * exp(-(diff_pct²) / (2 * tolerancia²))
    """
    presupuesto_monto = _to_float(req_data.get('presupuesto_monto'))
    price = _to_float(prop_dict.get('price'))

    if not presupuesto_monto or not price or presupuesto_monto <= 0:
        return PESOS['precio'] * 0.5  # Score neutro

    # Convertir monedas si es necesario
    moneda_req = (req_data.get('presupuesto_moneda') or 'PEN').upper()
    moneda_prop = _extraer_moneda(prop_dict) if prop_dict.get('currency_name') else \
                  ('USD' if prop_dict.get('currency_id') == 1 else 'PEN')

    if moneda_req != moneda_prop:
        price = _convertir_moneda(price, moneda_prop, moneda_req)

    diff_pct = abs(price - presupuesto_monto) / presupuesto_monto
    exponent = -(diff_pct ** 2) / (2 * TOLERANCIA_PRECIO ** 2)
    score = PESOS['precio'] * math.exp(exponent)

    return round(score, 2)


# ── FACTOR 3: HABITACIONES (DISTANCIA) ────────────────────────────

def _score_habitaciones(prop_dict: Dict, req_data: Dict) -> float:
    """
    Score 0-15: Coincidencia con habitaciones requeridas (función de distancia).

    Fórmula:
        diff = prop.hab - req.hab_min
        score = PESO * max(0.0, 1.0 - (diff * penalizacion))
    """
    hab_req = _to_int(req_data.get('habitaciones'))
    hab_prop = _to_int(prop_dict.get('bedrooms'))

    if not hab_req or not hab_prop:
        return PESOS['habitaciones'] * 0.5  # Score neutro

    if hab_prop < hab_req:
        return 0.0  # No debería llegar aquí (filtro duro lo elimina)

    diff = hab_prop - hab_req
    score = PESOS['habitaciones'] * max(0.0, 1.0 - (diff * PENALIZACION_HABITACIONES))
    return round(score, 2)


# ── FACTOR 4: BAÑOS (DISTANCIA) ────────────────────────────────────

def _score_banos(prop_dict: Dict, req_data: Dict) -> float:
    """
    Score 0-10: Coincidencia con baños requeridos (función de distancia).

    Fórmula:
        diff = prop.banos - req.banos_min
        score = PESO * max(0.0, 1.0 - (diff * penalizacion))
    """
    banos_req = _to_int(req_data.get('banos'))
    banos_prop = _to_int(prop_dict.get('bathrooms'))

    if not banos_req or not banos_prop:
        return PESOS['banos'] * 0.5  # Score neutro

    if banos_prop < banos_req:
        return 0.0  # No debería llegar aquí (filtro duro lo elimina)

    diff = banos_prop - banos_req
    score = PESOS['banos'] * max(0.0, 1.0 - (diff * PENALIZACION_BANOS))
    return round(score, 2)


# ── FACTOR 5: ÁREA (DISTANCIA) ─────────────────────────────────────

def _score_area(prop_dict: Dict, req_data: Dict) -> float:
    """
    Score 0-10: Coincidencia con área requerida (función de distancia).

    Fórmula:
        diff_pct = (prop.area - req.area_min) / req.area_min
        score = PESO * max(0.0, 1.0 - (diff_pct * penalizacion))
    """
    area_req = _to_float(req_data.get('area_m2'))
    area_prop = _to_float(prop_dict.get('built_area'))

    if not area_req or not area_prop or area_req <= 0:
        return PESOS['area'] * 0.5  # Score neutro

    if area_prop < area_req:
        return 0.0  # No debería llegar aquí (filtro duro lo elimina)

    diff_pct = (area_prop - area_req) / area_req
    score = PESOS['area'] * max(0.0, 1.0 - (diff_pct * PENALIZACION_AREA))
    return round(score, 2)


# ── FACTOR 6: AMENITIES (JACCARD) ─────────────────────────────────

# Mapeo de keywords de caracteristicas_extra a amenities canónicos
_AMENITY_MAP = {
    'piscina': 'piscina',
    'pileta': 'piscina',
    'jardin': 'jardin',
    'jardín': 'jardin',
    'bbq': 'bbq',
    'parrilla': 'bbq',
    'terraza': 'terraza',
    'azotea': 'terraza',
    'aire acondicionado': 'aire_acondicionado',
    'aa': 'aire_acondicionado',
    'lavandería': 'lavanderia',
    'lavanderia': 'lavanderia',
    'cuarto de servicio': 'servicio',
    'servicio': 'servicio',
    'seguridad': 'seguridad',
    'mascotas': 'mascotas',
    'pet friendly': 'mascotas',
    'gimnasio': 'gimnasio',
    'area verde': 'area_verde',
    'área verde': 'area_verde',
    'parque': 'area_verde',
    'estacionamiento': 'estacionamiento',
    'cochera': 'estacionamiento',
    'garage': 'estacionamiento',
}


def _score_amenities(prop_dict: Dict, req_data: Dict) -> float:
    """
    Score 0-10: Coincidencia de amenities usando Jaccard similarity.

    Fórmula:
        jaccard = |intersección| / |unión|
        score = PESO * jaccard
    """
    extras_req = _normalize_str(req_data.get('caracteristicas_extra', ''))
    if not extras_req:
        return PESOS['amenities'] * 0.5  # Score neutro

    # Extraer amenities canónicos del requerimiento
    req_amenities = set()
    palabras = extras_req.replace(',', ' ').split()
    for p in palabras:
        p = p.strip()
        if len(p) > 2:
            amenity = _AMENITY_MAP.get(p.lower())
            if amenity:
                req_amenities.add(amenity)

    if not req_amenities:
        return PESOS['amenities'] * 0.5  # Score neutro

    # Extraer amenities canónicos de la propiedad (desde campos booleanos)
    prop_amenities = set()
    bool_to_amenity = {
        'has_pool': 'piscina',
        'has_garden': 'jardin',
        'has_bbq': 'bbq',
        'has_terrace': 'terraza',
        'has_security': 'seguridad',
        'pet_friendly': 'mascotas',
        'has_air_conditioning': 'aire_acondicionado',
        'has_laundry_area': 'lavanderia',
        'has_service_room': 'servicio',
    }
    for campo, amenity in bool_to_amenity.items():
        val = prop_dict.get(campo)
        if val is True:
            prop_amenities.add(amenity)

    # También considerar garage_spaces
    garage = _to_int(prop_dict.get('garage_spaces'))
    if garage and garage > 0:
        prop_amenities.add('estacionamiento')

    intersection = req_amenities & prop_amenities
    union = req_amenities | prop_amenities

    if not union:
        return PESOS['amenities'] * 0.5

    jaccard = len(intersection) / len(union)
    score = PESOS['amenities'] * jaccard
    return round(score, 2)


# ── FACTOR 7: ANTIGÜEDAD (DISTANCIA) ──────────────────────────────

def _score_antiguedad(prop_dict: Dict, req_data: Dict) -> float:
    """
    Score 0-5: Coincidencia con antigüedad máxima (función de distancia).

    Fórmula:
        diff = req.antiguedad_max - prop.antiguedad
        score = PESO * (1.0 - (diff / req.antiguedad_max))
    """
    antiguedad_max = _to_int(req_data.get('antiguedad_max'))
    antiguedad_prop = _to_int(prop_dict.get('antiquity_years'))

    if not antiguedad_max:
        return PESOS['antiguedad'] * 0.5  # Score neutro

    if antiguedad_prop is None:
        return PESOS['antiguedad'] * 0.5  # Score neutro

    if antiguedad_prop > antiguedad_max:
        return 0.0  # No debería llegar aquí (filtro duro)

    diff = antiguedad_max - antiguedad_prop
    score = PESOS['antiguedad'] * (1.0 - (diff / antiguedad_max))
    return max(0.0, round(score, 2))


# ── FACTOR 8: SEMÁNTICO (ESCALONADA) ──────────────────────────────

def _score_semantico(similarity: Optional[float] = None) -> float:
    """
    Score 0-15: Similaridad semántica usando función escalonada.

    Fórmula:
        similarity >= 0.85: score = 15 * 1.0   (excelente)
        similarity >= 0.70: score = 15 * 0.8   (bueno)
        similarity >= 0.55: score = 15 * 0.6   (aceptable)
        similarity >= 0.40: score = 15 * 0.3   (débil)
        similarity < 0.40:  score = 0           (muy débil)
        sin FAISS:          score = 7.5         (neutro)
    """
    if similarity is None:
        return PESOS['semantico'] * 0.5  # Score neutro (7.5)

    if similarity >= SEMANTICO_UMBRALES['excelente']:
        return PESOS['semantico'] * SEMANTICO_MULTIPLICADORES['excelente']
    elif similarity >= SEMANTICO_UMBRALES['bueno']:
        return PESOS['semantico'] * SEMANTICO_MULTIPLICADORES['bueno']
    elif similarity >= SEMANTICO_UMBRALES['aceptable']:
        return PESOS['semantico'] * SEMANTICO_MULTIPLICADORES['aceptable']
    elif similarity >= SEMANTICO_UMBRALES['debil']:
        return PESOS['semantico'] * SEMANTICO_MULTIPLICADORES['debil']
    else:
        return PESOS['semantico'] * SEMANTICO_MULTIPLICADORES['muy_debil']


# ============================================================
# FASE 3: FILTRADO FINAL
# ============================================================

def filtrar_resultados_finales(
    resultados: List[Dict],
    umbral_minimo: int = UMBRAL_MINIMO_SCORE,
    top_k: int = TOP_K_MATCHES,
) -> List[Dict]:
    """
    Aplica el filtrado final a los resultados de matching.

    Pasos:
    1. Filtrar por umbral mínimo de score
    2. Limitar a top-K matches
    3. Asignar ranking

    Args:
        resultados: Lista de dicts con al menos {'score_total': float}
        umbral_minimo: Score mínimo para incluir (default: 70)
        top_k: Máximo de matches a retornar (default: 10)

    Returns:
        Lista filtrada y ordenada con ranking asignado
    """
    # Filtrar por umbral
    filtrados = [r for r in resultados if r.get('score_total', 0) >= umbral_minimo]

    # Ordenar por score descendente
    filtrados.sort(key=lambda x: x.get('score_total', 0), reverse=True)

    # Limitar a top-K
    top = filtrados[:top_k]

    # Asignar ranking
    for i, resultado in enumerate(top, 1):
        resultado['ranking'] = i

    return top


def preparar_req_data(requerimiento) -> Dict:
    """
    Prepara un dict estandarizado con datos del requerimiento
    para usar en filtros duros y scoring.

    Args:
        requerimiento: Instancia del modelo Requerimiento

    Returns:
        Dict con campos normalizados
    """
    return {
        'id': requerimiento.id,
        'condicion': requerimiento.condicion or '',
        'tipo_propiedad': requerimiento.tipo_propiedad or '',
        'distritos': requerimiento.distritos or '',
        'distritos_lista': requerimiento.distritos_lista if hasattr(requerimiento, 'distritos_lista') else [],
        'distrito_obligatorio': False,  # Por defecto, puede configurarse
        'presupuesto_monto': float(requerimiento.presupuesto_monto) if requerimiento.presupuesto_monto else None,
        'presupuesto_moneda': (requerimiento.presupuesto_moneda or 'PEN').upper(),
        'forma_pago': (requerimiento.presupuesto_forma_pago or '').lower(),
        'habitaciones': requerimiento.habitaciones,
        'banos': requerimiento.banos,
        'area_m2': float(requerimiento.area_m2) if requerimiento.area_m2 else None,
        'ascensor': (requerimiento.ascensor or '').lower(),
        'cochera': (requerimiento.cochera or '').lower(),
        'caracteristicas_extra': requerimiento.caracteristicas_extra or '',
    }
