"""
Módulo para capturar screenshots completos de páginas web y extraer texto mediante OCR.
Permite capturar toda la página desde arriba hasta el final, incluso contenido lazy-loaded.
"""

import logging
import os
import time
from typing import Dict, Any, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# Intentar importar Selenium para captura de pantalla
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, WebDriverException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    logger.warning("Selenium no está instalado. Instalar con: pip install selenium")

# Intentar importar Pillow para procesamiento de imágenes
try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    logger.warning("Pillow no está instalado. Instalar con: pip install Pillow")

# Intentar importar pytesseract para OCR
try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    logger.warning("pytesseract no está instalado. Instalar con: pip install pytesseract")

# Intentar importar OpenCV para procesamiento avanzado de imágenes
try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False
    logger.warning("OpenCV no está instalado. Instalar con: pip install opencv-python")


class CapturaScreenshot:
    """
    Clase para capturar screenshots completos de páginas web y extraer texto mediante OCR.
    
    Características:
    1. Captura de pantalla completa (full page screenshot) usando Selenium
    2. Scroll automático para capturar toda la página
    3. Guardado en formato JPG con calidad configurable
    4. Extracción de texto mediante OCR (Tesseract)
    5. Procesamiento de imagen para mejorar OCR
    """
    
    def __init__(self, 
                 driver_path: Optional[str] = None,
                 output_dir: str = "capturas_screenshots",
                 jpg_quality: int = 85,
                 ocr_language: str = "spa+eng"):
        """
        Inicializa el capturador de screenshots.
        
        Args:
            driver_path: Ruta al ChromeDriver (opcional, se detecta automáticamente)
            output_dir: Directorio donde guardar las capturas
            jpg_quality: Calidad del JPG (1-100)
            ocr_language: Idioma para OCR (ej: 'spa+eng' para español e inglés)
        """
        self.driver_path = driver_path
        self.output_dir = Path(output_dir)
        self.jpg_quality = jpg_quality
        self.ocr_language = ocr_language
        self.driver = None
        
        # Crear directorio de salida si no existe
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Verificar dependencias
        self._verificar_dependencias()
    
    def _verificar_dependencias(self):
        """Verifica que las dependencias necesarias estén instaladas."""
        if not SELENIUM_AVAILABLE:
            logger.error("Selenium no está instalado. Es necesario para captura de pantalla.")
        
        if not PILLOW_AVAILABLE:
            logger.warning("Pillow no está instalado. No se podrá procesar imágenes.")
        
        if not TESSERACT_AVAILABLE:
            logger.warning("pytesseract no está instalado. No se podrá extraer texto con OCR.")
    
    def inicializar_driver(self):
        """Inicializa el driver de Selenium para Chrome."""
        if not SELENIUM_AVAILABLE:
            raise ImportError("Selenium no está instalado")
        
        if self.driver:
            return
        
        try:
            from selenium.webdriver.chrome.options import Options
            
            chrome_options = Options()
            chrome_options.add_argument("--headless")  # Ejecutar en modo headless
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            
            # Configurar para captura completa
            chrome_options.add_argument("--hide-scrollbars")
            
            # Inicializar driver
            if self.driver_path:
                self.driver = webdriver.Chrome(
                    executable_path=self.driver_path,
                    options=chrome_options
                )
            else:
                self.driver = webdriver.Chrome(options=chrome_options)
            
            logger.info("Driver de Chrome inicializado exitosamente")
            
        except Exception as e:
            logger.error(f"Error inicializando driver de Chrome: {e}")
            raise
    
    def cerrar_driver(self):
        """Cierra el driver de Selenium."""
        if self.driver:
            try:
                self.driver.quit()
                self.driver = None
                logger.info("Driver cerrado exitosamente")
            except Exception as e:
                logger.error(f"Error cerrando driver: {e}")
    
    def _hacer_scroll_completo(self, timeout: int = 30):
        """
        Hace scroll completo en la página para cargar todo el contenido lazy-loaded.
        
        Args:
            timeout: Tiempo máximo de espera en segundos
        """
        if not self.driver:
            return
        
        try:
            # Obtener altura total inicial de la página
            altura_total = self.driver.execute_script("return document.body.scrollHeight")
            altura_ventana = self.driver.execute_script("return window.innerHeight")
            
            logger.info(f"Altura total de la página: {altura_total}px, Altura de ventana: {altura_ventana}px")
            
            # Hacer scroll en incrementos
            scroll_incremento = altura_ventana - 100  # Dejar un pequeño margen
            scroll_actual = 0
            intentos = 0
            max_intentos = 10
            
            while scroll_actual < altura_total and intentos < max_intentos:
                # Hacer scroll
                self.driver.execute_script(f"window.scrollTo(0, {scroll_actual});")
                time.sleep(0.8)  # Esperar a que cargue contenido lazy-loaded
                
                # Actualizar posición de scroll
                scroll_actual += scroll_incremento
                
                # Verificar si la altura cambió (contenido nuevo cargado)
                nueva_altura = self.driver.execute_script("return document.body.scrollHeight")
                if nueva_altura > altura_total:
                    logger.info(f"Nueva altura detectada: {nueva_altura}px (antes: {altura_total}px)")
                    altura_total = nueva_altura
                
                intentos += 1
            
            # Volver al inicio para captura consistente
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            
            logger.info(f"Scroll completo realizado. Altura final: {altura_total}px")
            
        except Exception as e:
            logger.warning(f"Error haciendo scroll completo: {e}")
    
    def capturar_screenshot_completo(self, url: str, nombre_archivo: Optional[str] = None) -> Dict[str, Any]:
        """
        Captura un screenshot completo de una página web.
        
        Args:
            url: URL de la página a capturar
            nombre_archivo: Nombre del archivo de salida (sin extensión)
            
        Returns:
            Diccionario con información de la captura:
            {
                'exito': bool,
                'ruta_imagen': str,
                'tamaño_bytes': int,
                'dimensiones': (ancho, alto),
                'error': str (si hubo error),
                'metadatos': dict
            }
        """
        resultado = {
            'exito': False,
            'ruta_imagen': None,
            'tamaño_bytes': 0,
            'dimensiones': (0, 0),
            'error': None,
            'metadatos': {
                'url': url,
                'metodo': 'selenium_full_page',
                'tiempo_inicio': time.time(),
                'scroll_completado': False,
                'driver_inicializado': False
            }
        }
        
        if not SELENIUM_AVAILABLE:
            resultado['error'] = 'Selenium no está disponible'
            return resultado
        
        try:
            # Inicializar driver
            self.inicializar_driver()
            resultado['metadatos']['driver_inicializado'] = True
            
            logger.info(f"Capturando screenshot completo de: {url}")
            
            # Navegar a la URL
            self.driver.get(url)
            
            # Esperar a que la página cargue completamente
            WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Esperar a que JavaScript cargue contenido dinámico
            time.sleep(3)
            
            # Hacer scroll completo para cargar todo el contenido
            self._hacer_scroll_completo()
            resultado['metadatos']['scroll_completado'] = True
            
            # Esperar después del scroll para que cargue imágenes y contenido
            time.sleep(2)
            
            # Obtener dimensiones de la página completa
            ancho = self.driver.execute_script("return document.documentElement.scrollWidth")
            alto = self.driver.execute_script("return document.documentElement.scrollHeight")
            
            # Configurar tamaño de ventana para capturar toda la página
            self.driver.set_window_size(ancho, alto)
            time.sleep(1)
            
            # Generar nombre de archivo si no se proporciona
            if not nombre_archivo:
                # Crear nombre basado en la URL y timestamp
                from urllib.parse import urlparse
                parsed_url = urlparse(url)
                dominio = parsed_url.netloc.replace('.', '_')
                ruta = parsed_url.path.replace('/', '_')[:50]
                timestamp = int(time.time())
                nombre_archivo = f"{dominio}_{ruta}_{timestamp}"
                nombre_archivo = ''.join(c for c in nombre_archivo if c.isalnum() or c in '_-')
            
            # Ruta completa del archivo
            ruta_imagen = self.output_dir / f"{nombre_archivo}.jpg"
            
            # Capturar screenshot
            screenshot_data = self.driver.get_screenshot_as_png()
            
            # Guardar como JPG
            if PILLOW_AVAILABLE:
                from io import BytesIO
                img = Image.open(BytesIO(screenshot_data))
                
                # Convertir a RGB si es necesario (PNG puede tener canal alpha)
                if img.mode in ('RGBA', 'LA'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background
                
                # Guardar como JPG con calidad configurable
                img.save(ruta_imagen, 'JPEG', quality=self.jpg_quality, optimize=True)
            else:
                # Guardar como PNG si Pillow no está disponible
                with open(ruta_imagen.with_suffix('.png'), 'wb') as f:
                    f.write(screenshot_data)
                ruta_imagen = ruta_imagen.with_suffix('.png')
            
            # Obtener información del archivo
            tamaño = os.path.getsize(ruta_imagen)
            if PILLOW_AVAILABLE:
                with Image.open(ruta_imagen) as img:
                    dimensiones = img.size
            else:
                dimensiones = (ancho, alto)
            
            # Actualizar resultado
            resultado['exito'] = True
            resultado['ruta_imagen'] = str(ruta_imagen)
            resultado['tamaño_bytes'] = tamaño
            resultado['dimensiones'] = dimensiones
            resultado['metadatos']['tiempo_fin'] = time.time()
            resultado['metadatos']['duracion'] = resultado['metadatos']['tiempo_fin'] - resultado['metadatos']['tiempo_inicio']
            
            logger.info(f"Screenshot guardado exitosamente: {ruta_imagen} ({tamaño} bytes, {dimensiones[0]}x{dimensiones[1]})")
            
            return resultado
            
        except TimeoutException:
            resultado['error'] = f"Timeout al cargar la página {url}"
            logger.error(f"Timeout capturando {url}")
            return resultado
            
        except WebDriverException as e:
            resultado['error'] = f"Error WebDriver: {str(e)}"
            logger.error(f"Error WebDriver capturando {url}: {e}")
            return resultado
            
        except Exception as e:
            resultado['error'] = f"Error inesperado: {str(e)}"
            logger.error(f"Error capturando screenshot de {url}: {e}")
            return resultado
    
    def extraer_texto_ocr(self, ruta_imagen: str, preprocesar: bool = True) -> Dict[str, Any]:
        """
        Extrae texto de una imagen usando OCR.
        
        Args:
            ruta_imagen: Ruta a la imagen (JPG/PNG)
            preprocesar: Si es True, aplica preprocesamiento para mejorar OCR
            
        Returns:
            Diccionario con resultados del OCR:
            {
                'exito': bool,
                'texto': str,
                'confianza_promedio': float,
                'idioma_detectado': str,
                'error': str (si hubo error),
                'metadatos': dict
            }
        """
        resultado = {
            'exito': False,
            'texto': '',
            'confianza_promedio': 0.0,
            'idioma_detectado': self.ocr_language,
            'error': None,
            'metadatos': {
                'ruta_imagen': ruta_imagen,
                'preprocesado': preprocesar,
                'tiempo_inicio': time.time()
            }
        }
        
        if not TESSERACT_AVAILABLE:
            resultado['error'] = 'pytesseract no está disponible'
            return resultado
        
        if not os.path.exists(ruta_imagen):
            resultado['error'] = f'Archivo no encontrado: {ruta_imagen}'
            return resultado
        
        try:
            import pytesseract
            from PIL import Image
            
            # Cargar imagen
            img = Image.open(ruta_imagen)
            
            # Preprocesamiento para mejorar OCR
            if preprocesar and PILLOW_AVAILABLE:
                img = self._preprocesar_imagen_ocr(img)
                resultado['metadatos']['preprocesado'] = True
            
            # Configurar parámetros de Tesseract
            config = f'--oem 3 --psm 3 -l {self.ocr_language}'
            
            # Extraer texto con datos de confianza
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT, config=config)
            
            # Filtrar texto con confianza razonable (> 60)
            textos = []
            confianzas = []
            
            for i in range(len(data['text'])):
                conf = float(data['conf'][i]) if data['conf'][i] != '-1' else 0
                texto = data['text'][i].strip()
                
                if texto and conf > 60:
                    textos.append(texto)
                    confianzas.append(conf)
            
            # Combinar texto
            texto_completo = ' '.join(textos)
            
            # Calcular confianza promedio
            confianza_promedio = sum(confianzas) / len(confianzas) if confianzas else 0
            
            # Actualizar resultado
            resultado['exito'] = True
            resultado['texto'] = texto_completo
            resultado['confianza_promedio'] = confianza_promedio
            resultado['metadatos']['tiempo_fin'] = time.time()
            resultado['metadatos']['duracion'] = resultado['metadatos']['tiempo_fin'] - resultado['metadatos']['tiempo_inicio']
            resultado['metadatos']['num_palabras'] = len(texto_completo.split())
            resultado['metadatos']['num_caracteres'] = len(texto_completo)
            
            logger.info(f"OCR completado: {len(texto_completo)} caracteres, confianza promedio: {confianza_promedio:.2f}")
            
            return resultado
            
        except Exception as e:
            resultado['error'] = f"Error en OCR: {str(e)}"
            logger.error(f"Error extrayendo texto con OCR de {ruta_imagen}: {e}")
            return resultado
    
    def _preprocesar_imagen_ocr(self, img):
        """
        Preprocesa una imagen para mejorar la precisión del OCR.
        
        Args:
            img: Imagen PIL.Image
            
        Returns:
            Imagen preprocesada
        """
        try:
            # Convertir a escala de grises
            if img.mode != 'L':
                img = img.convert('L')
            
            # Aumentar contraste
            from PIL import ImageEnhance
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(2.0)  # Aumentar contraste
            
            # Redimensionar si es muy grande (máximo 2000px de ancho)
            max_width = 2000
            if img.width > max_width:
                ratio = max_width / img.width
                new_height = int(img.height * ratio)
                img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
            
            return img
            
        except Exception as e:
            logger.warning(f"Error en preprocesamiento de imagen: {e}")
            return img
    
    def capturar_y_extraer_texto(self, url: str, guardar_imagen: bool = True) -> Dict[str, Any]:
        """
        Captura un screenshot completo y extrae texto mediante OCR en un solo paso.
        
        Args:
            url: URL de la página a capturar
            guardar_imagen: Si es True, guarda la imagen; si es False, la procesa en memoria
            
        Returns:
            Diccionario combinado con resultados de captura y OCR
        """
        resultado_combinado = {
            'exito': False,
            'url': url,
            'captura': None,
            'ocr': None,
            'texto_completo': '',
            'error': None,
            'metadatos': {
                'tiempo_inicio': time.time()
            }
        }
        
        try:
            # Paso 1: Capturar screenshot
            resultado_captura = self.capturar_screenshot_completo(url)
            resultado_combinado['captura'] = resultado_captura
            
            if not resultado_captura['exito']:
                resultado_combinado['error'] = f"Error en captura: {resultado_captura['error']}"
                return resultado_combinado
            
            # Paso 2: Extraer texto con OCR
            ruta_imagen = resultado_captura['ruta_imagen']
            resultado_ocr = self.extraer_texto_ocr(ruta_imagen)
            resultado_combinado['ocr'] = resultado_ocr
            
            if not resultado_ocr['exito']:
                resultado_combinado['error'] = f"Error en OCR: {resultado_ocr['error']}"
                # Aún consideramos éxito parcial si la captura fue exitosa
                resultado_combinado['exito'] = True
            else:
                resultado_combinado['texto_completo'] = resultado_ocr['texto']
                resultado_combinado['exito'] = True
            
            # Limpiar imagen si no se quiere guardar
            if not guardar_imagen and ruta_imagen and os.path.exists(ruta_imagen):
                try:
                    os.remove(ruta_imagen)
                    logger.info(f"Imagen temporal eliminada: {ruta_imagen}")
                except Exception as e:
                    logger.warning(f"No se pudo eliminar imagen temporal: {e}")
            
            resultado_combinado['metadatos']['tiempo_fin'] = time.time()
            resultado_combinado['metadatos']['duracion'] = (
                resultado_combinado['metadatos']['tiempo_fin'] - 
                resultado_combinado['metadatos']['tiempo_inicio']
            )
            
            logger.info(f"Proceso completo: {url} -> {len(resultado_combinado['texto_completo'])} caracteres extraídos")
            
            return resultado_combinado
            
        except Exception as e:
            resultado_combinado['error'] = f"Error en proceso completo: {str(e)}"
            logger.error(f"Error en capturar_y_extraer_texto para {url}: {e}")
            return resultado_combinado
    
    def __enter__(self):
        """Context manager para uso con 'with'."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cierra el driver al salir del contexto."""
        self.cerrar_driver()


