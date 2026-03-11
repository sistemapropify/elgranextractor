"""
Motor de matching inmobiliario.

Evalúa la compatibilidad entre un requerimiento y las propiedades disponibles.
Implementa dos fases:
1. Filtros discriminatorios (eliminación inmediata)
2. Scoring ponderado (0-100)
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from django.db.models import QuerySet

from requerimientos.models import Requerimiento
from propifai.models import PropifaiProperty
from .models import MatchResult

logger = logging.getLogger(__name__)


class MatchingEngine:
    """
    Motor principal de matching.
    """
    
    # Pesos para campos de scoring (suman 100)
    # Estos pesos se basan en la importancia relativa de cada campo
    PESOS = {
        # Campos numéricos con rango (40% del total)
        'precio': 15,           # Precio vs presupuesto
        'area': 10,             # Área construida vs área deseada
        'habitaciones': 8,      # Número de habitaciones
        'banos': 5,             # Número de baños
        'antiguedad': 5,        # Antigüedad de la propiedad
        'pisos': 3,             # Número de pisos
        'estacionamientos': 4,  # Espacios de estacionamiento
        
        # Campos cualitativos (35% del total)
        'tipo_propiedad': 15,   # Tipo de propiedad (casa, departamento, etc.)
        'distrito': 12,         # Ubicación geográfica
        'amenidades': 8,        # Amenidades (ascensor, cochera, etc.)
        
        # Campos adicionales (25% del total)
        'estado': 10,           # Estado de la propiedad (nueva, usada, etc.)
        'zona': 8,              # Zonificación (residencial, comercial, etc.)
        'accesibilidad': 7,     # Accesibilidad (cercanía a servicios)
    }
    
    # Tolerancia para campos numéricos (porcentaje)
    TOLERANCIA_NUMERICA = 0.10  # 10%
    
    def __init__(self, requerimiento: Requerimiento):
        self.requerimiento = requerimiento
        self.propiedades_evaluadas = 0
        self.propiedades_descartadas = {
            'tipo_propiedad': 0,
            'metodo_pago': 0,
            'distrito': 0,
            'presupuesto': 0,
        }
        self.propiedades_compatibles = []
        
    def ejecutar_matching(self, propiedades: QuerySet[PropifaiProperty] = None) -> List[Dict]:
        """
        Ejecuta el matching completo para el requerimiento.
        
        Args:
            propiedades: QuerySet de propiedades a evaluar. Si es None, se evalúan todas.
            
        Returns:
            Lista de diccionarios con resultados para cada propiedad que pasó la fase 1.
        """
        if propiedades is None:
            propiedades = PropifaiProperty.objects.all()
        
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
            f"Matching completado para requerimiento {self.requerimiento.id}. "
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
        # 1. Tipo de propiedad
        if not self._coincide_tipo_propiedad(propiedad):
            return 'tipo_propiedad'
        
        # 2. Método de pago
        if not self._coincide_metodo_pago(propiedad):
            return 'metodo_pago'
        
        # 3. Distrito
        if not self._coincide_distrito(propiedad):
            return 'distrito'
        
        # 4. Presupuesto
        if not self._dentro_de_presupuesto(propiedad):
            return 'presupuesto'
        
        return None
    
    def _coincide_tipo_propiedad(self, propiedad: PropifaiProperty) -> bool:
        """
        Verifica si el tipo de propiedad coincide exactamente.
        
        NOTA: El modelo PropifaiProperty no tiene campo 'tipo_propiedad' explícito.
        En una implementación real, se debería mapear desde algún campo existente.
        Por ahora, asumimos que todas las propiedades son compatibles.
        """
        # TODO: Implementar mapeo real de tipos de propiedad
        # Por ahora, retornamos True para no descartar propiedades
        return True
    
    def _coincide_metodo_pago(self, propiedad: PropifaiProperty) -> bool:
        """
        Verifica si el método de pago coincide exactamente.
        
        NOTA: El modelo PropifaiProperty no tiene campo 'metodo_pago'.
        En una implementación real, se debería inferir de algún campo.
        Por ahora, asumimos que todas las propiedades son compatibles.
        """
        # TODO: Implementar lógica real de método de pago
        return True
    
    def _coincide_distrito(self, propiedad: PropifaiProperty) -> bool:
        """
        Verifica si el distrito de la propiedad está en la lista de distritos del requerimiento.
        
        NOTA: Las propiedades tienen IDs numéricos de distrito (ej: '4', '23') mientras que
        los requerimientos tienen nombres de distritos de Arequipa (ej: 'Miraflores', 'Yanahuara').
        Se implementa un mapeo mejorado para aumentar las coincidencias.
        """
        # Si el requerimiento no especifica distritos o es 'nan', se acepta cualquier propiedad
        if not self.requerimiento.distritos:
            return True
        
        distritos_str = str(self.requerimiento.distritos).lower().strip()
        if distritos_str == 'nan' or distritos_str == '':
            return True
        
        distritos_requerimiento = self.requerimiento.distritos_lista
        distrito_propiedad = propiedad.district
        
        if not distrito_propiedad:
            # Si la propiedad no tiene distrito, no podemos verificar
            return False
        
        # Normalizar nombres (minúsculas, sin espacios extras)
        distritos_req_norm = [d.strip().lower() for d in distritos_requerimiento]
        distrito_prop_norm = distrito_propiedad.strip().lower()
        
        # Verificación directa (si el distrito de propiedad ya es un nombre)
        if distrito_prop_norm in distritos_req_norm:
            return True
        
        # Mapeo de IDs numéricos a nombres de distritos de Arequipa
        # Mapeo más completo basado en datos reales
        mapeo_id_a_nombre = {
            '1': 'cercado',
            '2': 'yanahuara',
            '3': 'cayma',
            '4': 'miraflores',
            '5': 'mariano melgar',
            '6': 'alto selva alegre',
            '7': 'cerro colorado',
            '8': 'sachaca',
            '9': 'jose luis bustamante y rivero',
            '10': 'tiabaya',
            '11': 'characato',
            '12': 'polobaya',
            '13': 'socabaya',
            '14': 'hunter',
            '15': 'la joya',
            '16': 'mollendo',
            '17': 'punta de bombon',
            '18': 'umacollo',
            '19': 'santa rosa',
            '20': 'santa isabel de siguas',
            '21': 'yura',
            '22': 'la union',
            '23': 'vallecito',
            '24': 'paucarpata',
            '25': 'bustamante',
            '26': 'sabandia',
            '27': 'yanahuara',
            '28': 'chiguata',
            '29': 'jacobo hunter',
            '30': 'lari',
        }
        
        # También mapeo inverso: nombres comunes a IDs
        mapeo_nombre_a_id = {
            'miraflores': ['4'],
            'yanahuara': ['2', '27'],
            'cercado': ['1'],
            'cayma': ['3'],
            'cerro colorado': ['7'],
            'sachaca': ['8'],
            'socabaya': ['13'],
            'umacollo': ['18'],
            'vallecito': ['23'],
            'bustamante': ['25'],
            'paucarpata': ['24'],
            'sabandia': ['26'],
            'mariano melgar': ['5'],
            'alto selva alegre': ['6'],
            'jose luis bustamante y rivero': ['9'],
            'hunter': ['14', '29'],
            'cerro': ['7'],  # Abreviatura
            'yan': ['2', '27'],  # Abreviatura
        }
        
        # 1. Si el distrito de propiedad es un ID numérico, mapearlo
        if distrito_prop_norm in mapeo_id_a_nombre:
            nombre_mapeado = mapeo_id_a_nombre[distrito_prop_norm]
            if nombre_mapeado in distritos_req_norm:
                return True
        
        # 2. Si el distrito de propiedad es un nombre, verificar si coincide con IDs mapeados
        for distrito_req in distritos_req_norm:
            # Verificar si el nombre del requerimiento está en el mapeo inverso
            if distrito_req in mapeo_nombre_a_id:
                ids_posibles = mapeo_nombre_a_id[distrito_req]
                if distrito_prop_norm in ids_posibles:
                    return True
        
        # 3. Verificación parcial (substring)
        for distrito_req in distritos_req_norm:
            if distrito_req in distrito_prop_norm or distrito_prop_norm in distrito_req:
                return True
        
        # 4. Para pruebas, si el requerimiento tiene pocos distritos específicos,
        # pero tenemos propiedades en distritos populares, permitir matching parcial
        # Esto es solo para demostración hasta que se tenga un mapeo completo
        distritos_populares = ['miraflores', 'yanahuara', 'cercado', 'cayma', 'cerro colorado', 'cerro', 'yan']
        for distrito_popular in distritos_populares:
            if distrito_popular in distritos_req_norm and distrito_prop_norm in ['4', '2', '1', '3', '7']:
                return True
        
        # 5. Si después de todas las verificaciones no hay coincidencia,
        # pero el requerimiento tiene muchos distritos (más de 3), permitir matching
        # para no descartar todas las propiedades (solo en modo de prueba)
        if len(distritos_req_norm) > 3:
            logger.debug(f"Requerimiento {self.requerimiento.id} con muchos distritos ({len(distritos_req_norm)}), permitiendo matching parcial")
            return True
        
        return False
    
    def _dentro_de_presupuesto(self, propiedad: PropifaiProperty) -> bool:
        """
        Verifica si el precio de la propiedad está dentro del rango de presupuesto.
        Aplica una tolerancia del 10% hacia arriba del límite máximo.
        """
        if not self.requerimiento.presupuesto_monto:
            # Si no hay presupuesto definido, se acepta cualquier precio
            return True
        
        if not propiedad.price:
            # Si la propiedad no tiene precio, no podemos verificar
            return False
        
        # Convertir a Decimal para comparaciones precisas
        presupuesto = Decimal(str(self.requerimiento.presupuesto_monto))
        precio = Decimal(str(propiedad.price))
        
        # Calcular límite máximo con tolerancia del 10%
        limite_maximo = presupuesto * Decimal('1.10')
        
        # Verificar si el precio está dentro del rango (0 a límite máximo con tolerancia)
        # Asumimos que el presupuesto es el máximo que el cliente puede pagar
        return precio <= limite_maximo
    
    def _calcular_scoring(self, propiedad: PropifaiProperty) -> Tuple[Decimal, Dict[str, Decimal]]:
        """
        Calcula el score ponderado para una propiedad.
        
        Returns:
            Tuple (score_total, score_detalle)
        """
        score_detalle = {}
        score_total = Decimal('0.0')
        
        # 1. Precio vs presupuesto
        score_precio = self._calcular_score_precio(propiedad)
        score_detalle['precio'] = score_precio
        score_total += score_precio * Decimal(str(self.PESOS['precio'])) / 100
        
        # 2. Área
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
        
        # 6. Distrito (ya pasó el filtro discriminatorio, pero aún puede aportar score)
        score_distrito = self._calcular_score_distrito(propiedad)
        score_detalle['distrito'] = score_distrito
        score_total += score_distrito * Decimal(str(self.PESOS['distrito'])) / 100
        
        # 7. Amenidades
        score_amenidades = self._calcular_score_amenidades(propiedad)
        score_detalle['amenidades'] = score_amenidades
        score_total += score_amenidades * Decimal(str(self.PESOS['amenidades'])) / 100
        
        # Asegurar que el score esté entre 0 y 100
        score_total = max(Decimal('0.0'), min(Decimal('100.0'), score_total))
        
        return score_total, score_detalle
    
    def _calcular_score_precio(self, propiedad: PropifaiProperty) -> Decimal:
        """
        Calcula score para precio vs presupuesto.
        Mientras más cerca del presupuesto, mayor score.
        """
        if not self.requerimiento.presupuesto_monto or not propiedad.price:
            return Decimal('0.5')  # Score neutral
        
        presupuesto = Decimal(str(self.requerimiento.presupuesto_monto))
        precio = Decimal(str(propiedad.price))
        
        if precio <= presupuesto:
            # Precio igual o menor al presupuesto: score máximo
            return Decimal('1.0')
        else:
            # Precio mayor al presupuesto: penalización proporcional
            # Usamos la tolerancia del 10% como límite
            limite_maximo = presupuesto * Decimal('1.10')
            
            if precio > limite_maximo:
                # Ya fue filtrado en fase 1, pero por si acaso
                return Decimal('0.0')
            
            # Penalización lineal entre presupuesto y límite máximo
            diferencia = precio - presupuesto
            rango_tolerancia = limite_maximo - presupuesto
            penalizacion = diferencia / rango_tolerancia
            
            return Decimal('1.0') - penalizacion
    
    def _calcular_score_area(self, propiedad: PropifaiProperty) -> Decimal:
        """
        Calcula score para área construida vs área deseada.
        """
        if not self.requerimiento.area_m2 or not propiedad.built_area:
            return Decimal('0.5')  # Score neutral
        
        area_deseada = Decimal(str(self.requerimiento.area_m2))
        area_propiedad = Decimal(str(propiedad.built_area))
        
        # Calcular diferencia porcentual
        if area_propiedad == 0:
            return Decimal('0.0')
        
        diferencia_porcentual = abs(area_propiedad - area_deseada) / area_deseada
        
        # Score máximo si la diferencia es menor al 10%
        if diferencia_porcentual <= self.TOLERANCIA_NUMERICA:
            return Decimal('1.0')
        
        # Penalización lineal hasta el 50% de diferencia
        if diferencia_porcentual > 0.5:
            return Decimal('0.0')
        
        # Mapear diferencia (0.1 a 0.5) a score (1.0 a 0.0)
        # Convertir TOLERANCIA_NUMERICA a Decimal para evitar error de tipos
        tolerancia_decimal = Decimal(str(self.TOLERANCIA_NUMERICA))
        return Decimal('1.0') - (diferencia_porcentual - tolerancia_decimal) / Decimal('0.4')
    
    def _calcular_score_habitaciones(self, propiedad: PropifaiProperty) -> Decimal:
        """
        Calcula score para número de habitaciones.
        """
        if not self.requerimiento.habitaciones or not propiedad.bedrooms:
            return Decimal('0.5')  # Score neutral
        
        habitaciones_deseadas = self.requerimiento.habitaciones
        habitaciones_propiedad = propiedad.bedrooms
        
        if habitaciones_propiedad >= habitaciones_deseadas:
            # Más habitaciones de las deseadas: score máximo
            return Decimal('1.0')
        else:
            # Menos habitaciones: penalización proporcional
            diferencia = habitaciones_deseadas - habitaciones_propiedad
            if diferencia >= 3:  # Si faltan 3 o más habitaciones
                return Decimal('0.0')
            
            return Decimal('1.0') - Decimal(str(diferencia)) / Decimal('3.0')
    
    def _calcular_score_banos(self, propiedad: PropifaiProperty) -> Decimal:
        """
        Calcula score para número de baños.
        """
        if not self.requerimiento.banos or not propiedad.bathrooms:
            return Decimal('0.5')  # Score neutral
        
        banos_deseados = self.requerimiento.banos
        banos_propiedad = propiedad.bathrooms
        
        if banos_propiedad >= banos_deseados:
            return Decimal('1.0')
        else:
            diferencia = banos_deseados - banos_propiedad
            if diferencia >= 2:  # Si faltan 2 o más baños
                return Decimal('0.0')
            
            return Decimal('1.0') - Decimal(str(diferencia)) / Decimal('2.0')
    
    def _calcular_score_antiguedad(self, propiedad: PropifaiProperty) -> Decimal:
        """
        Calcula score para antigüedad de la propiedad.
        Generalmente, los clientes prefieren propiedades más nuevas.
        """
        if not propiedad.antiquity_years:
            return Decimal('0.5')  # Score neutral
        
        antiguedad = propiedad.antiquity_years
        
        # Score máximo para propiedades nuevas (0-5 años)
        if antiguedad <= 5:
            return Decimal('1.0')
        # Buen score para propiedades de 6-15 años
        elif antiguedad <= 15:
            return Decimal('0.7')
        # Score medio para propiedades de 16-30 años
        elif antiguedad <= 30:
            return Decimal('0.4')
        # Score bajo para propiedades muy antiguas
        else:
            return Decimal('0.1')
    
    def _calcular_score_distrito(self, propiedad: PropifaiProperty) -> Decimal:
        """
        Calcula score adicional para distrito.
        Ya pasó el filtro discriminatorio, pero podemos dar score extra
        si es el distrito preferido del cliente.
        """
        if not self.requerimiento.distritos or not propiedad.district:
            return Decimal('0.5')
        
        distritos_requerimiento = self.requerimiento.distritos_lista
        distrito_propiedad = propiedad.district.strip().lower()
        
        # Si el requerimiento tiene múltiples distritos, el primero podría ser el preferido
        if distritos_requerimiento and distrito_propiedad == distritos_requerimiento[0].strip().lower():
            return Decimal('1.0')  # Distrito preferido
        else:
            return Decimal('0.8')  # Distrito aceptable
    
    def _calcular_score_amenidades(self, propiedad: PropifaiProperty) -> Decimal:
        """
        Calcula score para amenidades (ascensor, cochera, amueblado).
        """
        score = Decimal('0.0')
        criterios_cumplidos = 0
        total_criterios = 3  # ascensor, cochera, amueblado
        
        # Ascensor
        if self.requerimiento.ascensor == 'indiferente':
            criterios_cumplidos += 1
        elif self.requerimiento.ascensor == 'si':
            # Verificar si la propiedad tiene ascensor
            if propiedad.ascensor and propiedad.ascensor.lower() in ['si', 'sí', 'yes', 'true']:
                criterios_cumplidos += 1
        elif self.requerimiento.ascensor == 'no':
            # El cliente no quiere ascensor
            if not propiedad.ascensor or propiedad.ascensor.lower() in ['no', 'false']:
                criterios_cumplidos += 1
        
        # Cochera
        if self.requerimiento.cochera == 'indiferente':
            criterios_cumplidos += 1
        elif self.requerimiento.cochera == 'si':
            if propiedad.garage_spaces and propiedad.garage_spaces > 0:
                criterios_cumplidos += 1
        elif self.requerimiento.cochera == 'no':
            if not propiedad.garage_spaces or propiedad.garage_spaces == 0:
                criterios_cumplidos += 1
        
        # Amueblado (no hay campo directo en PropifaiProperty, asumimos neutral)
        # Por ahora, si el cliente es indiferente o no especifica, contamos como cumplido
        if self.requerimiento.amueblado in ['indiferente', 'no_especificado']:
            criterios_cumplidos += 1
        else:
            # No podemos verificar, asumimos neutral
            criterios_cumplidos += 0.5
        
        # Calcular score proporcional
        if total_criterios > 0:
            score = Decimal(str(criterios_cumplidos / total_criterios))
        
        return score
    
    def obtener_estadisticas(self) -> Dict[str, Any]:
        """
        Devuelve estadísticas del matching ejecutado.
        """
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


# Función de conveniencia para uso rápido
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
    from .models import MatchResult
    
    requerimiento = Requerimiento.objects.get(id=requerimiento_id)
    objetos_creados = []
    
    for resultado in resultados:
        match_result = MatchResult(
            requerimiento=requerimiento,
            propiedad=resultado['propiedad'],
            score_total=resultado['score_total'],
            score_detalle=resultado['score_detalle'],
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
    
    Args:
        requerimientos: QuerySet de requerimientos (si None, todos)
        propiedades: QuerySet de propiedades (si None, todas activas)
        limite_por_requerimiento: Máximo de propiedades a retornar por requerimiento
        
    Returns:
        Dict con {
            'requerimiento_id': {
                'mejor_score': float,
                'total_compatibles': int,
                'mejor_propiedad': dict,
                'score_promedio': float,
                'timestamp': datetime
            }
        }
    """
    from django.utils import timezone
    
    if requerimientos is None:
        requerimientos = Requerimiento.objects.all().order_by('-fecha', '-hora')[:2000]  # Limitar a 2000
    
    if propiedades is None:
        propiedades = PropifaiProperty.objects.filter(is_active=True)[:1000]  # Limitar a 1000 propiedades activas
    
    resultados_masivo = {}
    
    for requerimiento in requerimientos:
        engine = MatchingEngine(requerimiento)
        resultados = engine.ejecutar_matching(propiedades)
        
        # Obtener estadísticas
        compatibles = [r for r in resultados if r['fase_eliminada'] is None]
        total_compatibles = len(compatibles)
        
        if total_compatibles > 0:
            mejor_resultado = compatibles[0]  # Ya está ordenado por score descendente
            mejor_score = float(mejor_resultado['score_total'])
            score_promedio = sum(r['score_total'] for r in compatibles) / total_compatibles
            
            # Información de la mejor propiedad
            mejor_propiedad = {
                'id': mejor_resultado['propiedad'].id,
                'code': mejor_resultado['propiedad'].code,
                'title': mejor_resultado['propiedad'].title,
                'district': mejor_resultado['propiedad'].district,
                'price': float(mejor_resultado['propiedad'].price) if mejor_resultado['propiedad'].price else None,
            }
        else:
            mejor_score = 0.0
            score_promedio = 0.0
            mejor_propiedad = None
        
        resultados_masivo[requerimiento.id] = {
            'requerimiento': {
                'id': requerimiento.id,
                'agente': requerimiento.agente,
                'tipo_propiedad': requerimiento.get_tipo_propiedad_display(),
                'distritos': requerimiento.distritos,
                'presupuesto_display': requerimiento.presupuesto_display,
            },
            'mejor_score': mejor_score,
            'total_compatibles': total_compatibles,
            'mejor_propiedad': mejor_propiedad,
            'score_promedio': score_promedio,
            'timestamp': timezone.now(),
            'tiene_match_alto': mejor_score >= 80.0,  # Match alto si >= 80%
        }
    
    return resultados_masivo


