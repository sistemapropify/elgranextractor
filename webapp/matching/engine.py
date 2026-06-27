"""
Wrapper de compatibilidad — Motor de matching.

TODA la lógica de matching ahora vive en HybridMatchingSkill (intelligence/skills/matching_hybrid.py).
Este archivo solo mantiene funciones de consulta de datos y wrappers que redirigen
al HybridMatchingSkill para no romper imports existentes.

Eliminado (Junio 2026):
- MatchingEngine (clase legacy)
- _fetch_properties() (reemplazado por FAISS + IntelligenceDocument)
- ejecutar_matching_masivo() (reemplazado por HybridMatchingSkill)
- ejecutar_matching_requerimiento() (redirige a HybridMatchingSkill)
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from django.db import connections

from requerimientos.models import Requerimiento
from propifai.mapeo_ubicaciones import DISTRITOS
from . import scoring

logger = logging.getLogger(__name__)

# Cache de nombres de distrito (id → nombre)
_DISTRICT_CACHE = {}

# Tipo de cambio (mantener aquí para compatibilidad con funciones existentes)
TIPO_CAMBIO_USD_PEN = Decimal('3.75')


def _get_distrito_id(nombre_distrito: str) -> Optional[str]:
    """Resuelve un nombre de distrito a su ID numérico usando mapeo_ubicaciones."""
    nombre_limpio = nombre_distrito.lower().strip()
    for id_dist, nombre in DISTRITOS.items():
        if nombre.lower().strip() == nombre_limpio:
            return id_dist
    for id_dist, nombre in DISTRITOS.items():
        nombre_normalizado = nombre.lower().strip()
        if nombre_limpio in nombre_normalizado or nombre_normalizado in nombre_limpio:
            return id_dist
    return None


def _get_district_name(district_id) -> Optional[str]:
    """Obtiene el nombre del distrito desde la tabla district."""
    if not district_id:
        return None
    cache_key = str(district_id)
    if cache_key in _DISTRICT_CACHE:
        return _DISTRICT_CACHE[cache_key]
    try:
        with connections['propifai'].cursor() as cursor:
            cursor.execute("SELECT name FROM district WHERE id = %s", [district_id])
            row = cursor.fetchone()
            name = row[0] if row else None
            _DISTRICT_CACHE[cache_key] = name
            return name
    except Exception as e:
        logger.error(f"Error al obtener nombre de distrito {district_id}: {e}")
        return None


def _fetch_property_by_id(property_id: int) -> Optional[Dict]:
    """
    Obtiene una propiedad específica desde dbpropify_be con todos sus datos
    (specs, tipo, operación, imagen).

    Solo para enriquecer display en vistas de detalle. NO se usa para matching.

    Args:
        property_id: ID de la propiedad en dbpropify_be.property

    Returns:
        Dict con todos los campos de property + property_specs + nombres, o None
    """
    try:
        query = """
            SELECT
                p.id, p.code, p.title, p.description,
                p.price, p.maintenance_fee,
                p.map_address, p.display_address,
                p.latitude, p.longitude,
                p.is_project, p.is_visible, p.project_name,
                p.currency_id, p.district_id, p.operation_type_id,
                p.property_type_id, p.property_condition_id,
                p.property_status_id, p.contact_id, p.responsible_id,
                p.created_at, p.updated_at,
                p.uuid, p.video_url, p.registry_number,
                p.payment_method_id, p.property_subtype_id,
                p.urbanization_id, p.parent_project_id,
                p.created_by_id, p.updated_by_id,
                p.wp_post_id, p.wp_slug, p.wp_last_sync,
                s.bedrooms, s.bathrooms, s.half_bathrooms,
                s.has_elevator, s.land_area, s.built_area,
                s.front_measure, s.depth_measure, s.area_unit, s.linear_unit,
                s.garage_spaces, s.garage_type, s.parking_cost_included, s.parking_cost,
                s.antiquity_years, s.delivery_date,
                s.has_security, s.has_pool, s.has_garden, s.has_bbq, s.has_terrace,
                s.has_air_conditioning, s.has_laundry_area, s.has_service_room, s.pet_friendly,
                s.floors_total, s.unit_location,
                (SELECT TOP 1 pm2.[file] FROM property_media pm2
                 WHERE pm2.property_id = p.id AND pm2.media_type = 'image'
                 ORDER BY pm2.[order]) AS [file],
                pt.name AS property_type_name,
                ot.name AS operation_type_name
            FROM property p
            LEFT JOIN property_specs s ON s.property_id = p.id
            LEFT JOIN property_type pt ON pt.id = p.property_type_id
            LEFT JOIN operation_type ot ON ot.id = p.operation_type_id
            WHERE p.id = %s
        """
        with connections['propifai'].cursor() as cursor:
            cursor.execute(query, [property_id])
            columns = [desc[0] for desc in cursor.description]
            row = cursor.fetchone()
            if row:
                prop_dict = dict(zip(columns, row))
                prop_dict['district_name'] = _get_district_name(prop_dict.get('district_id'))
                return prop_dict
            return None
    except Exception as e:
        logger.error(f"Error al obtener propiedad {property_id} desde dbpropify_be: {e}")
        return None


def _get_moneda_propiedad(prop_dict: Dict) -> str:
    """Determina la moneda de la propiedad basado en currency_id (1=USD, 2=PEN)."""
    currency_id = prop_dict.get('currency_id')
    if currency_id == 1:
        return 'USD'
    elif currency_id == 2:
        return 'PEN'
    return 'PEN'


def _get_property_type_name(property_type_id) -> Optional[str]:
    """Obtiene el nombre del tipo de propiedad usando el cache de scoring.py."""
    if not property_type_id:
        return None
    property_type_id_int = int(property_type_id) if property_type_id else None
    if property_type_id_int is None:
        return None
    from . import scoring as scoring_mod
    scoring_mod._tipo_propiedad_name_to_id('')
    if scoring_mod._TIPO_CACHE:
        for name, tid in scoring_mod._TIPO_CACHE.items():
            if tid == property_type_id_int:
                return name.capitalize()
    return None


# ============================================================
# Funciones de conveniencia — Wrappers que redirigen a HybridMatchingSkill
# ============================================================

def ejecutar_matching_requerimiento(requerimiento_id: int, propiedades=None) -> Tuple[List[Dict], Dict[str, Any]]:
    """
    Ejecuta matching híbrido vía HybridMatchingSkill (FAISS + scoring).
    
    Args:
        requerimiento_id: ID del requerimiento.
        propiedades: Ignorado (se usa FAISS, no SQL).
        
    Returns:
        Tuple (resultados, estadisticas)
    """
    try:
        requerimiento = Requerimiento.objects.get(id=requerimiento_id)
    except Requerimiento.DoesNotExist:
        raise ValueError(f"Requerimiento con ID {requerimiento_id} no existe.")

    from intelligence.skills.registry import SkillRegistry
    from intelligence.skills.orchestrator import SkillOrchestrator, ExecutionContext
    from intelligence.skills.cache import SkillCache

    registry = SkillRegistry()
    orchestrator = SkillOrchestrator(registry, SkillCache())
    context = ExecutionContext()

    result = orchestrator.execute_skill('matching_hibrido', {
        'requerimiento_id': requerimiento_id,
        'top_n': scoring.TOP_K_MATCHES,
        'umbral_minimo': scoring.UMBRAL_MINIMO_SCORE,
    }, context)

    if not result.success or not result.data:
        logger.warning(f"HybridMatchingSkill falló para req {requerimiento_id}: {result.message}")
        return [], {
            'total_evaluadas': 0,
            'total_descartadas': 0,
            'total_compatibles': 0,
            'descartadas_por_campo': {},
            'score_promedio': 0.0,
            'propiedad_top': None,
        }

    matches = result.data.get('matches', [])
    
    # Convertir al formato esperado por los callers
    resultados = []
    for m in matches:
        resultados.append({
            'propiedad_dict': m.get('field_values', {}),
            'propiedad_id': m['property_id'],
            'score_total': m['score_total'],
            'score_detalle': m.get('score_detalle', {}),
            'fase_eliminada': None,
            'porcentaje_compatibilidad': m['score_total'],
            'ranking': m.get('ranking'),
        })

    estadisticas = {
        'total_evaluadas': len(matches),
        'total_descartadas': 0,
        'total_compatibles': len(matches),
        'descartadas_por_campo': {},
        'score_promedio': round(sum(m['score_total'] for m in matches) / len(matches), 2) if matches else 0.0,
        'propiedad_top': {
            'propiedad_id': matches[0]['property_id'],
            'score_total': matches[0]['score_total'],
        } if matches else None,
    }

    return resultados, estadisticas


def guardar_resultados_matching(requerimiento_id: int, resultados: List[Dict]) -> List[Any]:
    """
    Guarda los resultados del matching en MatchResult.
    
    Compatible con formato score_detalle: {factor: {score, peso_maximo, detalle}}
    
    Args:
        requerimiento_id: ID del requerimiento.
        resultados: Lista de resultados del matching.
        
    Returns:
        Lista de objetos MatchResult creados.
    """
    requerimiento = Requerimiento.objects.get(id=requerimiento_id)
    from .models import MatchResult
    objetos_creados = []

    for resultado in resultados:
        score_detalle = resultado.get('score_detalle', {})
        if isinstance(score_detalle, dict):
            score_detalle_clean = {}
            for k, v in score_detalle.items():
                if isinstance(v, dict) and 'score' in v:
                    score_detalle_clean[k] = {
                        'score': float(v.get('score', 0)),
                        'peso_maximo': v.get('peso_maximo', 0),
                        'detalle': v.get('detalle', ''),
                    }
                elif isinstance(v, Decimal):
                    score_detalle_clean[k] = float(v)
                else:
                    score_detalle_clean[k] = v
            score_detalle = score_detalle_clean

        score_total = resultado.get('score_total', 0)
        if isinstance(score_total, Decimal):
            score_total = float(score_total)

        match_result = MatchResult(
            requerimiento=requerimiento,
            propiedad_id=resultado.get('propiedad_id'),
            score_total=score_total,
            score_detalle=score_detalle,
            fase_eliminada=resultado.get('fase_eliminada'),
            porcentaje_compatibilidad=resultado.get('porcentaje_compatibilidad', score_total),
            ranking=resultado.get('ranking'),
        )
        match_result.save()
        objetos_creados.append(match_result)

    return objetos_creados


def obtener_resumen_matching_masivo(limite=500):
    """
    Retorna un resumen de matching para todos los requerimientos con MatchResult.
    NO ejecuta matching — solo consulta resultados previamente guardados.
    """
    from .models import MatchResult
    from requerimientos.models import Requerimiento
    from django.db.models import Max

    try:
        reqs_con_match = (
            MatchResult.objects
            .values('requerimiento_id')
            .annotate(max_score=Max('score_total'))
            .order_by('-max_score')
        )

        req_ids = [r['requerimiento_id'] for r in reqs_con_match]
        if not req_ids:
            return []

        reqs_map = {r.id: r for r in Requerimiento.objects.filter(id__in=req_ids, verificado=True)}

        mejores = {}
        for mr in MatchResult.objects.filter(requerimiento_id__in=req_ids).order_by('requerimiento_id', '-score_total'):
            if mr.requerimiento_id not in mejores:
                mejores[mr.requerimiento_id] = mr

        resumen = []
        for item in reqs_con_match:
            req_id = item['requerimiento_id']
            req = reqs_map.get(req_id)
            if not req:
                continue
            mejor = mejores.get(req_id)
            if mejor:
                sd = mejor.score_detalle or {}

                def _extraer_score(d, key, default=0):
                    val = d.get(key, default)
                    if isinstance(val, dict):
                        return float(val.get('score', default))
                    return float(val) if val else default

                score_semantico = _extraer_score(sd, 'semantico')
                score_structural = _extraer_score(sd, 'score_structural', mejor.score_total)

                if score_semantico > 0 and score_structural > 0:
                    match_tipo = 'hibrido'
                    match_tipo_label = 'Híbrido'
                elif score_semantico > 0:
                    match_tipo = 'semantico'
                    match_tipo_label = 'Semántico'
                elif score_structural > 0:
                    match_tipo = 'estructural'
                    match_tipo_label = 'Estructural'
                else:
                    match_tipo = 'estructural'
                    match_tipo_label = 'Estructural'

                # Enriquecer con datos reales de la propiedad desde dbpropify_be
                prop_data = _fetch_property_by_id(mejor.propiedad_id)
                if prop_data:
                    prop_code = prop_data.get('code')
                    prop_title = prop_data.get('title')
                    prop_distrito = prop_data.get('district_name')
                    prop_precio = float(prop_data['price']) if prop_data.get('price') else None
                    prop_moneda = prop_data.get('currency_id')
                    prop_tipo = prop_data.get('property_type_name')
                else:
                    prop_code = prop_title = prop_distrito = prop_precio = None
                    prop_moneda = prop_tipo = None

                resumen.append({
                    'requerimiento_id': req_id,
                    'requerimiento_nombre': str(req),
                    'porcentaje_match': float(mejor.score_total),
                    'score_semantico': score_semantico,
                    'score_structural': score_structural,
                    'match_tipo': match_tipo,
                    'match_tipo_label': match_tipo_label,
                    'score_promedio': float(item.get('max_score', 0)),
                    'total_compatibles': 1,
                    'mejor_propiedad_id': mejor.propiedad_id,
                    'mejor_propiedad_codigo': prop_code,
                    'mejor_propiedad_titulo': prop_title,
                    'mejor_propiedad_distrito': prop_distrito,
                    'mejor_propiedad_precio': prop_precio,
                    'mejor_propiedad_moneda_id': prop_moneda,
                    'mejor_propiedad_tipo': prop_tipo,
                })

        return resumen[:limite]
    except Exception as e:
        logger.error(f"Error en obtener_resumen_matching_masivo: {e}")
        return []