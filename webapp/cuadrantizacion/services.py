"""
Servicios y lógica de negocio para el sistema de cuadrantización inmobiliaria.
"""
import math
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
from django.db.models import Avg, StdDev, Count, Q
from django.utils import timezone

from .models import ZonaValor, PropiedadValoracion, EstadisticaZona
from ingestas.models import PropiedadRaw


def punto_en_poligono(lat: float, lng: float, poligono: List[List[float]]) -> bool:
    """
    Determina si un punto (lat, lng) está dentro de un polígono.
    Implementa el algoritmo del punto en polígono (ray casting).
    
    Args:
        lat: Latitud del punto
        lng: Longitud del punto
        poligono: Lista de puntos [[lat1, lng1], [lat2, lng2], ...]
    
    Returns:
        True si el punto está dentro del polígono, False en caso contrario.
    """
    if not poligono or len(poligono) < 3:
        return False
    
    # Asegurar que el polígono esté cerrado (primer y último punto iguales)
    if poligono[0] != poligono[-1]:
        poligono = poligono + [poligono[0]]
    
    inside = False
    n = len(poligono)
    
    for i in range(n - 1):
        lat1, lng1 = poligono[i]
        lat2, lng2 = poligono[i + 1]
        
        # Verificar si el punto está en el borde
        if (lat == lat1 and lng == lng1) or (lat == lat2 and lng == lng2):
            return True
        
        # Verificar intersección
        if ((lng1 > lng) != (lng2 > lng)) and \
           (lat < (lat2 - lat1) * (lng - lng1) / (lng2 - lng1) + lat1):
            inside = not inside
    
    return inside


def calcular_area_poligono(coordenadas: List[List[float]]) -> Optional[Decimal]:
    """
    Calcula el área de un polígono en metros cuadrados usando la fórmula del área de Gauss.
    Asume coordenadas en grados decimales y calcula área aproximada en la superficie terrestre.
    
    Args:
        coordenadas: Lista de puntos [[lat, lng], ...]
    
    Returns:
        Área en metros cuadrados o None si no se puede calcular.
    """
    if len(coordenadas) < 3:
        return None
    
    # Radio de la Tierra en metros
    R = 6371000
    
    # Convertir coordenadas a radianes
    coords_rad = []
    for lat, lng in coordenadas:
        lat_rad = math.radians(lat)
        lng_rad = math.radians(lng)
        coords_rad.append((lat_rad, lng_rad))
    
    # Asegurar polígono cerrado
    if coords_rad[0] != coords_rad[-1]:
        coords_rad.append(coords_rad[0])
    
    # Calcular área esférica usando fórmula de l'Huilier
    area = 0.0
    n = len(coords_rad)
    
    for i in range(n - 1):
        lat1, lng1 = coords_rad[i]
        lat2, lng2 = coords_rad[i + 1]
        
        area += (lng2 - lng1) * (2 + math.sin(lat1) + math.sin(lat2))
    
    area = abs(area * R * R / 2.0)
    
    return Decimal(round(area, 2))


def encontrar_zona_por_punto(lat: float, lng: float) -> Optional[ZonaValor]:
    """
    Encuentra la zona de valor que contiene un punto dado.
    
    Args:
        lat: Latitud del punto
        lng: Longitud del punto
    
    Returns:
        ZonaValor que contiene el punto, o None si no se encuentra.
    """
    zonas = ZonaValor.objects.filter(activo=True)
    
    for zona in zonas:
        if punto_en_poligono(lat, lng, zona.coordenadas):
            return zona
    
    return None


