"""
Motor de matching inmobiliario v3 — ADAPTADO PARA dbpropify_be.

Cambios respecto a v2:
1. Usa raw SQL con JOIN entre property y property_specs (dbpropify_be)
2. No depende de campos ORM que no existen en la tabla `property`
3. Los specs (bedrooms, bathrooms, areas, amenities) vienen de property_specs
4. Los lookup values (district name, property type name) se resuelven con SQL
5. MatchResult guarda property_id como entero (no ForeignKey a PropifaiProperty)
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from django.db import connections
from django.conf import settings

from requerimientos.models import Requerimiento
from propifai.mapeo_ubicaciones import DISTRITOS

logger = logging.getLogger(__name__)

# Cache global de PropertyTypes (se carga una vez)
_PROPERTY_TYPES_CACHE = None
_PROPERTY_TYPES_NAME_TO_ID = None

# Cache de nombres de distrito (id → nombre)
_DISTRICT_CACHE = {}

# Tipo de cambio configurable (PEN por USD)
TIPO_CAMBIO_USD_PEN = Decimal('3.75')


def _recargar_cache_property_types():
    """Recarga el cache de PropertyTypes desde la BD propifai."""
    global _PROPERTY_TYPES_CACHE, _PROPERTY_TYPES_NAME_TO_ID
    try:
        with connections['propifai'].cursor() as cursor:
            cursor.execute("SELECT id, name FROM property_type WHERE is_active = 1")
            rows = cursor.fetchall()
            _PROPERTY_TYPES_CACHE = {row[0]: row[1] for row in rows}
            _PROPERTY_TYPES_NAME_TO_ID = {}
            for pt_id, pt_name in _PROPERTY_TYPES_CACHE.items():
                nombre_key = pt_name.lower().strip()
                _PROPERTY_TYPES_NAME_TO_ID[nombre_key] = pt_id
                # Variantes comunes
                if nombre_key == 'departamento':
                    _PROPERTY_TYPES_NAME_TO_ID['depto'] = pt_id
                    _PROPERTY_TYPES_NAME_TO_ID['deptos'] = pt_id
                    _PROPERTY_TYPES_NAME_TO_ID['dpto'] = pt_id
                elif nombre_key == 'casa':
                    _PROPERTY_TYPES_NAME_TO_ID['casas'] = pt_id
                elif nombre_key == 'terreno':
                    _PROPERTY_TYPES_NAME_TO_ID['terrenos'] = pt_id
                elif nombre_key == 'local':
                    _PROPERTY_TYPES_NAME_TO_ID['local_comercial'] = pt_id
                    _PROPERTY_TYPES_NAME_TO_ID['local comercial'] = pt_id
                    _PROPERTY_TYPES_NAME_TO_ID['locales'] = pt_id
                    _PROPERTY_TYPES_NAME_TO_ID['locales comerciales'] = pt_id
                elif nombre_key == 'oficina':
                    _PROPERTY_TYPES_NAME_TO_ID['oficinas'] = pt_id
        logger.debug(f"Cache de PropertyTypes recargado: {_PROPERTY_TYPES_CACHE}")
    except Exception as e:
        logger.error(f"Error al cargar PropertyTypes: {e}")
        _PROPERTY_TYPES_CACHE = {}
        _PROPERTY_TYPES_NAME_TO_ID = {}


def _get_property_type_id(nombre_tipo: str) -> Optional[int]:
    """Resuelve un nombre de tipo de propiedad a un ID de property_type."""
    global _PROPERTY_TYPES_NAME_TO_ID
    if _PROPERTY_TYPES_NAME_TO_ID is None:
        _recargar_cache_property_types()
    nombre_limpio = nombre_tipo.lower().strip()
    return _PROPERTY_TYPES_NAME_TO_ID.get(nombre_limpio)


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


def _convertir_moneda(monto: Decimal, moneda_origen: str, moneda_destino: str) -> Decimal:
    """Convierte un monto entre USD y PEN."""
    if moneda_origen == moneda_destino:
        return monto
    if moneda_origen == 'USD' and moneda_destino == 'PEN':
        return monto * TIPO_CAMBIO_USD_PEN
    elif moneda_origen == 'PEN' and moneda_destino == 'USD':
        return monto / TIPO_CAMBIO_USD_PEN
    return monto


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
                pm.file
            FROM property p
            LEFT JOIN property_specs s ON s.property_id = p.id
            LEFT JOIN property_media pm ON pm.property_id = p.id AND pm.media_type = 'image' AND pm.order = 1
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
    """Obtiene el nombre del tipo de propiedad."""
    if not property_type_id:
        return None
    global _PROPERTY_TYPES_CACHE
    if _PROPERTY_TYPES_CACHE is None:
        _recargar_cache_property_types()
    return _PROPERTY_TYPES_CACHE.get(property_type_id)


class MatchingEngine:
    """
    Motor principal de matching v3 — adaptado para dbpropify_be.
    
    Usa raw SQL con JOIN entre property y property_specs.
    Todas las propiedades se cargan como diccionarios al inicio.
    """
    
    # Pesos para campos de scoring (suman 100)
    PESOS = {
        'precio': 20,
        'area': 12,
        'habitaciones': 10,
        'banos': 7,
        'antiguedad': 5,
        'estacionamiento': 5,
        'distrito': 15,
        'amenities': 10,
        'ascensor': 4,
        'tipo_propiedad': 12,
    }
    
    TOLERANCIA_NUMERICA = 0.10  # 10%
    
    def __init__(self, requerimiento: Requerimiento):
        self.requerimiento = requerimiento
        self.propiedades_evaluadas = 0
        self.propiedades_descartadas = {
            'tipo_propiedad': 0,
            'condicion': 0,
            'distrito': 0,
            'presupuesto': 0,
        }
        self.propiedades_compatibles = []
        
        # Cargar cache de PropertyTypes si no está cargado
        global _PROPERTY_TYPES_NAME_TO_ID
        if _PROPERTY_TYPES_NAME_TO_ID is None:
            _recargar_cache_property_types()
    
    def ejecutar_matching(self, propiedades: List[Dict] = None) -> List[Dict]:
        """
        Ejecuta el matching completo para el requerimiento.
        
        Args:
            propiedades: Lista de diccionarios con datos de propiedades.
                         Si es None, se cargan desde la BD.
                         
        Returns:
            Lista de diccionarios con resultados.
        """
        if propiedades is None:
            propiedades = _fetch_properties(is_active_only=True)
        
        resultados = []
        
        for prop_dict in propiedades:
            self.propiedades_evaluadas += 1
            
            # FASE 1: Filtros discriminatorios
            fase_eliminada = self._aplicar_filtros_discriminatorios(prop_dict)
            if fase_eliminada:
                self.propiedades_descartadas[fase_eliminada] += 1
                continue
            
            # FASE 2: Scoring ponderado
            score_total, score_detalle = self._calcular_scoring(prop_dict)
            
            resultado = {
                'propiedad_dict': prop_dict,
                'propiedad_id': prop_dict['id'],
                'score_total': score_total,
                'score_detalle': score_detalle,
                'fase_eliminada': None,
                'porcentaje_compatibilidad': score_total,
            }
            
            resultados.append(resultado)
            self.propiedades_compatibles.append(resultado)
        
        # Ordenar por score descendente
        resultados.sort(key=lambda x: x['score_total'], reverse=True)
        
        # Asignar ranking
        for i, resultado in enumerate(resultados, 1):
            resultado['ranking'] = i
        
        logger.info(
            f"Matching v3 completado para requerimiento {self.requerimiento.id}. "
            f"Evaluadas: {self.propiedades_evaluadas}, "
            f"Compatibles: {len(resultados)}, "
            f"Descartadas: {sum(self.propiedades_descartadas.values())}"
        )
        
        return resultados
    
    def _aplicar_filtros_discriminatorios(self, prop_dict: Dict) -> Optional[str]:
        """Aplica los filtros discriminatorios."""
        if not self._coincide_tipo_propiedad(prop_dict):
            return 'tipo_propiedad'
        if not self._coincide_condicion(prop_dict):
            return 'condicion'
        if not self._coincide_distrito(prop_dict):
            return 'distrito'
        if not self._dentro_de_presupuesto(prop_dict):
            return 'presupuesto'
        return None
    
    def _coincide_tipo_propiedad(self, prop_dict: Dict) -> bool:
        """Verifica si el tipo de propiedad coincide."""
        tipo_req = self.requerimiento.tipo_propiedad
        if not tipo_req:
            return True
        
        valores_sin_filtro = {'no_especificado', 'no especificado', 'todos', 'cualquiera', ''}
        if tipo_req.lower().strip() in valores_sin_filtro:
            return True
        
        property_type_id = prop_dict.get('property_type_id')
        if not property_type_id:
            return False
        
        tipo_id_esperado = _get_property_type_id(tipo_req)
        if tipo_id_esperado is None:
            logger.warning(
                f"No se pudo resolver tipo_propiedad '{tipo_req}' del requerimiento "
                f"{self.requerimiento.id}. Aceptando propiedad."
            )
            return True
        
        return property_type_id == tipo_id_esperado
    
    def _coincide_condicion(self, prop_dict: Dict) -> bool:
        """Verifica si la condición (compra/alquiler) coincide."""
        condicion_req = self.requerimiento.condicion
        if not condicion_req:
            return True
        
        operation_type_id = prop_dict.get('operation_type_id')
        if not operation_type_id:
            return True
        
        condicion = condicion_req.lower().strip()
        
        if condicion in ('compra',):
            return operation_type_id in (1, 2)
        elif condicion in ('alquiler', 'anticresis'):
            return operation_type_id == 3
        
        return True
    
    def _coincide_distrito(self, prop_dict: Dict) -> bool:
        """Verifica si el distrito de la propiedad está en la lista del requerimiento."""
        if not self.requerimiento.distritos:
            return True
        
        distritos_str = str(self.requerimiento.distritos).lower().strip()
        if distritos_str == 'nan' or distritos_str == '':
            return True
        
        distritos_requerimiento = self.requerimiento.distritos_lista
        district_id = prop_dict.get('district_id')
        
        if not district_id:
            return False
        
        district_id_str = str(district_id).strip()
        
        for distrito_req in distritos_requerimiento:
            distrito_req_limpio = distrito_req.strip().lower()
            
            # 1. Coincidencia directa
            if distrito_req_limpio == district_id_str:
                return True
            
            # 2. Resolver nombre del requerimiento a ID
            id_resuelto = _get_distrito_id(distrito_req_limpio)
            if id_resuelto and id_resuelto == district_id_str:
                return True
            
            # 3. Resolver ID de la propiedad a nombre y comparar
            nombre_prop = _get_district_name(district_id)
            if nombre_prop:
                nombre_prop_norm = nombre_prop.lower().strip()
                if distrito_req_limpio == nombre_prop_norm:
                    return True
                if distrito_req_limpio in nombre_prop_norm or nombre_prop_norm in distrito_req_limpio:
                    return True
        
        return False
    
    def _dentro_de_presupuesto(self, prop_dict: Dict) -> bool:
        """Verifica si el precio está dentro del presupuesto."""
        if not self.requerimiento.presupuesto_monto:
            return True
        
        price = prop_dict.get('price')
        if not price:
            return False
        
        presupuesto = Decimal(str(self.requerimiento.presupuesto_monto))
        precio = Decimal(str(price))
        
        moneda_req = (self.requerimiento.presupuesto_moneda or 'PEN').upper()
        moneda_prop = _get_moneda_propiedad(prop_dict)
        
        presupuesto_en_pen = _convertir_moneda(presupuesto, moneda_req, 'PEN')
        precio_en_pen = _convertir_moneda(precio, moneda_prop, 'PEN')
        
        limite_maximo = presupuesto_en_pen * Decimal('1.10')
        
        return precio_en_pen <= limite_maximo
    
    def _calcular_scoring(self, prop_dict: Dict) -> Tuple[Decimal, Dict[str, Decimal]]:
        """Calcula el score ponderado para una propiedad."""
        score_detalle = {}
        score_total = Decimal('0.0')
        
        score_precio = self._calcular_score_precio(prop_dict)
        score_detalle['precio'] = score_precio
        score_total += score_precio * Decimal(str(self.PESOS['precio'])) / 100
        
        score_area = self._calcular_score_area(prop_dict)
        score_detalle['area'] = score_area
        score_total += score_area * Decimal(str(self.PESOS['area'])) / 100
        
        score_habitaciones = self._calcular_score_habitaciones(prop_dict)
        score_detalle['habitaciones'] = score_habitaciones
        score_total += score_habitaciones * Decimal(str(self.PESOS['habitaciones'])) / 100
        
        score_banos = self._calcular_score_banos(prop_dict)
        score_detalle['banos'] = score_banos
        score_total += score_banos * Decimal(str(self.PESOS['banos'])) / 100
        
        score_antiguedad = self._calcular_score_antiguedad(prop_dict)
        score_detalle['antiguedad'] = score_antiguedad
        score_total += score_antiguedad * Decimal(str(self.PESOS['antiguedad'])) / 100
        
        score_distrito = self._calcular_score_distrito(prop_dict)
        score_detalle['distrito'] = score_distrito
        score_total += score_distrito * Decimal(str(self.PESOS['distrito'])) / 100
        
        score_amenities = self._calcular_score_amenities(prop_dict)
        score_detalle['amenities'] = score_amenities
        score_total += score_amenities * Decimal(str(self.PESOS['amenities'])) / 100
        
        score_ascensor = self._calcular_score_ascensor(prop_dict)
        score_detalle['ascensor'] = score_ascensor
        score_total += score_ascensor * Decimal(str(self.PESOS['ascensor'])) / 100
        
        score_tipo = self._calcular_score_tipo_propiedad(prop_dict)
        score_detalle['tipo_propiedad'] = score_tipo
        score_total += score_tipo * Decimal(str(self.PESOS['tipo_propiedad'])) / 100
        
        score_total = score_total * Decimal('100.0')
        score_total = max(Decimal('0.0'), min(Decimal('100.0'), score_total))
        
        return score_total, score_detalle
    
    def _calcular_score_precio(self, prop_dict: Dict) -> Decimal:
        """Calcula score para precio vs presupuesto."""
        if not self.requerimiento.presupuesto_monto or not prop_dict.get('price'):
            return Decimal('0.5')
        
        presupuesto = Decimal(str(self.requerimiento.presupuesto_monto))
        precio = Decimal(str(prop_dict['price']))
        
        moneda_req = (self.requerimiento.presupuesto_moneda or 'PEN').upper()
        moneda_prop = _get_moneda_propiedad(prop_dict)
        
        presupuesto_pen = _convertir_moneda(presupuesto, moneda_req, 'PEN')
        precio_pen = _convertir_moneda(precio, moneda_prop, 'PEN')
        
        if precio_pen <= presupuesto_pen:
            return Decimal('1.0')
        else:
            limite_maximo = presupuesto_pen * Decimal('1.10')
            if precio_pen > limite_maximo:
                return Decimal('0.0')
            
            diferencia = precio_pen - presupuesto_pen
            rango_tolerancia = limite_maximo - presupuesto_pen
            if rango_tolerancia > 0:
                penalizacion = diferencia / rango_tolerancia
                return Decimal('1.0') - penalizacion
            return Decimal('0.0')
    
    def _calcular_score_area(self, prop_dict: Dict) -> Decimal:
        """Calcula score para área construida."""
        if not self.requerimiento.area_m2 or not prop_dict.get('built_area'):
            return Decimal('0.5')
        
        area_deseada = Decimal(str(self.requerimiento.area_m2))
        area_propiedad = Decimal(str(prop_dict['built_area']))
        
        if area_propiedad == 0:
            return Decimal('0.0')
        
        diferencia_porcentual = abs(area_propiedad - area_deseada) / area_deseada
        
        if diferencia_porcentual <= self.TOLERANCIA_NUMERICA:
            return Decimal('1.0')
        if diferencia_porcentual > 0.5:
            return Decimal('0.0')
        
        tolerancia_decimal = Decimal(str(self.TOLERANCIA_NUMERICA))
        return Decimal('1.0') - (diferencia_porcentual - tolerancia_decimal) / Decimal('0.4')
    
    def _calcular_score_habitaciones(self, prop_dict: Dict) -> Decimal:
        """Calcula score para número de habitaciones."""
        if not self.requerimiento.habitaciones or not prop_dict.get('bedrooms'):
            return Decimal('0.5')
        
        habitaciones_deseadas = self.requerimiento.habitaciones
        habitaciones_propiedad = prop_dict['bedrooms']
        
        if habitaciones_propiedad >= habitaciones_deseadas:
            return Decimal('1.0')
        else:
            diferencia = habitaciones_deseadas - habitaciones_propiedad
            if diferencia >= 3:
                return Decimal('0.0')
            return Decimal('1.0') - Decimal(str(diferencia)) / Decimal('3.0')
    
    def _calcular_score_banos(self, prop_dict: Dict) -> Decimal:
        """Calcula score para número de baños."""
        if not self.requerimiento.banos or not prop_dict.get('bathrooms'):
            return Decimal('0.5')
        
        banos_deseados = self.requerimiento.banos
        banos_propiedad = prop_dict['bathrooms']
        
        if banos_propiedad >= banos_deseados:
            return Decimal('1.0')
        else:
            diferencia = banos_deseados - banos_propiedad
            if diferencia >= 2:
                return Decimal('0.0')
            return Decimal('1.0') - Decimal(str(diferencia)) / Decimal('2.0')
    
    def _calcular_score_antiguedad(self, prop_dict: Dict) -> Decimal:
        """Calcula score para antigüedad."""
        antiguedad = prop_dict.get('antiquity_years')
        if not antiguedad:
            return Decimal('0.5')
        
        if antiguedad <= 5:
            return Decimal('1.0')
        elif antiguedad <= 15:
            return Decimal('0.7')
        elif antiguedad <= 30:
            return Decimal('0.4')
        else:
            return Decimal('0.1')
    
    def _calcular_score_distrito(self, prop_dict: Dict) -> Decimal:
        """Calcula score adicional para distrito."""
        if not self.requerimiento.distritos or not prop_dict.get('district_id'):
            return Decimal('0.5')
        
        distritos_requerimiento = self.requerimiento.distritos_lista
        district_id_str = str(prop_dict['district_id']).strip()
        
        if distritos_requerimiento:
            primer_distrito = distritos_requerimiento[0].strip().lower()
            id_primer_distrito = _get_distrito_id(primer_distrito)
            if id_primer_distrito and id_primer_distrito == district_id_str:
                return Decimal('1.0')
        
        return Decimal('0.8')
    
    def _calcular_score_amenities(self, prop_dict: Dict) -> Decimal:
        """Calcula score para amenities basado en booleanos de property_specs."""
        score = Decimal('0.5')
        
        if not self.requerimiento.caracteristicas_extra:
            return score
        
        extras_req = self.requerimiento.caracteristicas_extra.lower()
        
        # Mapear palabras clave del requerimiento a campos booleanos de property_specs
        amenity_map = {
            'piscina': 'has_pool',
            'pileta': 'has_pool',
            'jardin': 'has_garden',
            'jardín': 'has_garden',
            'bbq': 'has_bbq',
            'parrilla': 'has_bbq',
            'terraza': 'has_terrace',
            'azotea': 'has_terrace',
            'aire acondicionado': 'has_air_conditioning',
            'aa': 'has_air_conditioning',
            'lavandería': 'has_laundry_area',
            'lavanderia': 'has_laundry_area',
            'cuarto de servicio': 'has_service_room',
            'servicio': 'has_service_room',
            'ascensor': 'has_elevator',
            'elevador': 'has_elevator',
            'seguridad': 'has_security',
            'mascotas': 'pet_friendly',
            'pet friendly': 'pet_friendly',
            'estacionamiento': 'garage_spaces',
            'cochera': 'garage_spaces',
            'garage': 'garage_spaces',
        }
        
        palabras_clave = extras_req.replace(',', ' ').split()
        palabras_clave = [p.strip() for p in palabras_clave if len(p.strip()) > 2]
        
        if not palabras_clave:
            return score
        
        coincidencias = 0
        total_buscadas = 0
        
        for palabra in palabras_clave:
            campo = amenity_map.get(palabra)
            if campo:
                total_buscadas += 1
                if campo == 'garage_spaces':
                    if prop_dict.get('garage_spaces') and prop_dict['garage_spaces'] > 0:
                        coincidencias += 1
                else:
                    if prop_dict.get(campo) is True:
                        coincidencias += 1
        
        if total_buscadas > 0:
            ratio = coincidencias / total_buscadas
            return Decimal('0.5') + Decimal(str(ratio)) * Decimal('0.5')
        
        return score
    
    def _calcular_score_ascensor(self, prop_dict: Dict) -> Decimal:
        """Calcula score para ascensor."""
        if self.requerimiento.ascensor == 'indiferente' or not self.requerimiento.ascensor:
            return Decimal('0.5')
        
        has_elevator = prop_dict.get('has_elevator')
        
        if self.requerimiento.ascensor == 'si':
            if has_elevator is True:
                return Decimal('1.0')
            return Decimal('0.0')
        elif self.requerimiento.ascensor == 'no':
            if has_elevator is False or has_elevator is None:
                return Decimal('1.0')
            return Decimal('0.0')
        
        return Decimal('0.5')
    
    def _calcular_score_tipo_propiedad(self, prop_dict: Dict) -> Decimal:
        """Score extra si el tipo de propiedad coincide exactamente."""
        if not self.requerimiento.tipo_propiedad or not prop_dict.get('property_type_id'):
            return Decimal('0.5')
        
        tipo_id_esperado = _get_property_type_id(self.requerimiento.tipo_propiedad)
        if tipo_id_esperado and prop_dict['property_type_id'] == tipo_id_esperado:
            return Decimal('1.0')
        
        return Decimal('0.5')
    
    def obtener_estadisticas(self) -> Dict[str, Any]:
        """Devuelve estadísticas del matching ejecutado."""
        total_descartadas = sum(self.propiedades_descartadas.values())
        return {
            'total_evaluadas': self.propiedades_evaluadas,
            'total_descartadas': total_descartadas,
            'total_compatibles': len(self.propiedades_compatibles),
            'descartadas_por_campo': self.propiedades_descartadas,
            'score_promedio': self._calcular_score_promedio(),
            'propiedad_top': self._obtener_propiedad_top(),
        }
    
    def _calcular_score_promedio(self) -> Decimal:
        if not self.propiedades_compatibles:
            return Decimal('0.0')
        total = sum(Decimal(str(r['score_total'])) for r in self.propiedades_compatibles)
        return total / len(self.propiedades_compatibles)
    
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
    Guarda los resultados del matching en MatchResult.
    
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
        score_detalle = resultado['score_detalle']
        if isinstance(score_detalle, dict):
            score_detalle = {
                k: float(v) if isinstance(v, Decimal) else v
                for k, v in score_detalle.items()
            }
        
        match_result = MatchResult(
            requerimiento=requerimiento,
            propiedad_id=resultado['propiedad_id'],
            score_total=resultado['score_total'],
            score_detalle=score_detalle,
            fase_eliminada=resultado['fase_eliminada'],
            porcentaje_compatibilidad=resultado['porcentaje_compatibilidad'],
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

        reqs_map = {r.id: r for r in Requerimiento.objects.filter(id__in=req_ids)}

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
                resumen.append({
                    'requerimiento_id': req_id,
                    'requerimiento_nombre': str(req),
                    'porcentaje_match': float(mejor.score_total),
                    'score_promedio': float(item.get('max_score', 0)),
                    'total_compatibles': 1,
                    'mejor_propiedad_id': mejor.propiedad_id,
                    'mejor_propiedad_codigo': None,
                    'mejor_propiedad_titulo': None,
                    'mejor_propiedad_distrito': None,
                    'mejor_propiedad_precio': None,
                    'mejor_propiedad_moneda_id': None,
                    'mejor_propiedad_tipo': None,
                })

        return resumen[:limite]
    except Exception as e:
        logger.error(f"Error en obtener_resumen_matching_masivo: {e}")
        return []