# Función de conveniencia para uso rápido
def capturar_pagina_completa(url: str, output_dir: str = "capturas_screenshots") -> Dict[str, Any]:
    """
    Función de conveniencia para capturar una página completa con un solo comando.
    
    Args:
        url: URL de la página a capturar
        output_dir: Directorio donde guardar las capturas
        
    Returns:
        Diccionario con resultados de captura y OCR
    """
    with CapturaScreenshot(output_dir=output_dir) as capturador:
        return capturador.capturar_y_extraer_texto(url)


if __name__ == "__main__":
    # Ejemplo de uso
    import sys
    
    if len(sys.argv) > 1:
        url = sys.argv[1]
        print(f"Capturando página: {url}")
        
        resultado = capturar_pagina_completa(url)
        
        if resultado['exito']:
            print(f"✓ Captura exitosa")
            print(f"  Imagen: {resultado['captura']['ruta_imagen']}")
            print(f"  Dimensiones: {resultado['captura']['dimensiones'][0]}x{resultado['captura']['dimensiones'][1]}")
            print(f"  Texto extraído: {len(resultado['texto_completo'])} caracteres")
            print(f"  Confianza OCR: {resultado['ocr']['confianza_promedio']:.2f}")
            
            # Mostrar primeras 500 caracteres del texto
            preview = resultado['texto_completo'][:500]
            if len(resultado['texto_completo']) > 500:
                preview += "..."
            print(f"\nPreview del texto:\n{preview}")
        else:
            print(f"✗ Error: {resultado['error']}")
    else:
        print("Uso: python captura_screenshot.py <URL>")
        print("Ejemplo: python captura_screenshot.py https://example.com")