def calcular_precio_m2_zona(propiedades, tipo_especifico: Optional[str] = None) -> Dict:
    """
    Calcula el precio por m² promedio de una zona usando propiedades comparables.
    
    Args:
        propiedades: QuerySet de PropiedadRaw
        tipo_especifico: Tipo de propiedad a filtrar (opcional)
    
    Returns:
        Diccionario con precio promedio, cantidad utilizada y método.
    """
    # Filtrar por tipo si se especifica
    if tipo_especifico:
        propiedades_filtradas = propiedades.filter(tipo_propiedad=tipo_especifico)
    else:
        propiedades_filtradas = propiedades
    
    # Si hay menos de 3 propiedades, ampliar búsqueda
    if propiedades_filtradas.count() < 3:
        # Incluir propiedades de tipos similares con factor de ajuste
        propiedades_filtradas = propiedades.all()
        metodo = 'con_ajuste_tipos'
        
        # Asignar factores de ajuste por tipo
        factores_ajuste = {
            'casa': 1.0,
            'departamento': 0.9,
            'terreno': 1.2,
            'local': 1.3,
            'oficina': 1.1,
            'otro': 1.0
        }
    else:
        metodo = 'directo'
    
    # Calcular precio m² con pesos (propiedades más nuevas pesan más)
    suma_ponderada = Decimal('0.0')
    suma_pesos = Decimal('0.0')
    precios_m2 = []
    
    for propiedad in propiedades_filtradas:
        # Obtener precio y metros cuadrados
        precio = propiedad.precio_usd
        metros = propiedad.area_construida or propiedad.area_terreno
        
        if not precio or not metros or metros <= 0:
            continue
        
        precio_m2 = precio / metros
        
        # Calcular peso basado en antigüedad (propiedades más nuevas pesan más)
        antiguedad = 0
        if propiedad.antiguedad and isinstance(propiedad.antiguedad, (int, float)):
            antiguedad = float(propiedad.antiguedad)
        
        peso = Decimal(1.0 / (1.0 + antiguedad / 10.0))
        
        # Aplicar factor de ajuste por tipo si es necesario
        factor_ajuste = Decimal('1.0')
        if metodo == 'con_ajuste_tipos':
            factor_ajuste = Decimal(str(factores_ajuste.get(propiedad.tipo_propiedad or 'otro', 1.0)))
        
        suma_ponderada += Decimal(str(precio_m2)) * Decimal(str(peso)) * factor_ajuste
        suma_pesos += Decimal(str(peso))
        precios_m2.append(float(precio_m2))
    
    if suma_pesos == 0:
        return {
            'precio_promedio': None,
            'cantidad_utilizada': 0,
            'metodo': metodo,
            'desviacion_estandar': None
        }
    
    precio_promedio = suma_ponderada / suma_pesos
    
    # Calcular desviación estándar si hay suficientes datos
    desviacion_estandar = None
    if len(precios_m2) >= 2:
        media = sum(precios_m2) / len(precios_m2)
        varianza = sum((x - media) ** 2 for x in precios_m2) / len(precios_m2)
        desviacion_estandar = Decimal(math.sqrt(varianza))
    
    return {
        'precio_promedio': precio_promedio,
        'cantidad_utilizada': len(precios_m2),
        'metodo': metodo,
        'desviacion_estandar': desviacion_estandar
    }


def estimar_precio_propiedad(
    zona: ZonaValor,
    metros_cuadrados: Decimal,
    habitaciones: int = 0,
    banos: int = 0,
    antiguedad: int = 0,
    tipo_propiedad: str = 'casa',
    propiedades_comparables=None
) -> Dict:
    """
    Estima el precio de una propiedad basado en características y zona.
    
    Args:
        zona: ZonaValor donde se encuentra la propiedad
        metros_cuadrados: Metros cuadrados de la propiedad
        habitaciones: Número de habitaciones
        banos: Número de baños
        antiguedad: Antigüedad en años
        tipo_propiedad: Tipo de propiedad
        propiedades_comparables: Propiedades comparables para cálculo
    
    Returns:
        Diccionario con precio estimado y detalles.
    """
    # Obtener precio base por m² de la zona
    precio_base_m2 = zona.precio_promedio_m2 or Decimal('1000.0')
    
    # Coeficientes de ajuste (valores empíricos)
    coeficientes = {
        'habitaciones': Decimal('0.05'),  # 5% por habitación adicional
        'banos': Decimal('0.03'),         # 3% por baño adicional
        'antiguedad': Decimal('-0.02'),   # -2% por año de antigüedad
    }
    
    # Factores por tipo de propiedad
    factores_tipo = {
        'casa': Decimal('1.0'),
        'departamento': Decimal('0.95'),
        'terreno': Decimal('1.1'),
        'local': Decimal('1.3'),
        'oficina': Decimal('1.2'),
        'otro': Decimal('1.0')
    }
    
    # Calcular ajustes
    ajuste_habitaciones = coeficientes['habitaciones'] * (habitaciones - 3)  # Base 3 habitaciones
    ajuste_banos = coeficientes['banos'] * (banos - 2)  # Base 2 baños
    ajuste_antiguedad = coeficientes['antiguedad'] * antiguedad
    factor_tipo = factores_tipo.get(tipo_propiedad, Decimal('1.0'))
    
    # Calcular precio estimado
    precio_estimado_m2 = precio_base_m2 * (
        Decimal('1.0') + ajuste_habitaciones + ajuste_banos + ajuste_antiguedad
    ) * factor_tipo
    
    precio_estimado_total = precio_estimado_m2 * metros_cuadrados
    
    # Calcular rango de confianza
    if propiedades_comparables:
        n_comparables = propiedades_comparables.count()
        nivel_confianza = min(Decimal('0.95'), Decimal(n_comparables) / Decimal('20.0'))
    else:
        n_comparables = 0
        nivel_confianza = Decimal('0.7')
    
    # Rango de +/- 10% ajustado por confianza
    margen_error = Decimal('0.1') * (Decimal('1.0') - nivel_confianza + Decimal('0.3'))
    rango_min = precio_estimado_total * (Decimal('1.0') - margen_error)
    rango_max = precio_estimado_total * (Decimal('1.0') + margen_error)
    
    return {
        'precio_estimado': precio_estimado_total,
        'rango_min': rango_min,
        'rango_max': rango_max,
        'nivel_confianza': float(nivel_confianza),
        'zona': zona.nombre_zona,
        'comparables_utilizados': n_comparables,
        'precio_base_m2': float(precio_base_m2),
        'detalles': {
            'precio_m2_estimado': float(precio_estimado_m2),
            'ajuste_habitaciones': float(ajuste_habitaciones),
            'ajuste_banos': float(ajuste_banos),
            'ajuste_antiguedad': float(ajuste_antiguedad),
            'factor_tipo': float(factor_tipo),
            'margen_error': float(margen_error)
        }
    }


