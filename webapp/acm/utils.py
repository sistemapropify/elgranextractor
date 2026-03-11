import math
from typing import Optional, Dict, Any


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calcula la distancia en metros entre dos coordenadas usando la fórmula de Haversine.
    """
    # Radio de la Tierra en metros
    R = 6371000
    
    # Convertir grados a radianes
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    # Fórmula de Haversine
    a = math.sin(delta_phi / 2) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c


def calcular_precio_m2(propiedad) -> Dict[str, Optional[float]]:
    """
    Calcula el precio por metro cuadrado según el tipo de propiedad.
    
    Para Terreno: precio / metros_terreno
    Para Casa/Departamento/Oficina: precio / metros_construccion
    
    Retorna un diccionario con:
    - precio_m2: basado en precio_usd (precio de lista)
    - precio_m2_final: basado en precio_final_venta (si existe)
    """
    precio = propiedad.precio_usd
    precio_final = propiedad.precio_final_venta
    
    # Determinar metros a usar según tipo
    tipo = (propiedad.tipo_propiedad or '').lower()
    
    if 'terreno' in tipo:
        metros = propiedad.area_terreno
    else:
        metros = propiedad.area_construida
    
    resultado = {'precio_m2': None, 'precio_m2_final': None}
    
    if precio and metros:
        try:
            resultado['precio_m2'] = float(precio) / float(metros)
        except (ValueError, TypeError, ZeroDivisionError):
            pass
    
    if precio_final and metros:
        try:
            resultado['precio_m2_final'] = float(precio_final) / float(metros)
        except (ValueError, TypeError, ZeroDivisionError):
            pass
    
    return resultado


def calcular_promedio_ponderado(propiedades_seleccionadas: list) -> Dict[str, Any]:
    """
    Calcula estadísticas ponderadas por distancia para propiedades seleccionadas.
    
    Args:
        propiedades_seleccionadas: Lista de diccionarios con 'precio_m2' y 'distancia_metros'
    
    Returns:
        Diccionario con:
        - min: precio_m2 mínimo
        - max: precio_m2 máximo
        - promedio_simple: promedio aritmético
        - promedio_ponderado: ponderado por distancia (1/(distancia+1))
        - total: número de propiedades
    """
    if not propiedades_seleccionadas:
        return {
            'min': 0,
            'max': 0,
            'promedio_simple': 0,
            'promedio_ponderado': 0,
            'total': 0,
        }
    
    precios_m2 = []
    pesos = []
    
    for prop in propiedades_seleccionadas:
        precio = prop.get('precio_m2')
        distancia = prop.get('distancia_metros', 0)
        
        if precio is not None and precio > 0:
            precios_m2.append(precio)
            # Peso inversamente proporcional a la distancia
            peso = 1 / (distancia + 1)  # +1 para evitar división por cero
            pesos.append(peso)
    
    if not precios_m2:
        return {
            'min': 0,
            'max': 0,
            'promedio_simple': 0,
            'promedio_ponderado': 0,
            'total': 0,
        }
    
    min_precio = min(precios_m2)
    max_precio = max(precios_m2)
    promedio_simple = sum(precios_m2) / len(precios_m2)
    
    # Promedio ponderado
    if sum(pesos) > 0:
        promedio_ponderado = sum(p * w for p, w in zip(precios_m2, pesos)) / sum(pesos)
    else:
        promedio_ponderado = promedio_simple
    
    return {
        'min': round(min_precio, 2),
        'max': round(max_precio, 2),
        'promedio_simple': round(promedio_simple, 2),
        'promedio_ponderado': round(promedio_ponderado, 2),
        'total': len(propiedades_seleccionadas),
    }


def estimar_valor_propiedad(metros: float, precio_m2_min: float, precio_m2_max: float) -> Dict[str, float]:
    """
    Estima el valor de una propiedad basado en un rango de precio/m².
    
    Args:
        metros: Metros cuadrados a valuar
        precio_m2_min: Precio por m² mínimo del mercado
        precio_m2_max: Precio por m² máximo del mercado
    
    Returns:
        Diccionario con valor_minimo y valor_maximo
    """
    valor_minimo = metros * precio_m2_min if metros and precio_m2_min else 0
    valor_maximo = metros * precio_m2_max if metros and precio_m2_max else 0
    
    return {
        'valor_minimo': round(valor_minimo, 2),
        'valor_maximo': round(valor_maximo, 2),
    }