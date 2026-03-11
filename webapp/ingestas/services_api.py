"""
Servicio para consumir API externa de propiedades.
"""
import requests
import json
from django.conf import settings
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class APIExternaService:
    """Servicio para consumir API externa de propiedades"""
    
    def __init__(self, api_url: str = None, api_key: str = None):
        self.api_url = api_url or getattr(settings, 'API_EXTERNA_URL', 'http://localhost/dashboard/api/properties/with-docs/')
        self.api_key = api_key or getattr(settings, 'API_EXTERNA_KEY', 'ItBJSnE6F7gIG5uhnPh0mtXmQ9yjE8ZgqtIjTU')
        self.timeout = getattr(settings, 'API_EXTERNA_TIMEOUT', 10)
    
    def obtener_propiedades(self) -> List[Dict[str, Any]]:
        """
        Obtiene propiedades de la API externa.
        
        Returns:
            Lista de propiedades en formato estandarizado.
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            logger.info(f"Consultando API externa: {self.api_url}")
            response = requests.get(
                self.api_url, 
                headers=headers, 
                timeout=self.timeout,
                verify=False  # Para desarrollo, en producción usar certificados válidos
            )
            
            if response.status_code == 200:
                data = response.json()
                propiedades = self._transformar_datos(data)
                logger.info(f"Obtenidas {len(propiedades)} propiedades de API externa")
                return propiedades
            else:
                logger.error(f"Error en API externa: {response.status_code} - {response.text[:200]}")
                return []
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error de conexión con API externa: {e}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Error decodificando JSON de API externa: {e}")
            return []
        except Exception as e:
            logger.error(f"Error inesperado al obtener propiedades de API externa: {e}")
            return []
    
    def _transformar_datos(self, data: Any) -> List[Dict[str, Any]]:
        """
        Transforma los datos de la API externa al formato estandarizado.
        
        Args:
            data: Datos crudos de la API
            
        Returns:
            Lista de propiedades en formato estandarizado.
        """
        propiedades = []
        
        # Intentar diferentes estructuras comunes de API
        if isinstance(data, dict):
            # Estructura 1: { "results": [ {...}, ... ] }
            if 'results' in data and isinstance(data['results'], list):
                items = data['results']
            # Estructura 2: { "data": [ {...}, ... ] }
            elif 'data' in data and isinstance(data['data'], list):
                items = data['data']
            # Estructura 3: { "properties": [ {...}, ... ] }
            elif 'properties' in data and isinstance(data['properties'], list):
                items = data['properties']
            # Estructura 4: { "items": [ {...}, ... ] }
            elif 'items' in data and isinstance(data['items'], list):
                items = data['items']
            else:
                # Asumir que el dict es una propiedad individual
                items = [data]
        elif isinstance(data, list):
            items = data
        else:
            logger.warning(f"Formato de datos no reconocido: {type(data)}")
            return []
        
        for item in items:
            propiedad = self._mapear_propiedad(item)
            if propiedad:
                propiedades.append(propiedad)
        
        return propiedades
    
    def _mapear_propiedad(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Mapea una propiedad de la API externa al formato interno.
        
        Args:
            item: Propiedad en formato de API externa
            
        Returns:
            Propiedad en formato estandarizado o None si no es válida.
        """
        try:
            # Mapeo de campos comunes
            propiedad = {
                'id_externo': str(item.get('id', item.get('property_id', item.get('codigo', '')))),
                'tipo_propiedad': self._obtener_tipo_propiedad(item),
                'descripcion': item.get('description', item.get('descripcion', item.get('title', ''))),
                'precio_usd': self._obtener_precio(item),
                'departamento': item.get('department', item.get('departamento', item.get('state', ''))),
                'provincia': item.get('province', item.get('provincia', item.get('city', ''))),
                'distrito': item.get('district', item.get('distrito', item.get('locality', ''))),
                'direccion': item.get('address', item.get('direccion', item.get('location', ''))),
                'area_construida': self._obtener_area(item),
                'area_terreno': item.get('land_area', item.get('area_terreno', item.get('plot_size', None))),
                'numero_habitaciones': item.get('bedrooms', item.get('habitaciones', item.get('rooms', None))),
                'numero_banos': item.get('bathrooms', item.get('banos', item.get('baths', None))),
                'estacionamientos': item.get('parking', item.get('estacionamientos', item.get('garage', None))),
                'lat': item.get('latitude', item.get('lat', item.get('geo_lat', None))),
                'lng': item.get('longitude', item.get('lng', item.get('geo_lng', None))),
                'url_propiedad': item.get('url', item.get('property_url', item.get('link', ''))),
                'imagen_principal': self._obtener_imagen_principal(item),
                'fuente_externa': 'API Externa',
                'fecha_publicacion': item.get('publication_date', item.get('fecha_publicacion', item.get('created_at', None))),
                'atributos_extras': self._extraer_atributos_extras(item),
                'es_externo': True,  # Marcar como propiedad externa
            }
            
            # Validar que tenga al menos algunos datos básicos
            if not propiedad['descripcion'] and not propiedad['tipo_propiedad']:
                return None
                
            return propiedad
            
        except Exception as e:
            logger.error(f"Error mapeando propiedad: {e}")
            return None
    
    def _obtener_tipo_propiedad(self, item: Dict[str, Any]) -> str:
        """Extrae el tipo de propiedad"""
        tipo = item.get('property_type', item.get('tipo', item.get('type', '')))
        if not tipo:
            # Intentar inferir de otras claves
            if 'casa' in str(item.get('title', '')).lower() or 'casa' in str(item.get('description', '')).lower():
                return 'Casa'
            elif 'departamento' in str(item.get('title', '')).lower() or 'apartment' in str(item.get('description', '')).lower():
                return 'Departamento'
            elif 'terreno' in str(item.get('title', '')).lower() or 'land' in str(item.get('description', '')).lower():
                return 'Terreno'
            elif 'local' in str(item.get('title', '')).lower() or 'commercial' in str(item.get('description', '')).lower():
                return 'Local Comercial'
        return str(tipo) if tipo else 'Propiedad'
    
    def _obtener_precio(self, item: Dict[str, Any]) -> Optional[float]:
        """Extrae el precio en USD"""
        precio = item.get('price_usd', item.get('precio_usd', item.get('price', None)))
        if precio is None:
            return None
        
        try:
            # Limpiar formato de precio
            if isinstance(precio, str):
                # Remover símbolos de moneda y comas
                precio = precio.replace('$', '').replace(',', '').replace('USD', '').strip()
                # Convertir a float
                return float(precio)
            elif isinstance(precio, (int, float)):
                return float(precio)
        except (ValueError, TypeError):
            pass
        
        return None
    
    def _obtener_area(self, item: Dict[str, Any]) -> Optional[float]:
        """Extrae el área construida"""
        area = item.get('built_area', item.get('area_construida', item.get('area', None)))
        if area is None:
            return None
        
        try:
            if isinstance(area, str):
                # Remover unidades
                area = area.replace('m²', '').replace('m2', '').replace('sqm', '').strip()
                return float(area)
            elif isinstance(area, (int, float)):
                return float(area)
        except (ValueError, TypeError):
            pass
        
        return None
    
    def _obtener_imagen_principal(self, item: Dict[str, Any]) -> Optional[str]:
        """Extrae la URL de la imagen principal"""
        # Buscar en diferentes campos comunes
        campos_imagen = [
            'main_image', 'imagen_principal', 'image_url', 
            'photo', 'foto', 'thumbnail', 'cover_image'
        ]
        
        for campo in campos_imagen:
            if campo in item and item[campo]:
                url = item[campo]
                if isinstance(url, str) and url.startswith(('http://', 'https://')):
                    return url
        
        # Buscar en arrays de imágenes
        if 'images' in item and isinstance(item['images'], list) and item['images']:
            for img in item['images']:
                if isinstance(img, str) and img.startswith(('http://', 'https://')):
                    return img
                elif isinstance(img, dict) and 'url' in img:
                    url = img['url']
                    if isinstance(url, str) and url.startswith(('http://', 'https://')):
                        return url
        
        return None
    
    def _extraer_atributos_extras(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Extrae atributos adicionales que no están en el mapeo estándar"""
        atributos = {}
        
        # Excluir campos ya mapeados
        campos_mapeados = {
            'id', 'property_id', 'codigo', 'property_type', 'tipo', 'type',
            'description', 'descripcion', 'title', 'price_usd', 'precio_usd', 'price',
            'department', 'departamento', 'state', 'province', 'provincia', 'city',
            'district', 'distrito', 'locality', 'address', 'direccion', 'location',
            'built_area', 'area_construida', 'area', 'land_area', 'area_terreno', 'plot_size',
            'bedrooms', 'habitaciones', 'rooms', 'bathrooms', 'banos', 'baths',
            'parking', 'estacionamientos', 'garage', 'latitude', 'lat', 'geo_lat',
            'longitude', 'lng', 'geo_lng', 'url', 'property_url', 'link',
            'main_image', 'imagen_principal', 'image_url', 'photo', 'foto', 'thumbnail',
            'cover_image', 'images', 'publication_date', 'fecha_publicacion', 'created_at'
        }
        
        for key, value in item.items():
            if key not in campos_mapeados and value is not None:
                atributos[key] = value
        
        return atributos


# Instancia global del servicio
api_service = APIExternaService()


def obtener_propiedades_externas() -> List[Dict[str, Any]]:
    """
    Función de conveniencia para obtener propiedades de la API externa.
    
    Returns:
        Lista de propiedades externas en formato estandarizado.
    """
    return api_service.obtener_propiedades()