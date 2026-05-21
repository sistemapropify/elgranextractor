"""
Motor de matching inmobiliario v2 — MEJORADO.

Corrige los problemas identificados en la versión anterior:
1. Resuelve FK IDs (property_type_id, district) vs texto del requerimiento
2. Usa mapeo_ubicaciones.py como fuente única de verdad para distritos
3. Soporta moneda (USD/PEN) con tipo de cambio configurable
4. Corrige nombres de campo (amenities, availability_status, zoning)
5. Agrega filtro por condicion (compra/alquiler → operation_type_id)
6. Ajusta PESOS a campos que realmente existen en la BD
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from django.db.models import QuerySet

from requerimientos.models import Requerimiento
from propifai.models import PropifaiProperty, PropertyType
from propifai.mapeo_ubicaciones import DISTRITOS
from .models import MatchResult

logger = logging.getLogger(__name__)

# Cache global de PropertyTypes (se carga una vez)
_PROPERTY_TYPES_CACHE = None
_PROPERTY_TYPES_NAME_TO_ID = None

# Tipo de cambio configurable (PEN por USD)
# 1 USD = 3.75 PEN (tipo de cambio referencial, ajustable)
TIPO_CAMBIO_USD_PEN = Decimal('3.75')


def _recargar_cache_property_types():
    """Recarga el cache de PropertyTypes desde la BD propifai."""
    global _PROPERTY_TYPES_CACHE, _PROPERTY_TYPES_NAME_TO_ID
    try:
        types = PropertyType.objects.using('propifai').all()
        _PROPERTY_TYPES_CACHE = {pt.id: pt.name for pt in types}
        _PROPERTY_TYPES_NAME_TO_ID = {}
        for pt in types:
            nombre_key = pt.name.lower().strip()
            _PROPERTY_TYPES_NAME_TO_ID[nombre_key] = pt.id
            # También mapear variantes comunes
            if nombre_key == 'departamento':
                _PROPERTY_TYPES_NAME_TO_ID['depto'] = pt.id
                _PROPERTY_TYPES_NAME_TO_ID['departamento'] = pt.id
                _PROPERTY_TYPES_NAME_TO_ID['deptos'] = pt.id
                _PROPERTY_TYPES_NAME_TO_ID['dpto'] = pt.id
            elif nombre_key == 'casa':
                _PROPERTY_TYPES_NAME_TO_ID['casa'] = pt.id
                _PROPERTY_TYPES_NAME_TO_ID['casas'] = pt.id
            elif nombre_key == 'terreno':
                _PROPERTY_TYPES_NAME_TO_ID['terreno'] = pt.id
                _PROPERTY_TYPES_NAME_TO_ID['terrenos'] = pt.id
            elif nombre_key == 'local':
                _PROPERTY_TYPES_NAME_TO_ID['local'] = pt.id
                _PROPERTY_TYPES_NAME_TO_ID['local_comercial'] = pt.id  # Requerimiento usa snake_case
                _PROPERTY_TYPES_NAME_TO_ID['local comercial'] = pt.id
                _PROPERTY_TYPES_NAME_TO_ID['locales'] = pt.id
                _PROPERTY_TYPES_NAME_TO_ID['locales comerciales'] = pt.id
            elif nombre_key == 'oficina':
                _PROPERTY_TYPES_NAME_TO_ID['oficina'] = pt.id
                _PROPERTY_TYPES_NAME_TO_ID['oficinas'] = pt.id
        logger.debug(f"Cache de PropertyTypes recargado: {_PROPERTY_TYPES_CACHE}")
    except Exception as e:
        logger.error(f"Error al cargar PropertyTypes: {e}")
        _PROPERTY_TYPES_CACHE = {}
        _PROPERTY_TYPES_NAME_TO_ID = {}


def _get_property_type_id(nombre_tipo: str) -> Optional[int]:
    """
    Resuelve un nombre de tipo de propiedad (del requerimiento) a un ID de property_types.
    
    Args:
        nombre_tipo: Nombre del tipo (ej: 'departamento', 'casa', 'terreno')
        
    Returns:
        ID numérico en property_types, o None si no se encuentra.
    """
    global _PROPERTY_TYPES_NAME_TO_ID
    if _PROPERTY_TYPES_NAME_TO_ID is None:
        _recargar_cache_property_types()
    
    nombre_limpio = nombre_tipo.lower().strip()
    return _PROPERTY_TYPES_NAME_TO_ID.get(nombre_limpio)


def _get_distrito_id(nombre_distrito: str) -> Optional[str]:
    """
    Resuelve un nombre de distrito (del requerimiento) a su ID numérico.
    Usa mapeo_ubicaciones.DISTRITOS como fuente única de verdad.
    
    Args:
        nombre_distrito: Nombre del distrito (ej: 'Cayma', 'Miraflores')
        
    Returns:
        ID del distrito (string) o None si no se encuentra.
    """
    nombre_limpio = nombre_distrito.lower().strip()
    
    # Búsqueda directa inversa en DISTRITOS
    for id_dist, nombre in DISTRITOS.items():
        if nombre.lower().strip() == nombre_limpio:
            return id_dist
    
    # Búsqueda parcial (substring) para variaciones
    for id_dist, nombre in DISTRITOS.items():
        nombre_normalizado = nombre.lower().strip()
        # "Cayma alta" → contiene "Cayma"
        if nombre_limpio in nombre_normalizado or nombre_normalizado in nombre_limpio:
            return id_dist
    
    return None


def _convertir_moneda(monto: Decimal, moneda_origen: str, moneda_destino: str) -> Decimal:
    """
    Convierte un monto entre USD y PEN.
    
    Args:
        monto: Monto a convertir
        moneda_origen: 'USD' o 'PEN'
        moneda_destino: 'USD' o 'PEN'
        
    Returns:
        Monto convertido
    """
    if moneda_origen == moneda_destino:
        return monto
    
    if moneda_origen == 'USD' and moneda_destino == 'PEN':
        return monto * TIPO_CAMBIO_USD_PEN
    elif moneda_origen == 'PEN' and moneda_destino == 'USD':
        return monto / TIPO_CAMBIO_USD_PEN
    
    return monto


class MatchingEngine:
    """
    Motor principal de matching v2.
    
    Mejoras respecto a v1:
    - Resuelve FK IDs vs texto usando PropertyType cache y mapeo_ubicaciones
    - Soporta moneda (USD/PEN) en comparación de precios
    - Filtra por condicion (compra/alquiler) usando operation_type_id
    - Usa nombres de campo correctos (amenities, availability_status, zoning)
    """
    
    # Pesos para campos de scoring (suman 100)
    # Basados en campos que REALMENTE EXISTEN en PropifaiProperty
    PESOS = {
        'precio': 20,           # Precio vs presupuesto (con soporte de moneda)
        'area': 12,             # Área construida vs área deseada
        'habitaciones': 10,     # Número de habitaciones
        'banos': 7,             # Número de baños
        'antiguedad': 5,        # Antigüedad de la propiedad
        'estacionamiento': 5,   # Espacios de garaje
        'distrito': 15,         # Coincidencia de distrito
        'amenities': 10,        # Amenidades vs características extra
        'ascensor': 4,          # Ascensor
        'tipo_propiedad': 12,   # Tipo de propiedad (resuelto vía PropertyType)
    }
    
    # Tolerancia para campos numéricos (porcentaje)
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
        
    def ejecutar_matching(self, propiedades: QuerySet[PropifaiProperty] = None) -> List[Dict]:
        """
        Ejecuta el matching completo para el requerimiento.
        
        Args:
            propiedades: QuerySet de propiedades a evaluar. Si es None, se evalúan todas activas.
            
        Returns:
            Lista de diccionarios con resultados para cada propiedad que pasó la fase 1.
        """
        if propiedades is None:
            propiedades = PropifaiProperty.objects.filter(is_active=True)
        
        resultados = []
        
        for propiedad in propiedades:
            self.propiedades_evaluadas += 1
            
            # FASE 1: Filtros discriminatorios
            fase_eliminada = self._aplicar_filtros_discriminatorios(propiedad)
            if fase_eliminada:
                self.propiedades_descartadas[fase_eliminada] += 1
                continue
            
            # FASE 2: Scoring ponderado
            score_total, score_detalle = self._calcular_scoring(propiedad)
            
            resultado = {
                'propiedad': propiedad,
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
            f"Matching v2 completado para requerimiento {self.requerimiento.id}. "
            f"Evaluadas: {self.propiedades_evaluadas}, "
            f"Compatibles: {len(resultados)}, "
            f"Descartadas: {sum(self.propiedades_descartadas.values())}"
        )
        
        return resultados
    
    def _aplicar_filtros_discriminatorios(self, propiedad: PropifaiProperty) -> Optional[str]:
        """
        Aplica los filtros discriminatorios.
        
        Returns:
            Nombre del campo que eliminó la propiedad, o None si pasó todos los filtros.
        """
        # 1. Tipo de propiedad (resuelve texto del requerimiento → FK ID de la propiedad)
        if not self._coincide_tipo_propiedad(propiedad):
            return 'tipo_propiedad'
        
        # 2. Condición (compra/alquiler → operation_type_id)
        if not self._coincide_condicion(propiedad):
            return 'condicion'
        
        # 3. Distrito (texto del requerimiento → ID numérico de la propiedad)
        if not self._coincide_distrito(propiedad):
            return 'distrito'
        
        # 4. Presupuesto (con soporte de moneda USD/PEN)
        if not self._dentro_de_presupuesto(propiedad):
            return 'presupuesto'
        
        return None
    
    def _coincide_tipo_propiedad(self, propiedad: PropifaiProperty) -> bool:
        """
        Verifica si el tipo de propiedad coincide.
        
        El requerimiento tiene tipo_propiedad como texto (ej: 'departamento', 'casa').
        La propiedad tiene property_type_id como FK numérico (ej: 2 = Departamento).
        
        Se resuelve usando el cache de PropertyTypes.
        """
        tipo_req = self.requerimiento.tipo_propiedad
        if not tipo_req:
            # Si el requerimiento no especifica tipo, aceptar todas
            return True
        
        # Valores que significan "sin filtro" / "no especificado"
        valores_sin_filtro = {'no_especificado', 'no especificado', 'todos', 'cualquiera', ''}
        if tipo_req.lower().strip() in valores_sin_filtro:
            return True
        
        if not propiedad.property_type_id:
            # Si la propiedad no tiene tipo definido, no podemos verificar
            return False
        
        # Resolver el texto del requerimiento a un ID de property_types
        tipo_id_esperado = _get_property_type_id(tipo_req)
        if tipo_id_esperado is None:
            logger.warning(
                f"No se pudo resolver tipo_propiedad '{tipo_req}' del requerimiento "
                f"{self.requerimiento.id}. Aceptando propiedad."
            )
            return True
        
        # Comparar IDs
        return propiedad.property_type_id == tipo_id_esperado
    
    def _coincide_condicion(self, propiedad: PropifaiProperty) -> bool:
        """
        Verifica si la condición (compra/alquiler) coincide.
        
        El requerimiento tiene condicion como Choice: 'compra', 'alquiler', 'anticresis'.
        La propiedad tiene operation_type_id como FK: 1=Compra, 2=Venta, 3=Alquiler.
        
        Mapeo:
        - 'compra' → operation_type_id IN (1, 2)  # Compra o Venta
        - 'alquiler' → operation_type_id = 3
        - 'anticresis' → operation_type_id = 3 (se trata como alquiler)
        """
        condicion_req = self.requerimiento.condicion
        if not condicion_req:
            return True
        
        if not propiedad.operation_type_id:
            # Si la propiedad no tiene operación definida, asumimos compatible
            return True
        
        condicion = condicion_req.lower().strip()
        
        if condicion in ('compra',):
            # Compra → IDs 1 (Compra) o 2 (Venta)
            return propiedad.operation_type_id in (1, 2)
        elif condicion in ('alquiler', 'anticresis'):
            # Alquiler/Anticresis → ID 3 (Alquiler)
            return propiedad.operation_type_id == 3
        
        # Si no se reconoce la condición, aceptar
        return True
    
    def _coincide_distrito(self, propiedad: PropifaiProperty) -> bool:
        """
        Verifica si el distrito de la propiedad está en la lista de distritos del requerimiento.
        
        El requerimiento tiene distritos como texto libre (ej: 'Cayma, Yanahuara').
        La propiedad tiene district como ID numérico (ej: '3' = Cayma).
        
        Se usa mapeo_ubicaciones.DISTRITOS como fuente única de verdad.
        """
        if not self.requerimiento.distritos:
            return True
        
        distritos_str = str(self.requerimiento.distritos).lower().strip()
        if distritos_str == 'nan' or distritos_str == '':
            return True
        
        distritos_requerimiento = self.requerimiento.distritos_lista
        distrito_propiedad = propiedad.district
        
        if not distrito_propiedad:
            return False
        
        distrito_prop_str = str(distrito_propiedad).strip()
        
        # Verificar si el distrito de la propiedad (como ID) está en los nombres del requerimiento
        for distrito_req in distritos_requerimiento:
            distrito_req_limpio = distrito_req.strip().lower()
            
            # 1. Coincidencia directa: el nombre del requerimiento es el ID
            if distrito_req_limpio == distrito_prop_str:
                return True
            
            # 2. Resolver nombre del requerimiento a ID usando DISTRITOS
            id_resuelto = _get_distrito_id(distrito_req_limpio)
            if id_resuelto and id_resuelto == distrito_prop_str:
                return True
            
            # 3. Resolver ID de la propiedad a nombre y comparar
            nombre_prop = DISTRITOS.get(distrito_prop_str)
            if nombre_prop:
                nombre_prop_norm = nombre_prop.lower().strip()
                if distrito_req_limpio == nombre_prop_norm:
                    return True
                # Coincidencia parcial
                if distrito_req_limpio in nombre_prop_norm or nombre_prop_norm in distrito_req_limpio:
                    return True
        
        return False
    
    def _get_moneda_propiedad(self, propiedad: PropifaiProperty) -> str:
        """
        Determina la moneda de la propiedad basado en currency_id.
        
        currency_id: 1=USD, 2=PEN (según tabla currencies en Azure SQL)
        Si no tiene currency_id, se asume PEN por defecto.
        """
        if hasattr(propiedad, 'currency_id') and propiedad.currency_id:
            if propiedad.currency_id == 1:
                return 'USD'
            elif propiedad.currency_id == 2:
                return 'PEN'
        return 'PEN'  # default
    
    def _convertir_a_moneda_comun(self, monto: Decimal, moneda_origen: str, moneda_destino: str) -> Decimal:
        """Convierte un monto entre USD y PEN."""
        if moneda_origen == moneda_destino:
            return monto
        return _convertir_moneda(monto, moneda_origen, moneda_destino)
    
    def _dentro_de_presupuesto(self, propiedad: PropifaiProperty) -> bool:
        """
        Verifica si el precio de la propiedad está dentro del presupuesto.
        
        SOPORTE DE MONEDA REAL:
        - El requerimiento tiene presupuesto_monto y presupuesto_moneda (USD/PEN)
        - La propiedad tiene price y currency_id (1=USD, 2=PEN)
        - Si las monedas difieren, se convierte usando TIPO_CAMBIO_USD_PEN
        
        Aplica una tolerancia del 10% hacia arriba del límite máximo.
        """
        if not self.requerimiento.presupuesto_monto:
            return True
        
        if not propiedad.price:
            return False
        
        presupuesto = Decimal(str(self.requerimiento.presupuesto_monto))
        precio = Decimal(str(propiedad.price))
        
        # Obtener monedas reales
        moneda_req = (self.requerimiento.presupuesto_moneda or 'PEN').upper()
        moneda_prop = self._get_moneda_propiedad(propiedad)
        
        # Convertir ambos a una moneda común (PEN) para comparar
        presupuesto_en_pen = self._convertir_a_moneda_comun(presupuesto, moneda_req, 'PEN')
        precio_en_pen = self._convertir_a_moneda_comun(precio, moneda_prop, 'PEN')
        
        # Calcular límite máximo con tolerancia del 10%
        limite_maximo = presupuesto_en_pen * Decimal('1.10')
        
        return precio_en_pen <= limite_maximo
    
    def _calcular_scoring(self, propiedad: PropifaiProperty) -> Tuple[Decimal, Dict[str, Decimal]]:
        """
        Calcula el score ponderado para una propiedad.
        
        Returns:
            Tuple (score_total, score_detalle)
        """
        score_detalle = {}
        score_total = Decimal('0.0')
        
        # 1. Precio vs presupuesto (con moneda)
        score_precio = self._calcular_score_precio(propiedad)
        score_detalle['precio'] = score_precio
        score_total += score_precio * Decimal(str(self.PESOS['precio'])) / 100
        
        # 2. Área construida
        score_area = self._calcular_score_area(propiedad)
        score_detalle['area'] = score_area
        score_total += score_area * Decimal(str(self.PESOS['area'])) / 100
        
        # 3. Habitaciones
        score_habitaciones = self._calcular_score_habitaciones(propiedad)
        score_detalle['habitaciones'] = score_habitaciones
        score_total += score_habitaciones * Decimal(str(self.PESOS['habitaciones'])) / 100
        
        # 4. Baños
        score_banos = self._calcular_score_banos(propiedad)
        score_detalle['banos'] = score_banos
        score_total += score_banos * Decimal(str(self.PESOS['banos'])) / 100
        
        # 5. Antigüedad
        score_antiguedad = self._calcular_score_antiguedad(propiedad)
        score_detalle['antiguedad'] = score_antiguedad
        score_total += score_antiguedad * Decimal(str(self.PESOS['antiguedad'])) / 100
        
        # 6. Distrito (ya pasó el filtro, score extra si es el preferido)
        score_distrito = self._calcular_score_distrito(propiedad)
        score_detalle['distrito'] = score_distrito
        score_total += score_distrito * Decimal(str(self.PESOS['distrito'])) / 100
        
        # 7. Amenities (vs características extra del requerimiento)
        score_amenities = self._calcular_score_amenities(propiedad)
        score_detalle['amenities'] = score_amenities
        score_total += score_amenities * Decimal(str(self.PESOS['amenities'])) / 100
        
        # 8. Ascensor
        score_ascensor = self._calcular_score_ascensor(propiedad)
        score_detalle['ascensor'] = score_ascensor
        score_total += score_ascensor * Decimal(str(self.PESOS['ascensor'])) / 100
        
        # 9. Tipo de propiedad (score extra si coincide exactamente)
        score_tipo = self._calcular_score_tipo_propiedad(propiedad)
        score_detalle['tipo_propiedad'] = score_tipo
        score_total += score_tipo * Decimal(str(self.PESOS['tipo_propiedad'])) / 100
        
        # Convertir a porcentaje (0-100)
        score_total = score_total * Decimal('100.0')
        
        # Asegurar que el score esté entre 0 y 100
        score_total = max(Decimal('0.0'), min(Decimal('100.0'), score_total))
        
        return score_total, score_detalle
    
    def _calcular_score_precio(self, propiedad: PropifaiProperty) -> Decimal:
        """
        Calcula score para precio vs presupuesto con soporte de moneda REAL.
        
        Convierte TANTO el presupuesto como el precio a una moneda común (PEN)
        antes de comparar, usando currency_id real de la propiedad.
        
        Mientras más cerca del presupuesto, mayor score.
        """
        if not self.requerimiento.presupuesto_monto or not propiedad.price:
            return Decimal('0.5')
        
        presupuesto = Decimal(str(self.requerimiento.presupuesto_monto))
        precio = Decimal(str(propiedad.price))
        
        # Obtener monedas reales
        moneda_req = (self.requerimiento.presupuesto_moneda or 'PEN').upper()
        moneda_prop = self._get_moneda_propiedad(propiedad)
        
        # Convertir AMBOS a PEN para comparación justa
        presupuesto_pen = self._convertir_a_moneda_comun(presupuesto, moneda_req, 'PEN')
        precio_pen = self._convertir_a_moneda_comun(precio, moneda_prop, 'PEN')
        
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
    
    def _calcular_score_area(self, propiedad: PropifaiProperty) -> Decimal:
        """
        Calcula score para área construida vs área deseada.
        """
        if not self.requerimiento.area_m2 or not propiedad.built_area:
            return Decimal('0.5')
        
        area_deseada = Decimal(str(self.requerimiento.area_m2))
        area_propiedad = Decimal(str(propiedad.built_area))
        
        if area_propiedad == 0:
            return Decimal('0.0')
        
        diferencia_porcentual = abs(area_propiedad - area_deseada) / area_deseada
        
        if diferencia_porcentual <= self.TOLERANCIA_NUMERICA:
            return Decimal('1.0')
        
        if diferencia_porcentual > 0.5:
            return Decimal('0.0')
        
        tolerancia_decimal = Decimal(str(self.TOLERANCIA_NUMERICA))
        return Decimal('1.0') - (diferencia_porcentual - tolerancia_decimal) / Decimal('0.4')
    
    def _calcular_score_habitaciones(self, propiedad: PropifaiProperty) -> Decimal:
        """Calcula score para número de habitaciones."""
        if not self.requerimiento.habitaciones or not propiedad.bedrooms:
            return Decimal('0.5')
        
        habitaciones_deseadas = self.requerimiento.habitaciones
        habitaciones_propiedad = propiedad.bedrooms
        
        if habitaciones_propiedad >= habitaciones_deseadas:
            return Decimal('1.0')
        else:
            diferencia = habitaciones_deseadas - habitaciones_propiedad
            if diferencia >= 3:
                return Decimal('0.0')
            return Decimal('1.0') - Decimal(str(diferencia)) / Decimal('3.0')
    
    def _calcular_score_banos(self, propiedad: PropifaiProperty) -> Decimal:
        """Calcula score para número de baños."""
        if not self.requerimiento.banos or not propiedad.bathrooms:
            return Decimal('0.5')
        
        banos_deseados = self.requerimiento.banos
        banos_propiedad = propiedad.bathrooms
        
        if banos_propiedad >= banos_deseados:
            return Decimal('1.0')
        else:
            diferencia = banos_deseados - banos_propiedad
            if diferencia >= 2:
                return Decimal('0.0')
            return Decimal('1.0') - Decimal(str(diferencia)) / Decimal('2.0')
    
    def _calcular_score_antiguedad(self, propiedad: PropifaiProperty) -> Decimal:
        """Calcula score para antigüedad de la propiedad."""
        if not propiedad.antiquity_years:
            return Decimal('0.5')
        
        antiguedad = propiedad.antiquity_years
        
        if antiguedad <= 5:
            return Decimal('1.0')
        elif antiguedad <= 15:
            return Decimal('0.7')
        elif antiguedad <= 30:
            return Decimal('0.4')
        else:
            return Decimal('0.1')
    
    def _calcular_score_distrito(self, propiedad: PropifaiProperty) -> Decimal:
        """
        Calcula score adicional para distrito.
        Ya pasó el filtro discriminatorio, score extra si es el distrito preferido.
        """
        if not self.requerimiento.distritos or not propiedad.district:
            return Decimal('0.5')
        
        distritos_requerimiento = self.requerimiento.distritos_lista
        distrito_prop_str = str(propiedad.district).strip()
        
        # El primer distrito en la lista podría ser el preferido
        if distritos_requerimiento:
            primer_distrito = distritos_requerimiento[0].strip().lower()
            id_primer_distrito = _get_distrito_id(primer_distrito)
            if id_primer_distrito and id_primer_distrito == distrito_prop_str:
                return Decimal('1.0')  # Distrito preferido
        
        return Decimal('0.8')  # Distrito aceptable
    
    def _calcular_score_amenities(self, propiedad: PropifaiProperty) -> Decimal:
        """
        Calcula score para amenities vs características extra del requerimiento.
        
        Usa matching de palabras clave entre:
        - propiedad.amenities (texto libre con amenidades)
        - requerimiento.caracteristicas_extra (texto libre con características deseadas)
        """
        score = Decimal('0.5')  # Score base neutral
        
        if not propiedad.amenities or not self.requerimiento.caracteristicas_extra:
            return score
        
        amenities_prop = propiedad.amenities.lower()
        extras_req = self.requerimiento.caracteristicas_extra.lower()
        
        # Palabras clave a buscar en amenities
        palabras_clave = extras_req.replace(',', ' ').split()
        palabras_clave = [p.strip() for p in palabras_clave if len(p.strip()) > 2]
        
        if not palabras_clave:
            return score
        
        coincidencias = sum(1 for palabra in palabras_clave if palabra in amenities_prop)
        ratio_coincidencias = coincidencias / len(palabras_clave)
        
        # Score proporcional a las coincidencias
        return Decimal('0.5') + Decimal(str(ratio_coincidencias)) * Decimal('0.5')
    
    def _calcular_score_ascensor(self, propiedad: PropifaiProperty) -> Decimal:
        """
        Calcula score para ascensor.
        El requerimiento tiene ascensor como Ternario (si/no/indiferente).
        La propiedad tiene ascensor como CharField (sí/no).
        """
        if self.requerimiento.ascensor == 'indiferente' or not self.requerimiento.ascensor:
            return Decimal('0.5')
        
        if self.requerimiento.ascensor == 'si':
            if propiedad.ascensor and propiedad.ascensor.lower() in ['si', 'sí', 'yes', 'true']:
                return Decimal('1.0')
            return Decimal('0.0')
        elif self.requerimiento.ascensor == 'no':
            if not propiedad.ascensor or propiedad.ascensor.lower() in ['no', 'false']:
                return Decimal('1.0')
            return Decimal('0.0')
        
        return Decimal('0.5')
    
    def _calcular_score_tipo_propiedad(self, propiedad: PropifaiProperty) -> Decimal:
        """
        Score extra si el tipo de propiedad coincide exactamente.
        Ya pasó el filtro discriminatorio, esto da un bonus adicional.
        """
        if not self.requerimiento.tipo_propiedad or not propiedad.property_type_id:
            return Decimal('0.5')
        
        tipo_id_esperado = _get_property_type_id(self.requerimiento.tipo_propiedad)
        if tipo_id_esperado and propiedad.property_type_id == tipo_id_esperado:
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
        """Calcula el score promedio de las propiedades compatibles."""
        if not self.propiedades_compatibles:
            return Decimal('0.0')
        
        total = sum(Decimal(str(r['score_total'])) for r in self.propiedades_compatibles)
        return total / len(self.propiedades_compatibles)
    
    def _obtener_propiedad_top(self) -> Optional[Dict]:
        """Devuelve la propiedad con mayor score."""
        if not self.propiedades_compatibles:
            return None
        
        return max(self.propiedades_compatibles, key=lambda x: x['score_total'])


# ============================================================
# Funciones de conveniencia (compatibles con la API anterior)
# ============================================================

def ejecutar_matching_requerimiento(requerimiento_id: int, propiedades=None) -> Tuple[List[Dict], Dict[str, Any]]:
    """
    Función de conveniencia para ejecutar matching para un requerimiento.
    
    Args:
        requerimiento_id: ID del requerimiento a evaluar.
        propiedades: QuerySet de propiedades (opcional).
        
    Returns:
        Tuple (resultados, estadisticas)
    """
    try:
        requerimiento = Requerimiento.objects.get(id=requerimiento_id)
    except Requerimiento.DoesNotExist:
        raise ValueError(f"Requerimiento con ID {requerimiento_id} no existe.")
    
    engine = MatchingEngine(requerimiento)
    resultados = engine.ejecutar_matching(propiedades)
    estadisticas = engine.obtener_estadisticas()
    
    return resultados, estadisticas


def guardar_resultados_matching(requerimiento_id: int, resultados: List[Dict]) -> List[MatchResult]:
    """
    Guarda los resultados del matching en la base de datos.
    
    Args:
        requerimiento_id: ID del requerimiento.
        resultados: Lista de resultados del matching.
        
    Returns:
        Lista de objetos MatchResult creados.
    """
    from decimal import Decimal
    
    requerimiento = Requerimiento.objects.get(id=requerimiento_id)
    objetos_creados = []
    
    for resultado in resultados:
        # Convertir valores Decimal del score_detalle a float para JSON serializable
        score_detalle = resultado['score_detalle']
        if isinstance(score_detalle, dict):
            score_detalle = {
                k: float(v) if isinstance(v, Decimal) else v
                for k, v in score_detalle.items()
            }
        
        match_result = MatchResult(
            requerimiento=requerimiento,
            propiedad=resultado['propiedad'],
            score_total=resultado['score_total'],
            score_detalle=score_detalle,
            fase_eliminada=resultado['fase_eliminada'],
            porcentaje_compatibilidad=resultado['porcentaje_compatibilidad'],
            ranking=resultado.get('ranking'),
        )
        match_result.save()
        objetos_creados.append(match_result)
    
    return objetos_creados


# Funciones para matching masivo (batch)
def ejecutar_matching_masivo(requerimientos=None, propiedades=None, limite_por_requerimiento=10):
    """
    Ejecuta matching para múltiples requerimientos de forma optimizada.
    Los resultados se guardan en la tabla MatchResult para persistencia.
    
    Args:
        requerimientos: QuerySet de requerimientos (si None, todos)
        propiedades: QuerySet de propiedades (si None, todas activas)
        limite_por_requerimiento: Máximo de propiedades a retornar por requerimiento
        
    Returns:
        Dict con resultados por requerimiento
    """
    from django.utils import timezone
    
    if requerimientos is None:
        requerimientos = Requerimiento.objects.all().order_by('-fecha', '-hora')[:2000]
    
    if propiedades is None:
        propiedades = PropifaiProperty.objects.filter(is_active=True)[:1000]
    
    resultados_masivo = {}
    
    for requerimiento in requerimientos:
        engine = MatchingEngine(requerimiento)
        resultados = engine.ejecutar_matching(propiedades)
        
        # Guardar resultados en MatchResult para persistencia
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
            
            mejor_propiedad = {
                'id': mejor_resultado['propiedad'].id,
                'code': mejor_resultado['propiedad'].code,
                'title': mejor_resultado['propiedad'].title,
                'district': mejor_resultado['propiedad'].district,
                'district_name': mejor_resultado['propiedad'].distrito_nombre,
                'price': float(mejor_resultado['propiedad'].price) if mejor_resultado['propiedad'].price else None,
                'currency_id': mejor_resultado['propiedad'].currency_id,
                'property_type': mejor_resultado['propiedad'].tipo_propiedad,
            }
        else:
            mejor_score = 0.0
            score_promedio = 0.0
            mejor_propiedad = None
        
        resultados_masivo[requerimiento.id] = {
            'requerimiento_id': requerimiento.id,
            'requerimiento_nombre': str(requerimiento),
            'porcentaje_match': float(mejor_score),
            'score_promedio': float(score_promedio),
            'total_compatibles': total_compatibles,
            'mejor_propiedad_id': mejor_propiedad['id'] if mejor_propiedad else None,
            'mejor_propiedad_codigo': mejor_propiedad['code'] if mejor_propiedad else None,
            'mejor_propiedad_titulo': mejor_propiedad['title'] if mejor_propiedad else None,
            'mejor_propiedad_distrito': mejor_propiedad['district_name'] if mejor_propiedad else None,
            'mejor_propiedad_precio': mejor_propiedad['price'] if mejor_propiedad else None,
            'mejor_propiedad_moneda_id': mejor_propiedad['currency_id'] if mejor_propiedad else None,
            'mejor_propiedad_tipo': mejor_propiedad['property_type'] if mejor_propiedad else None,
            'fecha_ultimo_matching': timezone.now().isoformat(),
        }
    
    return resultados_masivo


def _obtener_desde_cache(limite=500):
    """
    Lee los resultados de matching desde la tabla MatchResult.
    Es rápido porque no ejecuta el motor de matching.
    Los resultados persisten aunque se reinicie el servidor.
    
    Args:
        limite: Número máximo de requerimientos a retornar.
        
    Returns:
        Lista de diccionarios con resumen de matching por requerimiento.
    """
    from django.db.models import Max
    
    # Obtener el último ejecutado_en por requerimiento, ordenado por score
    ultimos = MatchResult.objects.values(
        'requerimiento_id'
    ).annotate(
        ultimo_ejecutado=Max('ejecutado_en'),
        max_score=Max('score_total')
    ).order_by('-max_score')[:limite]
    
    resumen = []
    for item in ultimos:
        req_id = item['requerimiento_id']
        try:
            req = Requerimiento.objects.get(id=req_id)
        except Requerimiento.DoesNotExist:
            continue
        
        # Obtener el mejor match de ese batch
        mejor = MatchResult.objects.filter(
            requerimiento_id=req_id,
            ejecutado_en=item['ultimo_ejecutado']
        ).order_by('-score_total').first()
        
        if mejor:
            precio = float(mejor.propiedad.price) if mejor.propiedad and mejor.propiedad.price else None
            currency_id = mejor.propiedad.currency_id if mejor.propiedad else None
            
            resumen.append({
                'requerimiento_id': req_id,
                'requerimiento_nombre': str(req),
                'porcentaje_match': float(mejor.score_total),
                'score_promedio': float(mejor.score_total),
                'total_compatibles': 1,
                'mejor_propiedad_id': mejor.propiedad_id,
                'mejor_propiedad_codigo': mejor.propiedad.code if mejor.propiedad else None,
                'mejor_propiedad_titulo': mejor.propiedad.title if mejor.propiedad else None,
                'mejor_propiedad_distrito': mejor.propiedad.district if mejor.propiedad else None,
                'mejor_propiedad_precio': precio,
                'mejor_propiedad_moneda_id': currency_id,
                'mejor_propiedad_tipo': None,
                'fecha_ultimo_matching': mejor.ejecutado_en.isoformat() if mejor.ejecutado_en else None,
            })
    
    resumen.sort(key=lambda x: x['porcentaje_match'], reverse=True)
    return resumen[:limite]


def obtener_resumen_matching_masivo(limite=500):
    """
    Obtiene un resumen rápido del matching masivo.
    Primero intenta leer desde MatchResult (resultados guardados).
    Solo ejecuta matching si no hay resultados guardados o hay propiedades nuevas.
    
    Args:
        limite: Número máximo de requerimientos a procesar.
        
    Returns:
        Lista de diccionarios con resumen de matching por requerimiento.
    """
    try:
        from django.db.models import Max
        
        # 1. Verificar si hay resultados guardados en MatchResult
        ultimo_matching = MatchResult.objects.aggregate(
            max_ejecutado=Max('ejecutado_en')
        )['max_ejecutado']
        
        # 2. Verificar si hay propiedades más nuevas que el último matching
        hay_propiedades_nuevas = False
        if ultimo_matching:
            ultima_propiedad = PropifaiProperty.objects.aggregate(
                max_updated=Max('updated_at')
            )['max_updated']
            if ultima_propiedad and ultima_propiedad > ultimo_matching:
                hay_propiedades_nuevas = True
        
        # 3. Decidir: usar resultados guardados o recalcular
        if ultimo_matching and not hay_propiedades_nuevas:
            # Leer desde MatchResult (rápido, no ejecuta matching)
            return _obtener_desde_cache(limite)
        else:
            # Recalcular y guardar (lento pero necesario)
            resultados = ejecutar_matching_masivo()
            resumen = list(resultados.values())
            resumen.sort(key=lambda x: x['porcentaje_match'], reverse=True)
            return resumen[:limite]
            
    except Exception as e:
        logger.error(f"Error al obtener resumen de matching masivo: {e}")
        return []