def actualizar_estadisticas_zona(zona: ZonaValor) -> None:
    """
    Actualiza todas las estadísticas de una zona.
    
    Args:
        zona: ZonaValor a actualizar
    """
    # Obtener propiedades dentro de la zona
    propiedades = PropiedadRaw.objects.all()  # Filtrar por zona cuando tengamos la relación
    
    # Calcular estadísticas generales
    resultado = calcular_precio_m2_zona(propiedades)
    
    zona.precio_promedio_m2 = resultado['precio_promedio']
    zona.desviacion_estandar_m2 = resultado['desviacion_estandar']
    zona.cantidad_propiedades_analizadas = resultado['cantidad_utilizada']
    
    # Calcular área si no está calculada
    if not zona.area_total:
        area = calcular_area_poligono(zona.coordenadas)
        if area:
            zona.area_total = area
    
    zona.save()
    
    # Actualizar estadísticas por tipo
    tipos = ['casa', 'departamento', 'terreno', 'local', 'oficina', 'otro']
    
    for tipo in tipos:
        estadistica, created = EstadisticaZona.objects.get_or_create(
            zona=zona,
            tipo_propiedad=tipo
        )
        
        # Calcular estadísticas para este tipo
        propiedades_tipo = propiedades.filter(tipo_propiedad=tipo)
        
        if propiedades_tipo.exists():
            # Calcular promedios
            estadistica.cantidad_propiedades = propiedades_tipo.count()
            
            # Aquí se podrían calcular más estadísticas
            # Por ahora, usamos valores por defecto
            estadistica.precio_promedio_m2 = resultado['precio_promedio']
            estadistica.save()
    
    # Crear registro en historial
    from .models import HistorialPrecioZona
    HistorialPrecioZona.objects.create(
        zona=zona,
        fecha_registro=timezone.now().date(),
        precio_promedio_m2=resultado['precio_promedio'] or Decimal('0.0'),
        cantidad_propiedades=resultado['cantidad_utilizada'],
        desviacion_estandar=resultado['desviacion_estandar'],
        fuente_datos='cálculo_automático'
    )