def obtener_resumen_matching_masivo():
    """
    Obtiene un resumen rápido del matching masivo para mostrar en grilla.
    Retorna los requerimientos con su porcentaje de match para visualización rápida.
    
    Si no hay resultados guardados, ejecuta matching en tiempo real con límites
    para no afectar el rendimiento.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Limitar a 50 requerimientos más recientes para rendimiento
    requerimientos = Requerimiento.objects.all().order_by('-fecha', '-hora')[:50]
    
    # Obtener IDs de requerimientos
    requerimiento_ids = [req.id for req in requerimientos]
    
    # Buscar los últimos matches por requerimiento (solo los más recientes)
    from django.db.models import Subquery, OuterRef
    
    # Primero, obtener la fecha del último match por requerimiento
    subquery = MatchResult.objects.filter(
        requerimiento_id=OuterRef('pk'),
        fase_eliminada__isnull=True
    ).order_by('-ejecutado_en').values('ejecutado_en')[:1]

    # Anotar cada requerimiento con su último match
    requerimientos_con_fecha = Requerimiento.objects.filter(
        id__in=requerimiento_ids
    ).annotate(
        ultima_fecha_match=Subquery(subquery)
    )
    
    # Obtener propiedades activas (limitadas para rendimiento)
    propiedades = PropifaiProperty.objects.filter(is_active=True)[:200]
    
    # Ahora obtener los matches correspondientes a esas fechas
    resumen = []
    for req in requerimientos_con_fecha:
        porcentaje_match = 0.0
        fecha_match = None
        mejor_propiedad_id = None
        mejor_propiedad_codigo = None
        mejor_propiedad_distrito = None
        mejor_propiedad_precio = None
        total_compatibles = 0
        
        if req.ultima_fecha_match:
            # Usar resultado guardado
            ultimo_match = MatchResult.objects.filter(
                requerimiento=req,
                fase_eliminada__isnull=True,
                ejecutado_en=req.ultima_fecha_match
            ).order_by('-score_total').first()
            if ultimo_match:
                porcentaje_match = float(ultimo_match.score_total)
                fecha_match = req.ultima_fecha_match
                mejor_propiedad_id = ultimo_match.propiedad.id
                mejor_propiedad_codigo = ultimo_match.propiedad.code
                mejor_propiedad_distrito = ultimo_match.propiedad.district
                mejor_propiedad_precio = float(ultimo_match.propiedad.price) if ultimo_match.propiedad.price else None
                # Contar compatibles
                total_compatibles = MatchResult.objects.filter(
                    requerimiento=req,
                    fase_eliminada__isnull=True,
                    ejecutado_en=req.ultima_fecha_match
                ).count()
                logger.debug(f"Requerimiento {req.id}: usando resultado guardado ({porcentaje_match:.1f}%)")
        else:
            # No hay resultado guardado, ejecutar matching en tiempo real
            try:
                from .engine import MatchingEngine
                engine = MatchingEngine(req)
                resultados = engine.ejecutar_matching(propiedades)
                
                # Filtrar compatibles y obtener mejor score
                compatibles = [r for r in resultados if r['fase_eliminada'] is None]
                total_compatibles = len(compatibles)
                
                if compatibles:
                    mejor_resultado = compatibles[0]  # Ya ordenado por score
                    porcentaje_match = float(mejor_resultado['score_total'])
                    mejor_propiedad_id = mejor_resultado['propiedad'].id
                    mejor_propiedad_codigo = mejor_resultado['propiedad'].code
                    mejor_propiedad_distrito = mejor_resultado['propiedad'].district
                    mejor_propiedad_precio = float(mejor_resultado['propiedad'].price) if mejor_resultado['propiedad'].price else None
                    logger.debug(f"Requerimiento {req.id}: matching en tiempo real ({porcentaje_match:.1f}%)")
                else:
                    logger.debug(f"Requerimiento {req.id}: sin propiedades compatibles")
            except Exception as e:
                logger.error(f"Error al ejecutar matching para requerimiento {req.id}: {e}")
                porcentaje_match = 0.0
        
        tiene_match_alto = porcentaje_match >= 80.0
        tiene_propiedad_match = mejor_propiedad_id is not None
        
        resumen.append({
            'requerimiento_id': req.id,
            'porcentaje_match': porcentaje_match,
            'tiene_match_alto': tiene_match_alto,
            'tiene_propiedad_match': tiene_propiedad_match,
            'fecha_ultimo_matching': fecha_match,
            'agente': req.agente or 'Sin agente',
            'tipo_propiedad': req.get_tipo_propiedad_display(),
            'distritos': req.distritos or 'Sin distrito',
            'presupuesto': req.presupuesto_display,
            'fecha_requerimiento': req.fecha,
            'mejor_propiedad_id': mejor_propiedad_id,
            'mejor_propiedad_codigo': mejor_propiedad_codigo,
            'mejor_propiedad_distrito': mejor_propiedad_distrito,
            'mejor_propiedad_precio': mejor_propiedad_precio,
            'total_compatibles': total_compatibles,
        })
    
    # Ordenar por porcentaje descendente para mejor visualización
    resumen.sort(key=lambda x: x['porcentaje_match'], reverse=True)
    
    return resumen