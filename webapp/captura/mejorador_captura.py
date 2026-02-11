"""
Mejorador de captura para extraer contenido completo de páginas web.
Implementa técnicas avanzadas para capturar contenido dinámico y contenido
que no se captura completamente con requests simples.
"""

import logging
import time
import re
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

logger = logging.getLogger(__name__)


class MejoradorCaptura:
    """
    Mejorador de captura que implementa múltiples estrategias para extraer
    contenido completo de páginas web, especialmente contenido dinámico.
    
    Estrategias:
    1. Requests estándar (básico)
    2. Selenium con Chrome (para JavaScript)
    3. Extracción de contenido específico (artículos, noticias)
    4. Scroll automático para contenido lazy-loaded
    5. Extracción de contenido de iframes
    """
    
    def __init__(self, usar_selenium: bool = True, timeout: int = 30):
        """
        Inicializa el mejorador de captura.
        
        Args:
            usar_selenium: Si es True, usa Selenium para contenido dinámico
            timeout: Tiempo máximo de espera en segundos
        """
        self.usar_selenium = usar_selenium
        self.timeout = timeout
        self.driver = None
        
        # Configurar headers para requests
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        }
        
        # Patrones para detectar contenido principal
        self.patrones_contenido_principal = [
            r'<article[^>]*>.*?</article>',
            r'<div[^>]*class="[^"]*(content|article|post|entry|main)[^"]*"[^>]*>',
            r'<main[^>]*>.*?</main>',
            r'<div[^>]*id="[^"]*(content|article|post|entry|main)[^"]*"[^>]*>',
        ]
        
        # Selectores CSS para contenido principal (usados con Selenium)
        self.selectores_contenido = [
            'article',
            'main',
            '.content',
            '.article',
            '.post-content',
            '.entry-content',
            '.story-content',
            '.news-content',
            '.blog-content',
            '[role="main"]',
        ]
        
        # Elementos a eliminar (publicidad, scripts, etc.)
        self.elementos_a_eliminar = [
            'script', 'style', 'iframe', 'nav', 'footer', 'header',
            '.advertisement', '.ads', '.publicidad', '.sidebar',
            '.social-share', '.comments', '.related-posts',
            '.newsletter', '.popup', '.modal',
        ]
    
    def __del__(self):
        """Cierra el driver de Selenium si está abierto."""
        self.cerrar_driver()
    
    def cerrar_driver(self):
        """Cierra el driver de Selenium."""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None
    
    def capturar_con_requests(self, url: str) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Captura contenido usando requests estándar.
        
        Args:
            url: URL a capturar
            
        Returns:
            Tupla (contenido_html, metadatos)
        """
        metadatos = {
            'metodo': 'requests',
            'tiempo_inicio': time.time(),
            'exito': False,
            'error': None,
        }
        
        try:
            logger.info(f"Capturando con requests: {url}")
            
            response = requests.get(
                url,
                headers=self.headers,
                timeout=self.timeout,
                allow_redirects=True,
                stream=False
            )
            
            metadatos['status_code'] = response.status_code
            metadatos['url_final'] = response.url
            metadatos['content_type'] = response.headers.get('Content-Type', '')
            metadatos['encoding'] = response.encoding
            
            if response.status_code != 200:
                metadatos['error'] = f"HTTP {response.status_code}"
                return None, metadatos
            
            # Decodificar contenido
            try:
                contenido = response.content.decode(response.encoding or 'utf-8')
            except UnicodeDecodeError:
                contenido = response.content.decode('latin-1', errors='ignore')
            
            metadatos['tamaño_bytes'] = len(contenido.encode('utf-8'))
            metadatos['exito'] = True
            
            logger.info(f"Captura requests exitosa: {metadatos['tamaño_bytes']} bytes")
            return contenido, metadatos
            
        except requests.exceptions.Timeout:
            metadatos['error'] = f"Timeout después de {self.timeout} segundos"
            logger.error(f"Timeout capturando {url}")
            return None, metadatos
            
        except requests.exceptions.ConnectionError as e:
            metadatos['error'] = f"Error de conexión: {str(e)}"
            logger.error(f"Error de conexión capturando {url}: {e}")
            return None, metadatos
            
        except Exception as e:
            metadatos['error'] = f"Error inesperado: {str(e)}"
            logger.error(f"Error capturando {url} con requests: {e}")
            return None, metadatos
    
    def inicializar_selenium(self):
        """Inicializa el driver de Selenium si no está inicializado."""
        if self.driver is None and self.usar_selenium:
            try:
                options = webdriver.ChromeOptions()
                options.add_argument('--headless')  # Ejecutar sin interfaz gráfica
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                options.add_argument('--disable-gpu')
                options.add_argument('--window-size=1920,1080')
                options.add_argument(f'user-agent={self.headers["User-Agent"]}')
                
                # Deshabilitar imágenes para mayor velocidad
                prefs = {"profile.managed_default_content_settings.images": 2}
                options.add_experimental_option("prefs", prefs)
                
                self.driver = webdriver.Chrome(options=options)
                self.driver.set_page_load_timeout(self.timeout)
                
                logger.info("Driver Selenium inicializado")
                
            except Exception as e:
                logger.error(f"Error inicializando Selenium: {e}")
                self.usar_selenium = False
    
    def capturar_con_selenium(self, url: str) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Captura contenido usando Selenium para contenido dinámico.
        Versión mejorada con más tiempo de espera y scroll completo.
        
        Args:
            url: URL a capturar
            
        Returns:
            Tupla (contenido_html, metadatos)
        """
        metadatos = {
            'metodo': 'selenium',
            'tiempo_inicio': time.time(),
            'exito': False,
            'error': None,
        }
        
        if not self.usar_selenium:
            metadatos['error'] = 'Selenium no disponible'
            return None, metadatos
        
        try:
            self.inicializar_selenium()
            if not self.driver:
                metadatos['error'] = 'No se pudo inicializar Selenium'
                return None, metadatos
            
            logger.info(f"Capturando con Selenium mejorado: {url}")
            
            # Navegar a la URL
            self.driver.get(url)
            
            # Esperar a que la página cargue completamente (más tiempo)
            WebDriverWait(self.driver, self.timeout * 2).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Esperar a que JavaScript cargue contenido dinámico
            time.sleep(3)
            
            # Hacer scroll COMPLETO para cargar todo el contenido lazy-loaded
            self._hacer_scroll_completo()
            
            # Esperar después del scroll para que cargue imágenes y contenido
            time.sleep(2)
            
            # Intentar esperar a que elementos específicos carguen (si existen)
            try:
                # Esperar a que el contenido principal esté presente
                WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "article, .post-content, .content, main"))
                )
            except TimeoutException:
                # No hay problema si no encuentra estos selectores
                pass
            
            # Obtener el HTML COMPLETO del DOM actual
            contenido = self.driver.page_source
            
            # También obtener el HTML del body completo
            body_html = self.driver.execute_script("return document.body.outerHTML;")
            
            # Usar el más grande de los dos
            if len(body_html) > len(contenido):
                contenido = body_html
            
            metadatos['tamaño_bytes'] = len(contenido.encode('utf-8'))
            metadatos['exito'] = True
            metadatos['url_final'] = self.driver.current_url
            metadatos['scroll_completado'] = True
            
            logger.info(f"Captura Selenium mejorada exitosa: {metadatos['tamaño_bytes']} bytes")
            return contenido, metadatos
            
        except TimeoutException:
            metadatos['error'] = f"Timeout Selenium después de {self.timeout * 2} segundos"
            logger.error(f"Timeout Selenium capturando {url}")
            # Intentar obtener HTML aunque haya timeout
            try:
                if self.driver:
                    contenido = self.driver.page_source
                    if contenido and len(contenido) > 1000:
                        metadatos['exito'] = True
                        metadatos['tamaño_bytes'] = len(contenido.encode('utf-8'))
                        metadatos['warning'] = 'Timeout pero se obtuvo HTML'
                        return contenido, metadatos
            except:
                pass
            return None, metadatos
            
        except WebDriverException as e:
            metadatos['error'] = f"Error WebDriver: {str(e)}"
            logger.error(f"Error WebDriver capturando {url}: {e}")
            return None, metadatos
            
        except Exception as e:
            metadatos['error'] = f"Error inesperado Selenium: {str(e)}"
            logger.error(f"Error capturando {url} con Selenium: {e}")
            return None, metadatos
    
    def _hacer_scroll_para_cargar(self):
        """Hace scroll en la página para cargar contenido lazy-loaded."""
        try:
            # Obtener altura total de la página
            altura_total = self.driver.execute_script("return document.body.scrollHeight")
            
            # Hacer scroll en incrementos
            scroll_incremento = 800
            scroll_actual = 0
            
            while scroll_actual < altura_total:
                self.driver.execute_script(f"window.scrollTo(0, {scroll_actual});")
                time.sleep(0.5)  # Esperar a que cargue contenido
                scroll_actual += scroll_incremento
                
                # Verificar si la altura cambió (contenido nuevo cargado)
                nueva_altura = self.driver.execute_script("return document.body.scrollHeight")
                if nueva_altura > altura_total:
                    altura_total = nueva_altura
            
            # Volver al inicio
            self.driver.execute_script("window.scrollTo(0, 0);")
            
        except Exception as e:
            logger.warning(f"Error haciendo scroll: {e}")
    
    def extraer_contenido_principal(self, html: str, url: str) -> str:
        """
        Extrae el contenido principal de una página HTML.
        Para captura en crudo: devuelve el HTML completo sin procesar.
        
        Args:
            html: HTML completo de la página
            url: URL de la página (para resolver URLs relativas)
            
        Returns:
            HTML completo sin procesar (captura en crudo)
        """
        if not html:
            return ""
        
        # Para captura en crudo: devolver el HTML completo tal cual
        logger.info(f"Contenido principal (crudo): {len(html)} caracteres")
        return html
    
    def _limpiar_contenido(self, elemento, url: str):
        """
        Limpia el contenido eliminando elementos no deseados.
        
        Args:
            elemento: Elemento BeautifulSoup a limpiar
            url: URL base para resolver URLs relativas
            
        Returns:
            Elemento limpio
        """
        if not elemento:
            return elemento
        
        # Hacer una copia para no modificar el original
        elemento = elemento.copy()
        
        # Eliminar solo scripts, estilos e iframes (no eliminar nav, footer, header, etc.)
        for selector in ['script', 'style', 'iframe', 'noscript']:
            for tag in elemento.select(selector):
                tag.decompose()
        
        # Convertir URLs relativas a absolutas
        self._convertir_urls_absolutas(elemento, url)
        
        # Eliminar atributos innecesarios
        for tag in elemento.find_all(True):
            # Mantener solo atributos esenciales
            atributos_a_mantener = ['href', 'src', 'alt', 'title']
            atributos = list(tag.attrs.keys())
            
            for attr in atributos:
                if attr not in atributos_a_mantener:
                    del tag[attr]
        
        return elemento
    
    def _convertir_urls_absolutas(self, elemento, url_base: str):
        """
        Convierte URLs relativas a absolutas.
        
        Args:
            elemento: Elemento BeautifulSoup
            url_base: URL base para resolver URLs relativas
        """
        for tag in elemento.find_all(['a', 'img', 'link', 'script']):
            if tag.name == 'a' and tag.get('href'):
                href = tag['href']
                if not href.startswith(('http://', 'https://', 'mailto:', 'tel:', '#')):
                    tag['href'] = urljoin(url_base, href)
            
            elif tag.name == 'img' and tag.get('src'):
                src = tag['src']
                if not src.startswith(('http://', 'https://', 'data:')):
                    tag['src'] = urljoin(url_base, src)
    
    def capturar_contenido_completo(self, url: str) -> Dict[str, Any]:
        """
        Captura contenido completo usando múltiples estrategias.
        
        Args:
            url: URL a capturar
            
        Returns:
            Diccionario con resultados de la captura
        """
        resultado = {
            'url': url,
            'exito': False,
            'contenido_html': None,
            'contenido_principal': None,
            'metodo_usado': None,
            'metadatos': {},
            'error': None,
            'tiempo_total': 0,
        }
        
        tiempo_inicio = time.time()
        
        try:
            # Intentar primero con requests (más rápido)
            contenido_html, metadatos_requests = self.capturar_con_requests(url)
            
            if contenido_html:
                resultado['contenido_html'] = contenido_html
                resultado['metodo_usado'] = 'requests'
                resultado['metadatos'] = metadatos_requests
                resultado['exito'] = True
                
                # Extraer contenido principal
                resultado['contenido_principal'] = self.extraer_contenido_principal(
                    contenido_html, url
                )
                
                # Verificar si el contenido parece completo
                if self._contenido_parece_completo(contenido_html):
                    logger.info(f"Captura requests parece completa para {url}")
                else:
                    logger.warning(f"Captura requests puede estar incompleta para {url}")
                    
                    # Intentar con Selenium si requests no fue suficiente
                    if self.usar_selenium:
                        logger.info(f"Intentando captura Selenium para contenido más completo")
                        contenido_selenium, metadatos_selenium = self.capturar_con_selenium(url)
                        
                        if contenido_selenium:
                            # Comparar tamaños
                            tamaño_requests = len(contenido_html.encode('utf-8'))
                            tamaño_selenium = len(contenido_selenium.encode('utf-8'))
                            
                            # Usar Selenium si es significativamente más grande
                            if tamaño_selenium > tamaño_requests * 1.5:
                                resultado['contenido_html'] = contenido_selenium
                                resultado['metodo_usado'] = 'selenium'
                                resultado['metadatos'] = metadatos_selenium
                                
                                # Extraer contenido principal del HTML de Selenium
                                resultado['contenido_principal'] = self.extraer_contenido_principal(
                                    contenido_selenium, url
                                )
                                
                                logger.info(f"Usando Selenium (más completo: {tamaño_selenium} vs {tamaño_requests} bytes)")
            else:
                # Requests falló, intentar con Selenium
                if self.usar_selenium:
                    contenido_selenium, metadatos_selenium = self.capturar_con_selenium(url)
                    
                    if contenido_selenium:
                        resultado['contenido_html'] = contenido_selenium
                        resultado['contenido_principal'] = self.extraer_contenido_principal(
                            contenido_selenium, url
                        )
                        resultado['metodo_usado'] = 'selenium'
                        resultado['metadatos'] = metadatos_selenium
                        resultado['exito'] = True
                    else:
                        resultado['error'] = metadatos_selenium.get('error', 'Error desconocido')
                else:
                    resultado['error'] = metadatos_requests.get('error', 'Error desconocido')
            
        except Exception as e:
            resultado['error'] = f"Error en captura completa: {str(e)}"
            logger.error(f"Error capturando contenido completo de {url}: {e}")
        
        finally:
            resultado['tiempo_total'] = time.time() - tiempo_inicio
            self.cerrar_driver()
        
        return resultado
    
    def _contenido_parece_completo(self, html: str) -> bool:
        """
        Verifica si el contenido HTML parece completo.
        
        Args:
            html: HTML a verificar
            
        Returns:
            True si el contenido parece completo
        """
        if not html:
            return False
        
        # Verificar longitud mínima
        if len(html) < 1000:
            return False
        
        # Verificar que tenga elementos estructurales básicos
        tiene_body = '<body' in html.lower()
        tiene_html = '<html' in html.lower()
        
        # Verificar que tenga contenido de texto significativo
        soup = BeautifulSoup(html, 'html.parser')
        texto = soup.get_text(strip=True)
        
        # Contar palabras
        palabras = texto.split()
        tiene_suficiente_texto = len(palabras) > 100
        
        # Verificar que no sea principalmente JavaScript
        tiene_mucho_script = html.count('<script') > html.count('<p') * 2
        
        return tiene_body and tiene_html and tiene_suficiente_texto and not tiene_mucho_script
    
    def analizar_calidad_captura(self, html: str) -> Dict[str, Any]:
        """
        Analiza la calidad de una captura HTML.
        
        Args:
            html: HTML a analizar
            
        Returns:
            Diccionario con métricas de calidad
        """
        if not html:
            return {
                'calidad': 'muy_baja',
                'razon': 'HTML vacío',
                'metricas': {}
            }
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extraer texto
            texto = soup.get_text(strip=True)
            palabras = texto.split()
            
            # Contar elementos
            num_scripts = len(soup.find_all('script'))
            num_estilos = len(soup.find_all('style'))
            num_parrafos = len(soup.find_all('p'))
            num_imagenes = len(soup.find_all('img'))
            num_enlaces = len(soup.find_all('a'))
            
            # Calcular métricas
            ratio_texto_script = len(palabras) / max(num_scripts, 1)
            densidad_texto = len(palabras) / max(len(html) / 1000, 1)
            
            # Determinar calidad
            calidad = 'media'
            razon = ''
            
            if len(palabras) < 50:
                calidad = 'muy_baja'
                razon = f'Muy poco texto ({len(palabras)} palabras)'
            elif len(palabras) < 200:
                calidad = 'baja'
                razon = f'Poco texto ({len(palabras)} palabras)'
            elif ratio_texto_script < 10:
                calidad = 'baja'
                razon = f'Demasiado JavaScript (ratio: {ratio_texto_script:.1f})'
            elif densidad_texto < 1:
                calidad = 'baja'
                razon = f'Baja densidad de texto ({densidad_texto:.1f} palabras/KB)'
            elif len(palabras) > 1000 and num_parrafos > 10:
                calidad = 'alta'
                razon = f'Contenido extenso ({len(palabras)} palabras, {num_parrafos} párrafos)'
            
            return {
                'calidad': calidad,
                'razon': razon,
                'metricas': {
                    'palabras': len(palabras),
                    'caracteres': len(texto),
                    'scripts': num_scripts,
                    'estilos': num_estilos,
                    'parrafos': num_parrafos,
                    'imagenes': num_imagenes,
                    'enlaces': num_enlaces,
                    'ratio_texto_script': ratio_texto_script,
                    'densidad_texto': densidad_texto,
                }
            }
            
        except Exception as e:
            return {
                'calidad': 'desconocida',
                'razon': f'Error en análisis: {str(e)}',
                'metricas': {}
            }


# Función de utilidad para uso directo
def capturar_contenido_mejorado(url: str, usar_selenium: bool = True) -> Dict[str, Any]:
    """
    Función de utilidad para capturar contenido mejorado.
    
    Args:
        url: URL a capturar
        usar_selenium: Si es True, usa Selenium para contenido dinámico
        
    Returns:
        Diccionario con resultados de la captura
    """
    mejorador = MejoradorCaptura(usar_selenium=usar_selenium)
    return mejorador.capturar_contenido_completo(url)