def detectar_outliers(propiedades, desviaciones: int = 2) -> Tuple[List, List]:
    """
    Detecta outliers en una lista de propiedades basado en precio por m².
    
    Args:
        propiedades: QuerySet de PropiedadRaw
        desviaciones: Número de desviaciones estándar para considerar outlier
    
    Returns:
        Tuple con (propiedades_normales, propiedades_outliers)
    """
    # Calcular precio m² para cada propiedad
    precios_m2 = []
    propiedades_con_precio = []
    
    for propiedad in propiedades:
        precio = propiedad.precio_usd
        metros = propiedad.area_construida or propiedad.area_terreno
        
        if precio and metros and metros > 0:
            precio_m2 = float(precio / metros)
            precios_m2.append(precio_m2)
            propiedades_con_precio.append((propiedad, precio_m2))
    
    if len(precios_m2) < 2:
        return propiedades_con_precio, []
    
    # Calcular media y desviación estándar
    media = sum(precios_m2) / len(precios_m2)
    varianza = sum((x - media) ** 2 for x in precios_m2) / len(precios_m2)
    desviacion = math.sqrt(varianza)
    
    # Separar outliers
    normales = []
    outliers = []
    
    limite_inferior = media - desviaciones * desviacion
    limite_superior = media + desviaciones * desviacion
    
    for propiedad, precio_m2 in propiedades_con_precio:
        if limite_inferior <= precio_m2 <= limite_superior:
            normales.append(propiedad)
        else:
            outliers.append(propiedad)
    
    return normales, outliers


# ============================================================================
# FUNCIONES DE JERARQUÍA Y NIVELES
# ============================================================================

def obtener_zonas_por_nivel(nivel: str, activas: bool = True) -> List[ZonaValor]:
    """
    Obtiene todas las zonas de un nivel específico.
    
    Args:
        nivel: Código del nivel ('pais', 'departamento', 'provincia', 'distrito', 'zona', 'subzona')
        activas: Si True, solo devuelve zonas activas
    
    Returns:
        Lista de ZonaValor del nivel especificado
    """
    queryset = ZonaValor.objects.filter(nivel=nivel)
    if activas:
        queryset = queryset.filter(activo=True)
    
    return queryset.order_by('nombre_zona')


def obtener_jerarquia_completa(zona: ZonaValor) -> Dict:
    """
    Obtiene la jerarquía completa de una zona (ancestros y descendientes).
    
    Args:
        zona: ZonaValor de referencia
    
    Returns:
        Diccionario con estructura jerárquica completa
    """
    # Obtener ancestros
    ancestros = []
    current = zona.parent
    while current:
        ancestros.insert(0, current)
        current = current.parent
    
    # Obtener descendientes (recursivo)
    def obtener_descendientes(z):
        descendientes = []
        for hijo in z.children.all():
            descendientes.append({
                'zona': hijo,
                'descendientes': obtener_descendientes(hijo)
            })
        return descendientes
    
    descendientes = obtener_descendientes(zona)
    
    return {
        'zona_actual': zona,
        'ancestros': ancestros,
        'descendientes': descendientes,
        'ruta_jerarquica': zona.get_hierarchy_display(),
        'nivel_actual': zona.get_nivel_display()
    }


def calcular_estadisticas_jerarquicas(zona: ZonaValor, incluir_descendientes: bool = True) -> Dict:
    """
    Calcula estadísticas agregadas para una zona, incluyendo sus subzonas si se especifica.
    
    Args:
        zona: ZonaValor de referencia
        incluir_descendientes: Si True, incluye estadísticas de todas las subzonas
    
    Returns:
        Diccionario con estadísticas agregadas
    """
    from .models import PropiedadValoracion
    
    # Obtener propiedades de la zona actual
    propiedades_zona = PropiedadValoracion.objects.filter(zona=zona, es_comparable=True)
    
    if incluir_descendientes:
        # Obtener todas las subzonas
        subzonas = zona.get_descendants()
        
        # Obtener propiedades de todas las subzonas
        propiedades_subzonas = PropiedadValoracion.objects.filter(
            zona__in=subzonas,
            es_comparable=True
        )
        
        # Combinar propiedades
        todas_propiedades = propiedades_zona | propiedades_subzonas
    else:
        todas_propiedades = propiedades_zona
        subzonas = []
    
    # Calcular estadísticas
    cantidad_propiedades = todas_propiedades.count()
    
    if cantidad_propiedades == 0:
        return {
            'zona': zona.nombre_zona,
            'nivel': zona.nivel,
            'cantidad_propiedades': 0,
            'precio_promedio_m2': None,
            'precio_minimo_m2': None,
            'precio_maximo_m2': None,
            'desviacion_estandar': None,
            'subzonas_incluidas': len(subzonas) if incluir_descendientes else 0,
            'incluye_descendientes': incluir_descendientes
        }
    
    # Calcular precios
    precios_m2 = []
    for valoracion in todas_propiedades:
        if valoracion.precio_m2:
            precios_m2.append(float(valoracion.precio_m2))
    
    if not precios_m2:
        return {
            'zona': zona.nombre_zona,
            'nivel': zona.nivel,
            'cantidad_propiedades': cantidad_propiedades,
            'precio_promedio_m2': None,
            'precio_minimo_m2': None,
            'precio_maximo_m2': None,
            'desviacion_estandar': None,
            'subzonas_incluidas': len(subzonas) if incluir_descendientes else 0,
            'incluye_descendientes': incluir_descendientes
        }
    
    precio_promedio = sum(precios_m2) / len(precios_m2)
    precio_minimo = min(precios_m2)
    precio_maximo = max(precios_m2)
    
    # Calcular desviación estándar
    if len(precios_m2) >= 2:
        media = precio_promedio
        varianza = sum((x - media) ** 2 for x in precios_m2) / len(precios_m2)
        desviacion_estandar = math.sqrt(varianza)
    else:
        desviacion_estandar = 0.0
    
    return {
        'zona': zona.nombre_zona,
        'nivel': zona.nivel,
        'cantidad_propiedades': cantidad_propiedades,
        'precio_promedio_m2': precio_promedio,
        'precio_minimo_m2': precio_minimo,
        'precio_maximo_m2': precio_maximo,
        'desviacion_estandar': desviacion_estandar,
        'subzonas_incluidas': len(subzonas) if incluir_descendientes else 0,
        'incluye_descendientes': incluir_descendientes
    }


