"""
Motor de matching inmobiliario v4 — REFACTORIZADO con módulo scoring.py compartido.

Cambios v4 (basado en ESPECIFICACION_MATCHING_v3.md):
1. Usa scoring.py para filtros duros (10), scoring blando (8 factores) y filtrado final
2. Ascensor y cocheras ahora son FILTROS DUROS (no scoring)
3. Precio usa función GAUSSIANA (no binaria)
4. Habitaciones/baños/área usan función de DISTANCIA (penalizan exceso)
5. Amenities usa JACCARD similarity
6. Nuevo factor semántico escalonado (peso 15)
7. Nuevo factor antigüedad (peso 5)
8. Umbral mínimo de score: 70%
9. Top-K limit: 10 matches por requerimiento
10. score_detalle con nuevo formato {factor: {score, peso_maximo, detalle}}
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from django.db import connections
from django.conf import settings

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
    (specs, tipo, operación, imagen). El nombre del distrito se resuelve con _get_district_name().
    
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
                -- Primera imagen de property_media
                (SELECT TOP 1 pm2.[file] FROM property_media pm2
                 WHERE pm2.property_id = p.id AND pm2.media_type = 'image'
                 ORDER BY pm2.[order]) AS [file],
                -- Nombres de tipo y operación
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
                # Resolver nombre del distrito usando la función existente
                prop_dict['district_name'] = _get_district_name(prop_dict.get('district_id'))
                return prop_dict
            return None
    except Exception as e:
        logger.error(f"Error al obtener propiedad {property_id} desde dbpropify_be: {e}")
        return None


def _fetch_properties(is_active_only=True, limit=1000) -> List[Dict]:
    """
    Obtiene propiedades con JOIN a property_specs usando raw SQL.
    Solo propiedades visibles y disponibles (property_status_id = 3).
    """
    try:
        where_clause = "WHERE p.is_visible = 1 AND p.property_status_id = 3" if is_active_only else ""
        query = f"""
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
                -- Primera imagen de property_media
                (SELECT TOP 1 pm2.[file] FROM property_media pm2
                 WHERE pm2.property_id = p.id AND pm2.media_type = 'image'
                 ORDER BY pm2.[order]) AS [file],
                -- Nombres de tipo y operación
                pt.name AS property_type_name,
                ot.name AS operation_type_name
            FROM property p
            LEFT JOIN property_specs s ON s.property_id = p.id
            LEFT JOIN property_type pt ON pt.id = p.property_type_id
            LEFT JOIN operation_type ot ON ot.id = p.operation_type_id
            {where_clause}
            ORDER BY p.id
        """
        with connections['propifai'].cursor() as cursor:
            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            properties = [dict(zip(columns, row)) for row in rows]
        
        logger.debug(f"Propiedades cargadas desde dbpropify_be: {len(properties)}")
        return properties
    except Exception as e:
        logger.error(f"Error al cargar propiedades desde dbpropify_be: {e}")
        return []


def _get_moneda_propiedad(prop_dict: Dict) -> str:
    """
    Determina la moneda de la propiedad basado en currency_id.
    currency_id: 1=USD, 2=PEN
    """
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
    # Usar el cache de scoring.py para resolver nombres de tipos
    property_type_id_int = int(property_type_id) if property_type_id else None
    if property_type_id_int is None:
        return None
    # Cargar cache si no está cargado
    from . import scoring as scoring_mod
    # Forzar carga del cache de tipo en scoring module
    scoring_mod._tipo_propiedad_name_to_id('')  # Inicializa el cache
    # Invertir el cache para buscar por ID
    if scoring_mod._TIPO_CACHE:
        for name, tid in scoring_mod._TIPO_CACHE.items():
            if tid == property_type_id_int:
                return name.capitalize()
    return None


class MatchingEngine:
    """
    Motor principal de matching v4 — REFACTORIZADO con scoring.py.
    
    Basado en ESPECIFICACION_MATCHING_v3.md:
    - FASE 1: 10 filtros duros (via scoring.aplicar_filtros_duros)
    - FASE 2: 8 factores de scoring (via scoring.calcular_scoring_total)
    - FASE 3: Umbral 70% + top-10 + ranking (via scoring.filtrar_resultados_finales)
    """
    
    def __init__(self, requerimiento: Requerimiento):
        self.requerimiento = requerimiento
        self.req_data = scoring.preparar_req_data(requerimiento)
        self.propiedades_evaluadas = 0
        # Todos los 10 filtros duros posibles
        self.propiedades_descartadas = {
            'condicion': 0,
            'tipo_propiedad': 0,
            'forma_pago': 0,
            'presupuesto_maximo': 0,
            'presupuesto_minimo': 0,
            'ascensor': 0,
            'cocheras': 0,
            'habitaciones': 0,
            'banos': 0,
            'distrito': 0,
        }
        self.propiedades_compatibles = []
    
    def ejecutar_matching(self, propiedades: List[Dict] = None) -> List[Dict]:
        """
        Ejecuta el matching completo v4 para el requerimiento.
        
        Args:
            propiedades: Lista de diccionarios con datos de propiedades.
                         Si es None, se cargan desde la BD.
                         
        Returns:
            Lista de diccionarios con resultados (filtrados por umbral 70%, top-10).
        """
        if propiedades is None:
            propiedades = _fetch_properties(is_active_only=True)
        
        resultados_parciales = []
        
        for prop_dict in propiedades:
            self.propiedades_evaluadas += 1
            
            # ── FASE 1: Filtros duros ────────────────────────────────
            fase_eliminada = scoring.aplicar_filtros_duros(prop_dict, self.req_data)
            if fase_eliminada:
                if fase_eliminada in self.propiedades_descartadas:
                    self.propiedades_descartadas[fase_eliminada] += 1
                continue
            
            # ── FASE 2: Scoring blando ───────────────────────────────
            score_total, score_detalle = scoring.calcular_scoring_total(prop_dict, self.req_data)
            
            resultado = {
                'propiedad_dict': prop_dict,
                'propiedad_id': prop_dict['id'],
                'score_total': score_total,
                'score_detalle': score_detalle,
                'fase_eliminada': None,
                'porcentaje_compatibilidad': score_total,
                'ranking': None,
            }
            
            resultados_parciales.append(resultado)
            self.propiedades_compatibles.append(resultado)
        
        # ── FASE 3: Filtrado final (umbral + top-K + ranking) ─────
        resultados = scoring.filtrar_resultados_finales(
            resultados_parciales,
            umbral_minimo=scoring.UMBRAL_MINIMO_SCORE,
            top_k=scoring.TOP_K_MATCHES,
        )
        
        logger.info(
            f"Matching v4 completado para requerimiento {self.requerimiento.id}. "
            f"Evaluadas: {self.propiedades_evaluadas}, "
            f"Pasaron filtros: {len(resultados_parciales)}, "
            f"Top-{scoring.TOP_K_MATCHES} finales: {len(resultados)}, "
            f"Descartadas por filtro: {sum(self.propiedades_descartadas.values())}"
        )
        
        return resultados
    
    def _obtener_fase_eliminada_como_en_lista(self, prop_dict: Dict) -> Optional[str]:
        """
        Versión simplificada que solo verifica si una propiedad pasa los filtros
        (usada internamente para estadísticas).
        """
        return scoring.aplicar_filtros_duros(prop_dict, self.req_data)
    
    def obtener_estadisticas(self) -> Dict[str, Any]:
        """Devuelve estadísticas del matching ejecutado."""
        total_descartadas = sum(self.propiedades_descartadas.values())
        descartadas_con_data = {k: v for k, v in self.propiedades_descartadas.items() if v > 0}
        return {
            'total_evaluadas': self.propiedades_evaluadas,
            'total_descartadas': total_descartadas,
            'total_compatibles': len(self.propiedades_compatibles),
            'descartadas_por_campo': descartadas_con_data,
            'score_promedio': self._calcular_score_promedio(),
            'propiedad_top': self._obtener_propiedad_top(),
        }
    
    def _calcular_score_promedio(self) -> float:
        if not self.propiedades_compatibles:
            return 0.0
        total = sum(r['score_total'] for r in self.propiedades_compatibles)
        return round(total / len(self.propiedades_compatibles), 2)
    
    def _obtener_propiedad_top(self) -> Optional[Dict]:
        if not self.propiedades_compatibles:
            return None
        return max(self.propiedades_compatibles, key=lambda x: x['score_total'])


# ============================================================
# Funciones de conveniencia
# ============================================================

def ejecutar_matching_requerimiento(requerimiento_id: int, propiedades=None) -> Tuple[List[Dict], Dict[str, Any]]:
    """
    Ejecuta matching para un requerimiento.
    
    Args:
        requerimiento_id: ID del requerimiento.
        propiedades: Lista de dicts de propiedades (opcional, si None se cargan).
        
    Returns:
        Tuple (resultados, estadisticas)
    """
    try:
        requerimiento = Requerimiento.objects.get(id=requerimiento_id)
    except Requerimiento.DoesNotExist:
        raise ValueError(f"Requerimiento con ID {requerimiento_id} no existe.")
    
    if propiedades is None:
        propiedades = _fetch_properties(is_active_only=True)
    
    engine = MatchingEngine(requerimiento)
    resultados = engine.ejecutar_matching(propiedades)
    estadisticas = engine.obtener_estadisticas()
    
    return resultados, estadisticas


def guardar_resultados_matching(requerimiento_id: int, resultados: List[Dict]) -> List[Any]:
    """
    Guarda los resultados del matching en MatchResult (v4).
    
    Compatible con el nuevo formato score_detalle:
    {factor: {score: float, peso_maximo: int, detalle: str}}
    
    Args:
        requerimiento_id: ID del requerimiento.
        resultados: Lista de resultados del matching.
        
    Returns:
        Lista de objetos MatchResult creados.
    """
    from decimal import Decimal
    
    requerimiento = Requerimiento.objects.get(id=requerimiento_id)
    from .models import MatchResult
    objetos_creados = []
    
    for resultado in resultados:
        score_detalle = resultado.get('score_detalle', {})
        if isinstance(score_detalle, dict):
            score_detalle_clean = {}
            for k, v in score_detalle.items():
                if isinstance(v, dict) and 'score' in v:
                    # Nuevo formato: {score, peso_maximo, detalle}
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


def ejecutar_matching_masivo(requerimientos=None, propiedades=None, limite_por_requerimiento=10):
    """
    Ejecuta matching para múltiples requerimientos.
    
    Args:
        requerimientos: QuerySet de requerimientos (si None, todos)
        propiedades: Lista de dicts de propiedades (si None, se cargan)
        limite_por_requerimiento: Máximo de resultados a guardar por requerimiento
        
    Returns:
        Dict con resultados por requerimiento
    """
    from django.utils import timezone
    
    if requerimientos is None:
        requerimientos = Requerimiento.objects.all().order_by('-fecha', '-hora')[:2000]
    
    if propiedades is None:
        propiedades = _fetch_properties(is_active_only=True)
    
    resultados_masivo = {}
    
    for requerimiento in requerimientos:
        engine = MatchingEngine(requerimiento)
        resultados = engine.ejecutar_matching(propiedades)
        
        try:
            top_resultados = resultados[:limite_por_requerimiento]
            guardar_resultados_matching(requerimiento.id, top_resultados)
        except Exception as e:
            logger.error(f"Error guardando matching para req {requerimiento.id}: {e}")
        
        compatibles = [r for r in resultados if r['fase_eliminada'] is None]
        total_compatibles = len(compatibles)
        
        if total_compatibles > 0:
            mejor_resultado = compatibles[0]
            mejor_score = float(mejor_resultado['score_total'])
            score_promedio = sum(r['score_total'] for r in compatibles) / total_compatibles
            
            prop_dict = mejor_resultado['propiedad_dict']
            mejor_propiedad = {
                'id': prop_dict['id'],
                'code': prop_dict.get('code'),
                'title': prop_dict.get('title'),
                'district': prop_dict.get('district_id'),
                'district_name': _get_district_name(prop_dict.get('district_id')),
                'price': float(prop_dict['price']) if prop_dict.get('price') else None,
                'currency_id': prop_dict.get('currency_id'),
                'property_type': _get_property_type_name(prop_dict.get('property_type_id')),
            }
        else:
            mejor_score = 0.0
            score_promedio = 0.0
            mejor_propiedad = None
        
        resultados_masivo[requerimiento.id] = {
            'requerimiento_id': requerimiento.id,
            'requerimiento_nombre': str(requerimiento),
            'mejor_score': mejor_score,
            'score_promedio': score_promedio,
            'total_compatibles': total_compatibles,
            'mejor_propiedad': mejor_propiedad,
        }
    
    return resultados_masivo


def obtener_resumen_matching_masivo(limite=500):
    """
    Retorna un resumen de matching para todos los requerimientos con MatchResult.
    """
    from .models import MatchResult
    from requerimientos.models import Requerimiento
    from django.db.models import Max, Avg

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
                # Extraer scores semántico y estructural del score_detalle
                # Compatible con formatos: nuevo {factor: {score, peso_maximo, detalle}} y antiguo {factor: score}
                sd = mejor.score_detalle or {}
                
                def _extraer_score(d, key, default=0):
                    val = d.get(key, default)
                    if isinstance(val, dict):
                        return float(val.get('score', default))
                    return float(val) if val else default
                
                score_semantico = _extraer_score(sd, 'semantico')
                score_structural = _extraer_score(sd, 'score_structural', mejor.score_total)
                alpha = float(sd.get('alpha', 0.6)) if not isinstance(sd.get('alpha'), dict) else 0.6
                
                # Determinar tipo de match predominante
                if score_semantico > 0 and score_structural > 0:
                    if alpha >= 0.6:
                        match_tipo = 'estructural'
                        match_tipo_label = 'Estructural'
                    else:
                        match_tipo = 'semantico'
                        match_tipo_label = 'Semántico'
                elif score_semantico > 0:
                    match_tipo = 'semantico'
                    match_tipo_label = 'Semántico'
                elif score_structural > 0:
                    match_tipo = 'estructural'
                    match_tipo_label = 'Estructural'
                else:
                    match_tipo = 'legacy'
                    match_tipo_label = 'Legacy'
                
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
                    prop_code = None
                    prop_title = None
                    prop_distrito = None
                    prop_precio = None
                    prop_moneda = None
                    prop_tipo = None

                # Calcular score semantico REAL desde embeddings (si estan disponibles)
                real_semantic = score_semantico
                try:
                    from intelligence.models import IntelligenceDocument
                    import numpy as np
                    req_doc = IntelligenceDocument.objects.filter(
                        collection__name='requerimientos_enbedados',
                        source_id=str(req_id)
                    ).first()
                    prop_doc = IntelligenceDocument.objects.filter(
                        collection__name='propiedadespropify',
                        source_id=str(mejor.propiedad_id)
                    ).first()
                    if req_doc and prop_doc and req_doc.embedding and prop_doc.embedding:
                        qv = np.frombuffer(req_doc.embedding, dtype=np.float32)
                        pv = np.frombuffer(prop_doc.embedding, dtype=np.float32)
                        qn = np.linalg.norm(qv)
                        pn = np.linalg.norm(pv)
                        if qn > 0 and pn > 0:
                            real_semantic = round(float(np.dot(qv, pv) / (qn * pn)), 4)
                except Exception:
                    pass

                resumen.append({
                    'requerimiento_id': req_id,
                    'requerimiento_nombre': str(req),
                    'porcentaje_match': float(mejor.score_total),
                    'score_semantico': real_semantic,
                    'score_structural': score_structural,
                    'match_tipo': match_tipo,
                    'match_tipo_label': match_tipo_label,
                    'alpha': alpha,
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