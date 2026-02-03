"""
Sistema de descubrimiento de URLs para fuentes web de bienes raíces en Arequipa.

Este módulo proporciona funcionalidades para descubrir automáticamente
URLs relevantes de portales inmobiliarios y sitios de clasificados
especializados en bienes raíces en Arequipa, Perú.
"""

import re
import logging
import time
from typing import List, Dict, Any, Optional, Set
from urllib.parse import urljoin, urlparse, parse_qs
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from django.utils import timezone

from .models import FuenteWeb

logger = logging.getLogger(__name__)


class DescubridorURLs:
    """
    Clase principal para descubrir URLs de bienes raíces en Arequipa.
    
    Implementa estrategias de descubrimiento:
    1. Búsqueda en motores de búsqueda
    2. Exploración de sitios conocidos
    3. Extracción de enlaces de páginas existentes
    4. Análisis de sitemaps
    """
    
    def __init__(self, dominio_principal: str = "arequipa"):
        """
        Inicializa el descubridor de URLs.
        
        Args:
            dominio_principal: Dominio principal para filtrar resultados (ej: "arequipa")
        """
        self.dominio_principal = dominio_principal.lower()
        
        # Patrones regex para identificar URLs de bienes raíces
        self.patrones_bienes_raices = [
            r'(?i)(casa|departamento|apartamento|terreno|lote|local|oficina|inmueble)',
            r'(?i)(venta|alquiler|arriendo|renta|compra)',
            r'(?i)(precio|valor|m²|metros|habitaciones|baños|dormitorios)',
        ]
        
        # Dominios conocidos de portales inmobiliarios en Perú
        self.dominios_conocidos = [
            'adondevivir.com',
            'urbania.pe',
            'properati.com.pe',
            'vivanda.com.pe',
            'inmuebles24.com',
            'lamudi.com.pe',
            'goplaceit.com',
            'plusvalia.com',
            'zonaprop.com.pe',
            'mercadolibre.com.pe',
        ]
        
        # Palabras clave específicas para Arequipa
        self.palabras_clave_arequipa = [
            'arequipa',
            'yanahuara',
            'cayma',
            'sachaca',
            'socabaya',
            'tiabaya',
            'paucarpata',
            'cerro colorado',
            'miraflores',
            'jose luis bustamante',
        ]
        
        # Configuración de headers para requests
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
    
    def descubrir_urls_por_busqueda(self, consulta: str, limite: int = 20) -> List[Dict[str, Any]]:
        """
        Descubre URLs realizando búsquedas en motores de búsqueda.
        
        Args:
            consulta: Términos de búsqueda
            limite: Número máximo de resultados a obtener
            
        Returns:
            Lista de URLs descubiertas con metadatos
        """
        logger.info(f"Buscando URLs para consulta: {consulta}")
        
        urls_descubiertas = []
        
        # Construir consultas específicas para Arequipa
        consultas = [
            f"{consulta} arequipa",
            f"{consulta} arequipa perú",
            f"{consulta} en arequipa",
        ]
        
        for consulta_actual in consultas:
            if len(urls_descubiertas) >= limite:
                break
            
            try:
                # Simular búsqueda (en producción se usaría API de Google/Bing)
                resultados = self._simular_busqueda_google(consulta_actual, limite=10)
                
                for resultado in resultados:
                    if self._es_url_relevante(resultado['url']):
                        urls_descubiertas.append({
                            'url': resultado['url'],
                            'titulo': resultado.get('titulo', ''),
                            'descripcion': resultado.get('descripcion', ''),
                            'fuente': 'busqueda_google',
                            'consulta': consulta_actual,
                            'fecha_descubrimiento': timezone.now(),
                        })
                
                time.sleep(1)  # Respeta rate limiting
                
            except Exception as e:
                logger.error(f"Error en búsqueda para '{consulta_actual}': {str(e)}")
        
        logger.info(f"Descubiertas {len(urls_descubiertas)} URLs por búsqueda")
        return urls_descubiertas
    
    def _simular_busqueda_google(self, consulta: str, limite: int = 10) -> List[Dict[str, Any]]:
        """
        Simula una búsqueda en Google (para desarrollo).
        
        En producción, se debería usar la API oficial de Google Search.
        
        Args:
            consulta: Términos de búsqueda
            limite: Número máximo de resultados
            
        Returns:
            Lista de resultados simulados
        """
        # URLs simuladas basadas en consultas comunes
        resultados_simulados = []
        
        # Mapeo de consultas a URLs conocidas
        mapeo_consultas = {
            'casas venta arequipa': [
                {
                    'url': 'https://www.adondevivir.com/casas-venta-arequipa.html',
                    'titulo': 'Casas en Venta en Arequipa - AdondeVivir',
                    'descripcion': 'Encuentra las mejores casas en venta en Arequipa. Amplia selección de propiedades.',
                },
                {
                    'url': 'https://www.urbania.pe/casas-venta-arequipa',
                    'titulo': 'Casas en Venta Arequipa - Urbania',
                    'descripcion': 'Busca y encuentra casas en venta en Arequipa. Filtra por precio, ubicación y más.',
                },
            ],
            'departamentos alquiler arequipa': [
                {
                    'url': 'https://www.properati.com.pe/departamentos-alquiler-arequipa',
                    'titulo': 'Departamentos en Alquiler en Arequipa - Properati',
                    'descripcion': 'Departamentos en alquiler en Arequipa. Encuentra el que mejor se adapte a tus necesidades.',
                },
                {
                    'url': 'https://www.vivanda.com.pe/departamentos-alquiler-arequipa',
                    'titulo': 'Departamentos en Alquiler Arequipa - Vivanda',
                    'descripcion': 'Amplia oferta de departamentos en alquiler en Arequipa.',
                },
            ],
            'terrenos venta arequipa': [
                {
                    'url': 'https://www.inmuebles24.com/terrenos-venta-arequipa',
                    'titulo': 'Terrenos en Venta en Arequipa - Inmuebles24',
                    'descripcion': 'Terrenos en venta en Arequipa. Oportunidades de inversión.',
                },
            ],
        }
        
        # Buscar en el mapeo
        consulta_lower = consulta.lower()
        for clave, urls in mapeo_consultas.items():
            if clave in consulta_lower:
                resultados_simulados.extend(urls[:limite])
                break
        
        # Si no hay resultados en el mapeo, generar algunos genéricos
        if not resultados_simulados:
            for i in range(min(3, limite)):
                resultados_simulados.append({
                    'url': f'https://ejemplo{i}.com/{consulta.lower().replace(" ", "-")}',
                    'titulo': f'Resultado {i+1} para: {consulta}',
                    'descripcion': f'Descripción del resultado {i+1} para la búsqueda: {consulta}',
                })
        
        return resultados_simulados[:limite]
    
    def descubrir_urls_por_exploracion(self, url_base: str, profundidad: int = 2) -> List[Dict[str, Any]]:
        """
        Descubre URLs explorando un sitio web desde una URL base.
        
        Args:
            url_base: URL inicial para comenzar la exploración
            profundidad: Nivel máximo de profundidad para explorar
            
        Returns:
            Lista de URLs descubiertas con metadatos
        """
        logger.info(f"Explorando URLs desde {url_base} (profundidad: {profundidad})")
        
        urls_descubiertas = []
        urls_visitadas = set()
        urls_por_visitar = [(url_base, 0)]  # (url, profundidad_actual)
        
        while urls_por_visitar and len(urls_descubiertas) < 100:
            url_actual, profundidad_actual = urls_por_visitar.pop(0)
            
            if url_actual in urls_visitadas or profundidad_actual > profundidad:
                continue
            
            try:
                # Obtener contenido de la página
                response = requests.get(
                    url_actual,
                    headers=self.headers,
                    timeout=10,
                    allow_redirects=True
                )
                
                if response.status_code != 200:
                    continue
                
                urls_visitadas.add(url_actual)
                
                # Parsear HTML
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extraer todas las URLs de la página
                for link in soup.find_all('a', href=True):
                    href = link.get('href')
                    if not href:
                        continue
                    
                    # Convertir URL relativa a absoluta
                    url_absoluta = urljoin(url_actual, href)
                    
                    # Filtrar URLs no deseadas
                    if not self._es_url_valida(url_absoluta):
                        continue
                    
                    # Verificar si es relevante para bienes raíces
                    if self._es_url_relevante(url_absoluta):
                        titulo = link.get_text(strip=True)[:200] or ''
                        
                        urls_descubiertas.append({
                            'url': url_absoluta,
                            'titulo': titulo,
                            'descripcion': self._extraer_descripcion(link),
                            'fuente': 'exploracion',
                            'url_origen': url_actual,
                            'profundidad': profundidad_actual,
                            'fecha_descubrimiento': timezone.now(),
                        })
                    
                    # Agregar para exploración futura si no es demasiado profundo
                    if profundidad_actual < profundidad:
                        urls_por_visitar.append((url_absoluta, profundidad_actual + 1))
                
                # Respeta rate limiting
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error al explorar {url_actual}: {str(e)}")
                continue
        
        logger.info(f"Descubiertas {len(urls_descubiertas)} URLs por exploración")
        return urls_descubiertas
    
    def descubrir_urls_por_sitemap(self, url_sitemap: str) -> List[Dict[str, Any]]:
        """
        Descubre URLs analizando un sitemap XML.
        
        Args:
            url_sitemap: URL del sitemap XML
            
        Returns:
            Lista de URLs descubiertas con metadatos
        """
        logger.info(f"Analizando sitemap: {url_sitemap}")
        
        urls_descubiertas = []
        
        try:
            response = requests.get(
                url_sitemap,
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code != 200:
                logger.warning(f"No se pudo acceder al sitemap: {url_sitemap}")
                return urls_descubiertas
            
            # Parsear sitemap XML
            soup = BeautifulSoup(response.content, 'xml')
            
            # Buscar URLs en el sitemap
            urls = soup.find_all('url')
            
            for url_tag in urls:
                loc = url_tag.find('loc')
                if not loc or not loc.text:
                    continue
                
                url = loc.text.strip()
                
                if self._es_url_relevante(url):
                    # Extraer metadatos del sitemap
                    lastmod = url_tag.find('lastmod')
                    changefreq = url_tag.find('changefreq')
                    priority = url_tag.find('priority')
                    
                    urls_descubiertas.append({
                        'url': url,
                        'titulo': self._extraer_titulo_desde_url(url),
                        'descripcion': '',
                        'fuente': 'sitemap',
                        'lastmod': lastmod.text if lastmod else None,
                        'changefreq': changefreq.text if changefreq else None,
                        'priority': priority.text if priority else None,
                        'fecha_descubrimiento': timezone.now(),
                    })
            
        except Exception as e:
            logger.error(f"Error al analizar sitemap {url_sitemap}: {str(e)}")
        
        logger.info(f"Descubiertas {len(urls_descubiertas)} URLs desde sitemap")
        return urls_descubiertas
    
    def _es_url_valida(self, url: str) -> bool:
        """
        Verifica si una URL es válida para procesamiento.
        
        Args:
            url: URL a verificar
            
        Returns:
            True si la URL es válida, False en caso contrario
        """
        try:
            parsed = urlparse(url)
            
            # Verificar esquema
            if parsed.scheme not in ['http', 'https']:
                return False
            
            # Verificar que tenga dominio
            if not parsed.netloc:
                return False
            
            # Filtrar extensiones de archivo no deseadas
            extensiones_no_deseadas = [
                '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.css', '.js',
                '.zip', '.rar', '.exe', '.mp4', '.mp3', '.avi', '.mov',
            ]
            
            if any(url.lower().endswith(ext) for ext in extensiones_no_deseadas):
                return False
            
            # Filtrar URLs con parámetros de seguimiento comunes
            parametros_no_deseados = [
                'utm_source', 'utm_medium', 'utm_campaign', 'utm_term',
                'utm_content', 'fbclid', 'gclid', 'msclkid',
            ]
            
            query_params = parse_qs(parsed.query)
            if any(param in query_params for param in parametros_no_deseados):
                return False
            
            return True
            
        except Exception:
            return False
    
    def _es_url_relevante(self, url: str) -> bool:
        """
        Verifica si una URL es relevante para bienes raíces en Arequipa.
        
        Args:
            url: URL a verificar
            
        Returns:
            True si la URL es relevante, False en caso contrario
        """
        url_lower = url.lower()
        
        # Verificar si contiene palabras clave de bienes raíces
        tiene_palabras_clave = any(
            re.search(patron, url_lower) for patron in self.patrones_bienes_raices
        )
        
        if not tiene_palabras_clave:
            return False
        
        # Verificar si está relacionada con Arequipa
        tiene_arequipa = any(
            palabra in url_lower for palabra in self.palabras_clave_arequipa
        )
        
        if not tiene_arequipa:
            # Verificar si es de un dominio conocido de bienes raíces
            es_dominio_conocido = any(
                dominio in url_lower for dominio in self.dominios_conocidos
            )
            
            if not es_dominio_conocido:
                return False
        
        # Verificar que no sea una página de contacto, about, etc.
        paginas_no_deseadas = [
            'contacto', 'contact', 'about', 'nosotros', 'aviso-legal',
            'politica-privacidad', 'terminos-condiciones', 'login',
            'registro', 'signup', 'signin', 'carrito', 'cart', 'checkout',
        ]
        
        if any(pagina in url_lower for pagina in paginas_no_deseadas):
            return False
        
        return True
    
    def _extraer_descripcion(self, elemento_link) -> str:
        """
        Extrae una descripción del elemento de enlace.
        
        Args:
            elemento_link: Elemento BeautifulSoup <a>
            
        Returns:
            Descripción extraída
        """
        # Intentar obtener texto del enlace
        texto = elemento_link.get_text(strip=True)
        if texto and len(texto) > 10:
            return texto[:150] + ('...' if len(texto) > 150 else '')
        
        # Intentar obtener del atributo title
        titulo = elemento_link.get('title', '')
        if titulo:
            return titulo[:150] + ('...' if len(titulo) > 150 else '')
        
        # Intentar obtener del atributo alt de una imagen dentro del enlace
        imagen = elemento_link.find('img')
        if imagen:
            alt = imagen.get('alt', '')
            if alt:
                return alt[:150] + ('...' if len(alt) > 150 else '')
        
        return ''
    
    def _extraer_titulo_desde_url(self, url: str) -> str:
        """
        Extrae un título legible desde una URL.
        
        Args:
            url: URL de la cual extraer el título
            
        Returns:
            Título extraído
        """
        try:
            parsed = urlparse(url)
            path = parsed.path
            
            # Remover extensiones y separadores
            titulo = path.replace('/', ' ').replace('-', ' ').replace('_', ' ')
            
            # Capitalizar palabras
            titulo = ' '.join(word.capitalize() for word in titulo.split())
            
            # Limitar longitud
            if len(titulo) > 100:
                titulo = titulo[:97] + '...'
            
            return titulo if titulo else 'Sin título'
            
        except Exception:
            return 'Sin título'
    
    def filtrar_urls_existentes(self, urls_descubiertas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filtra URLs que ya existen en la base de datos.
        
        Args:
            urls_descubiertas: Lista de URLs descubiertas
            
        Returns:
            Lista de URLs nuevas (no existentes)
        """
        if not urls_descubiertas:
            return []
        
        # Extraer URLs
        urls = [item['url'] for item in urls_descubiertas]
        
        # Buscar URLs existentes en la base de datos
        fuentes_existentes = FuenteWeb.objects.filter(url__in=urls).values_list('url', flat=True)
        urls_existentes = set(fuentes_existentes)
        
        # Filtrar URLs nuevas
        urls_nuevas = []
        for item in urls_descubiertas:
            if item['url'] not in urls_existentes:
                urls_nuevas.append(item)
        
        logger.info(f"Filtradas {len(urls_descubiertas) - len(urls_nuevas)} URLs existentes")
        return urls_nuevas
    
    def crear_fuentes_desde_urls(self, urls_descubiertas: List[Dict[str, Any]]) -> List[FuenteWeb]:
        """
        Crea objetos FuenteWeb a partir de URLs descubiertas.
        
        Args:
            urls_descubiertas: Lista de URLs descubiertas con metadatos
            
        Returns:
            Lista de FuenteWeb creadas
        """
        fuentes_creadas = []
        
        for item in urls_descubiertas:
            try:
                # Determinar categoría basada en la URL
                categoria = self._determinar_categoria(item['url'], item.get('titulo', ''))
                
                # Determinar frecuencia inicial
                frecuencia = self._determinar_frecuencia_inicial(categoria)
                
                # Crear la fuente
                fuente = FuenteWeb(
                    nombre=item.get('titulo', self._extraer_titulo_desde_url(item['url'])),
                    url=item['url'],
                    descripcion=item.get('descripcion', ''),
                    categoria=categoria,
                    tipo_fuente='portal_inmobiliario',
                    frecuencia_revision_minutos=frecuencia,
                    activa=True,
                    estado='activa',
                    descubierta_automaticamente=True,
                    fecha_descubrimiento=item.get('fecha_descubrimiento', timezone.now()),
                    metadatos_descubrimiento={
                        'fuente_descubrimiento': item.get('fuente', 'desconocida'),
                        'consulta': item.get('consulta', ''),
                        'url_origen': item.get('url_origen', ''),
                    }
                )
                
                fuente.save()
                fuentes_creadas.append(fuente)
                
                logger.debug(f"Fuente creada: {fuente.nombre} ({fuente.url})")
                
            except Exception as e:
                logger.error(f"Error al crear fuente desde {item.get('url', 'desconocida')}: {str(e)}")
                continue
        
        logger.info(f"Creadas {len(fuentes_creadas)} nuevas fuentes")
        return fuentes_creadas
    
    def _determinar_categoria(self, url: str, titulo: str) -> str:
        """
        Determina la categoría de una fuente basada en su URL y título.
        
        Args:
            url: URL de la fuente
            titulo: Título de la fuente
            
        Returns:
            Categoría determinada
        """
        texto = f"{url.lower()} {titulo.lower()}"
        
        categorias = {
            'casas': ['casa', 'house', 'vivienda'],
            'departamentos': ['departamento', 'apartamento', 'apartment', 'flat'],
            'terrenos': ['terreno', 'lote', 'lot', 'parcela'],
            'locales': ['local', 'comercial', 'tienda', 'shop', 'store'],
            'oficinas': ['oficina', 'office'],
            'proyectos': ['proyecto', 'project', 'desarrollo', 'development'],
        }
        
        for categoria, palabras in categorias.items():
            if any(palabra in texto for palabra in palabras):
                return categoria
        
        # Categoría por defecto
        return 'otros'
    
    def _determinar_frecuencia_inicial(self, categoria: str) -> int:
        """
        Determina la frecuencia inicial de revisión basada en la categoría.
        
        Args:
            categoria: Categoría de la fuente
            
        Returns:
            Frecuencia en minutos
        """
        frecuencias = {
            'proyectos': 240,  # 4 horas (cambian lentamente)
            'terrenos': 360,   # 6 horas
            'casas': 180,      # 3 horas
            'departamentos': 120,  # 2 horas
            'locales': 240,    # 4 horas
            'oficinas': 240,   # 4 horas
            'otros': 180,      # 3 horas
        }
        
        return frecuencias.get(categoria, 180)
    
    def ejecutar_descubrimiento_completo(self) -> Dict[str, Any]:
        """
        Ejecuta un proceso completo de descubrimiento de URLs.
        
        Returns:
            Resultados del descubrimiento
        """
        logger.info("Iniciando descubrimiento completo de URLs")
        
        resultados = {
            'estado': 'en_progreso',
            'timestamp_inicio': timezone.now().isoformat(),
            'urls_descubiertas': 0,
            'fuentes_creadas': 0,
            'errores': [],
        }
        
        try:
            # 1. Búsqueda por consultas comunes
            consultas_comunes = [
                'casas venta arequipa',
                'departamentos alquiler arequipa',
                'terrenos venta arequipa',
                'locales comerciales arequipa',
                'oficinas arequipa',
            ]
            
            todas_urls = []
            
            for consulta in consultas_comunes:
                try:
                    urls = self.descubrir_urls_por_busqueda(consulta, limite=10)
                    todas_urls.extend(urls)
                except Exception as e:
                    resultados['errores'].append(f"Error en búsqueda '{consulta}': {str(e)}")
            
            # 2. Exploración de sitios conocidos
            sitios_conocidos = [
                'https://www.adondevivir.com',
                'https://www.urbania.pe',
                'https://www.properati.com.pe',
                'https://www.vivanda.com.pe',
            ]
            
            for sitio in sitios_conocidos:
                try:
                    urls = self.descubrir_urls_por_exploracion(sitio, profundidad=1)
                    todas_urls.extend(urls)
                except Exception as e:
                    resultados['errores'].append(f"Error explorando {sitio}: {str(e)}")
            
            # 3. Filtrar URLs existentes
            urls_nuevas = self.filtrar_urls_existentes(todas_urls)
            resultados['urls_descubiertas'] = len(urls_nuevas)
            
            # 4. Crear fuentes desde URLs nuevas
            if urls_nuevas:
                fuentes_creadas = self.crear_fuentes_desde_urls(urls_nuevas)
                resultados['fuentes_creadas'] = len(fuentes_creadas)
            
            resultados['estado'] = 'completado'
            resultados['timestamp_fin'] = timezone.now().isoformat()
            
            logger.info(f"Descubrimiento completado: {resultados['urls_descubiertas']} URLs, "
                       f"{resultados['fuentes_creadas']} fuentes creadas")
            
        except Exception as e:
            resultados['estado'] = 'error'
            resultados['error'] = str(e)
            logger.error(f"Error en descubrimiento completo: {str(e)}")
        
        return resultados