def encontrar_zona_por_jerarquia(lat: float, lng: float, nivel_deseado: str = None) -> Optional[ZonaValor]:
    """
    Encuentra la zona que contiene un punto, opcionalmente filtrando por nivel.
    
    Args:
        lat: Latitud del punto
        lng: Longitud del punto
        nivel_deseado: Nivel específico a buscar (ej: 'distrito', 'zona')
    
    Returns:
        ZonaValor que contiene el punto, o None si no se encuentra
    """
    # Encontrar todas las zonas que contienen el punto
    zonas_contienen = []
    zonas = ZonaValor.objects.filter(activo=True)
    
    for zona in zonas:
        if punto_en_poligono(lat, lng, zona.coordenadas):
            zonas_contienen.append(zona)
    
    if not zonas_contienen:
        return None
    
    # Si se especifica nivel, filtrar por él
    if nivel_deseado:
        zonas_nivel = [z for z in zonas_contienen if z.nivel == nivel_deseado]
        if zonas_nivel:
            # Si hay múltiples zonas del mismo nivel, devolver la primera
            return zonas_nivel[0]
    
    # Ordenar por nivel (de más específico a más general)
    niveles_orden = {nivel: i for i, (nivel, _) in enumerate(ZonaValor.NIVELES)}
    zonas_contienen.sort(key=lambda z: niveles_orden.get(z.nivel, 99), reverse=True)
    
    # Devolver la zona más específica
    return zonas_contienen[0] if zonas_contienen else None


def crear_estructura_jerarquica(
    nombre: str,
    nivel: str,
    coordenadas: List[List[float]],
    parent: ZonaValor = None,
    codigo: str = None
) -> ZonaValor:
    """
    Crea una nueva zona con estructura jerárquica.
    
    Args:
        nombre: Nombre de la zona
        nivel: Nivel jerárquico
        coordenadas: Coordenadas del polígono
        parent: Zona padre (opcional)
        codigo: Código único (opcional)
    
    Returns:
        ZonaValor creada
    """
    # Validar nivel
    niveles_validos = [n[0] for n in ZonaValor.NIVELES]
    if nivel not in niveles_validos:
        raise ValueError(f"Nivel '{nivel}' no válido. Válidos: {niveles_validos}")
    
    # Crear zona
    zona = ZonaValor.objects.create(
        nombre_zona=nombre,
        nivel=nivel,
        coordenadas=coordenadas,
        parent=parent,
        codigo=codigo,
        activo=True
    )
    
    # Calcular área automáticamente
    area = calcular_area_poligono(coordenadas)
    if area:
        zona.area_total = area
        zona.save()
    
    return zona


def actualizar_estadisticas_jerarquicas(zona: ZonaValor) -> None:
    """
    Actualiza estadísticas de una zona y todas sus subzonas.
    
    Args:
        zona: ZonaValor raíz
    """
    # Actualizar estadísticas de la zona actual
    actualizar_estadisticas_zona(zona)
    
    # Actualizar estadísticas de todas las subzonas (recursivo)
    for subzona in zona.children.all():
        actualizar_estadisticas_jerarquicas(subzona)