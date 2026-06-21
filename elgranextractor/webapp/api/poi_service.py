"""
Servicio de Puntos de Interés (POI) y cálculo de cercanía.
Proporciona la lógica de negocio para:
- Cálculo de distancia Haversine entre coordenadas
- Búsqueda de POIs cercanos a una propiedad
- Exportación de capas en formato GeoJSON
- Resolución de coordenadas desde property_id
"""
import math
from decimal import Decimal
from typing import Optional

from django.db.models import Q, QuerySet

from .models import CategoriaPOI, PointOfInterest


# ──────────────────────────────────────────────
#  CÁLCULO HAVERSINE
# ──────────────────────────────────────────────

def haversine(
    lat1: float, lon1: float,
    lat2: float, lon2: float
) -> float:
    """
    Calcula la distancia en metros entre dos coordenadas geográficas
    usando la fórmula de Haversine.
    """
    R = 6371000  # Radio de la Tierra en metros

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


# ──────────────────────────────────────────────
#  RESOLUCIÓN DE COORDENADAS
# ──────────────────────────────────────────────

def resolver_coordenadas(property_id: int) -> Optional[tuple[float, float]]:
    """
    Resuelve las coordenadas de una propiedad a partir de su ID.
    Busca primero en PropiedadRaw (ingestas) y luego en PropifaiProperty (propifai).
    Retorna (lat, lng) o None si no se encuentra.
    """
    # Intentar en PropiedadRaw (ingestas)
    try:
        from ingestas.models import PropiedadRaw
        prop = PropiedadRaw.objects.get(id=property_id)
        lat = prop.lat
        lng = prop.lng
        if lat is not None and lng is not None:
            return (float(lat), float(lng))
    except (ImportError, LookupError, ValueError, TypeError):
        pass

    # Intentar en PropifaiProperty (propifai)
    try:
        from propifai.models import PropifaiProperty
        prop = PropifaiProperty.objects.get(id=property_id)
        lat = prop.latitude
        lng = prop.longitude
        if lat is not None and lng is not None:
            return (float(lat), float(lng))
    except (ImportError, LookupError, ValueError, TypeError):
        pass

    return None


# ──────────────────────────────────────────────
#  POI MANAGER
# ──────────────────────────────────────────────

class POIManager:
    """
    Gestor principal de Puntos de Interés.
    Encapsula todas las operaciones de consulta y exportación.
    """

    @staticmethod
    def get_capas_activas() -> QuerySet:
        """Retorna todas las categorías/capas activas ordenadas."""
        return CategoriaPOI.objects.filter(is_active=True)

    @staticmethod
    def get_pois_activos() -> QuerySet:
        """Retorna todos los POIs activos con sus categorías precargadas."""
        return PointOfInterest.objects.filter(
            is_active=True,
            categoria__is_active=True
        ).select_related('categoria')

    @staticmethod
    def get_pois_por_capa(capa_slug: str) -> QuerySet:
        """Retorna los POIs activos de una capa específica."""
        return PointOfInterest.objects.filter(
            is_active=True,
            categoria__is_active=True,
            categoria__slug=capa_slug
        ).select_related('categoria')

    # ── Búsqueda de cercanía ──

    def buscar_cercanos(
        self,
        lat: float,
        lng: float,
        radio_metros: float = 500,
        capas: Optional[list[str]] = None,
    ) -> dict:
        """
        Busca POIs cercanos a una coordenada dentro de un radio.
        
        Args:
            lat: Latitud del punto de origen
            lng: Longitud del punto de origen
            radio_metros: Radio de búsqueda en metros (default: 500)
            capas: Lista de slugs de capas a filtrar (None = todas las activas)
        
        Returns:
            Dict con:
            - origen: {lat, lng}
            - radio_metros: float
            - capas: dict {capa_slug: {capa_info, puntos: [...]}}
            - total_puntos: int
        """
        # Obtener POIs base
        pois = self.get_pois_activos()

        # Filtrar por capas si se especificaron
        if capas:
            pois = pois.filter(categoria__slug__in=capas)

        # Calcular distancia para cada POI y filtrar por radio
        resultados = []
        for poi in pois:
            distancia = haversine(
                lat, lng,
                float(poi.latitud), float(poi.longitud)
            )
            if distancia <= radio_metros:
                resultados.append({
                    'id': poi.id,
                    'nombre': poi.nombre,
                    'latitud': float(poi.latitud),
                    'longitud': float(poi.longitud),
                    'distancia_metros': round(distancia, 1),
                    'distancia_texto': self._formatear_distancia(distancia),
                    'direccion': poi.direccion,
                    'descripcion': poi.descripcion,
                    'telefono': poi.telefono,
                    'sitio_web': poi.sitio_web,
                    'categoria_slug': poi.categoria.slug,
                    'categoria_nombre': poi.categoria.nombre,
                    'categoria_icono': poi.categoria.icono,
                    'categoria_color': poi.categoria.color,
                })

        # Agrupar por capa
        capas_dict: dict = {}
        for r in resultados:
            slug = r['categoria_slug']
            if slug not in capas_dict:
                capas_dict[slug] = {
                    'slug': slug,
                    'nombre': r['categoria_nombre'],
                    'icono': r['categoria_icono'],
                    'color': r['categoria_color'],
                    'puntos': [],
                }
            capas_dict[slug]['puntos'].append(r)

        return {
            'origen': {'lat': lat, 'lng': lng},
            'radio_metros': radio_metros,
            'capas': capas_dict,
            'total_puntos': len(resultados),
        }

    # ── Exportación GeoJSON ──

    def generar_geojson(
        self,
        capa_slug: Optional[str] = None
    ) -> dict:
        """
        Genera un GeoJSON FeatureCollection con los POIs.
        
        Args:
            capa_slug: Si se especifica, solo exporta esa capa.
                       Si es None, exporta todas las capas activas.
        
        Returns:
            Dict en formato GeoJSON FeatureCollection
        """
        if capa_slug:
            pois = self.get_pois_por_capa(capa_slug)
        else:
            pois = self.get_pois_activos()

        features = []
        for poi in pois:
            feature = {
                'type': 'Feature',
                'geometry': {
                    'type': 'Point',
                    'coordinates': [
                        float(poi.longitud),
                        float(poi.latitud),
                    ],
                },
                'properties': {
                    'id': poi.id,
                    'nombre': poi.nombre,
                    'categoria_slug': poi.categoria.slug,
                    'categoria_nombre': poi.categoria.nombre,
                    'categoria_icono': poi.categoria.icono,
                    'categoria_color': poi.categoria.color,
                    'direccion': poi.direccion,
                    'descripcion': poi.descripcion,
                    'telefono': poi.telefono,
                    'sitio_web': poi.sitio_web,
                },
            }
            features.append(feature)

        return {
            'type': 'FeatureCollection',
            'features': features,
        }

    # ── Utilidades ──

    @staticmethod
    def _formatear_distancia(metros: float) -> str:
        """Formatea una distancia en metros a texto legible."""
        if metros < 1000:
            return f"{int(round(metros))} m"
        else:
            km = metros / 1000
            return f"{km:.1f} km"
