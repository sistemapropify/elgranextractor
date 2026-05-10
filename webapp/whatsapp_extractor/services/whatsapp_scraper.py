"""
Servicio de scraping para WhatsApp Web usando Playwright.

Extrae mensajes de grupos de WhatsApp Web de forma automatizada.

DOS MODOS DE OPERACIÓN:
1. **Modo connect** (recomendado): Se conecta a Chrome ya abierto con WhatsApp Web
   vía Chrome DevTools Protocol (CDP) en puerto 9222.
   Requiere: chrome.exe --remote-debugging-port=9222

2. **Modo autónomo**: Lanza su propio navegador Chromium.
   Requiere: playwright install chromium
   El primer uso requiere login manual escaneando el código QR.
   Las cookies se guardan para sesiones posteriores.

Uso:
    scraper = WhatsAppScraper(modo='connect')
    mensajes = scraper.extraer_mensajes_grupo(
        nombre_grupo="Mi Grupo Inmobiliario",
    )
"""
import os
import json
import time
import logging
from datetime import timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass, field, asdict

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


@dataclass
class MensajeExtraido:
    """Representa un mensaje extraído de WhatsApp Web."""
    texto: str
    autor: str
    fuente: str
    extraido_en: str = field(default_factory=lambda: timezone.now().isoformat())


class WhatsAppScraperError(Exception):
    """Error base del scraper de WhatsApp."""
    pass


class WhatsAppScraper:
    """
    Scraper para WhatsApp Web usando Playwright.

    Args:
        modo: 'connect' para conectarse a Chrome existente (puerto 9222),
              'autonomo' para lanzar su propio navegador.
        headless: Solo aplica en modo 'autonomo'.
        cdp_port: Puerto de depuración remota de Chrome (default: 9222).
    """

    # URL de WhatsApp Web
    WHATSAPP_WEB_URL = "https://web.whatsapp.com"

    # Selectores CSS para elementos de WhatsApp Web
    SELECTOR_BARRA_BUSQUEDA = 'div[contenteditable="true"][data-tab="3"]'
    SELECTOR_LISTA_CHATS = 'div[role="row"]'
    SELECTOR_MENSAJES = 'div[data-testid="conversation-panel-messages"]'
    SELECTOR_BURBUJA_TEXTO = (
        'div[data-testid="conversation-panel-messages"] '
        'div.message-in, '
        'div[data-testid="conversation-panel-messages"] '
        'div.message-out'
    )
    SELECTOR_TEXTO_MENSAJE = 'span.selectable-text span'
    SELECTOR_AUTOR_MENSAJE = 'span[data-testid="author-name"]'

    # Configuración de scraping
    DIAS_HISTORICO = 7
    SCROLL_TIMEOUT = 30000
    NAVEGACION_TIMEOUT = 60000
    RETRY_MAX = 3
    RETRY_DELAY = 5

    def __init__(
        self,
        modo: str = 'connect',
        headless: bool = False,
        cdp_port: int = 9222,
    ):
        self.modo = modo
        self.headless = headless
        self.cdp_port = cdp_port
        self.browser = None
        self.context = None
        self.page = None
        self._playwright = None

    def _init_playwright(self):
        """Inicializa Playwright."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise WhatsAppScraperError(
                "Playwright no está instalado. Ejecute: "
                "pip install playwright && playwright install chromium"
            )
        self._playwright = sync_playwright().start()

    def _init_browser_connect(self):
        """
        Se conecta a una instancia de Chrome ya abierta con
        --remote-debugging-port={self.cdp_port}.

        La página de WhatsApp Web debe estar abierta y autenticada.
        """
        cdp_url = f"http://127.0.0.1:{self.cdp_port}"
        logger.info(f"Conectando a Chrome vía CDP: {cdp_url}")

        try:
            self.browser = self._playwright.chromium.connect_over_cdp(cdp_url)
        except Exception as e:
            raise WhatsAppScraperError(
                f"No se pudo conectar a Chrome en puerto {self.cdp_port}. "
                f"Asegúrate de tener Chrome abierto con:\n"
                f'  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" '
                f"--remote-debugging-port={self.cdp_port}\n"
                f"Error: {e}"
            )

        # Buscar la página de WhatsApp Web entre las pestañas abiertas
        pages = self.browser.contexts[0].pages if self.browser.contexts else []
        whatsapp_page = None
        for page in pages:
            if 'web.whatsapp.com' in page.url:
                whatsapp_page = page
                break

        if whatsapp_page:
            self.page = whatsapp_page
            self.context = self.browser.contexts[0]
            logger.info(f"Conectado a pestaña existente de WhatsApp Web: {whatsapp_page.url}")
        else:
            # Abrir nueva pestaña
            self.context = self.browser.contexts[0]
            self.page = self.context.new_page()
            logger.info("Abriendo nueva pestaña para WhatsApp Web...")
            self.page.goto(self.WHATSAPP_WEB_URL, timeout=self.NAVEGACION_TIMEOUT)

        # Verificar que estamos autenticados
        if not self._verificar_autenticado():
            raise WhatsAppScraperError(
                "No hay sesión activa de WhatsApp Web en Chrome. "
                "Abre web.whatsapp.com y escanea el código QR primero."
            )

        logger.info("Sesión de WhatsApp Web verificada correctamente")

    def _init_browser_autonomo(self):
        """Lanza su propio navegador Chromium."""
        self.browser = self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
            ]
        )
        self.context = self.browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            )
        )
        self.page = self.context.new_page()

    def _verificar_autenticado(self) -> bool:
        """
        Verifica si la página de WhatsApp Web está autenticada
        buscando la barra de búsqueda de chats.
        """
        try:
            self.page.wait_for_selector(
                self.SELECTOR_BARRA_BUSQUEDA,
                timeout=10000
            )
            return True
        except Exception:
            return False

    def _cargar_cookies(self, cookie_path: str) -> bool:
        """Carga cookies guardadas en el contexto del navegador."""
        if not os.path.exists(cookie_path):
            logger.info(f"No se encontraron cookies en: {cookie_path}")
            return False

        try:
            with open(cookie_path, 'r') as f:
                cookies = json.load(f)
            if self.context:
                self.context.add_cookies(cookies)
            logger.info(f"Cookies cargadas desde: {cookie_path} ({len(cookies)} cookies)")
            return True
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Error cargando cookies: {e}")
            return False

    def _guardar_cookies(self, cookie_path: str):
        """Guarda las cookies actuales del contexto."""
        if not self.context:
            return

        try:
            os.makedirs(os.path.dirname(cookie_path) or '.', exist_ok=True)
            cookies = self.context.cookies()
            with open(cookie_path, 'w') as f:
                json.dump(cookies, f, indent=2)
            logger.info(f"Cookies guardadas en: {cookie_path} ({len(cookies)} cookies)")
        except (IOError, OSError) as e:
            logger.error(f"Error guardando cookies: {e}")

    def _esperar_login(self, timeout: int = 120) -> bool:
        """
        Espera a que el usuario escanee el código QR.

        Args:
            timeout: Tiempo máximo de espera en segundos.

        Returns:
            True si el login fue exitoso.
        """
        logger.info("Esperando login de WhatsApp Web...")
        inicio = time.time()

        while time.time() - inicio < timeout:
            try:
                self.page.wait_for_selector(
                    self.SELECTOR_BARRA_BUSQUEDA,
                    timeout=5000
                )
                logger.info("Login exitoso en WhatsApp Web")
                return True
            except Exception:
                current_url = self.page.url
                if 'whatsapp.com' not in current_url:
                    logger.warning(f"Redirigido fuera de WhatsApp: {current_url}")
                time.sleep(2)

        logger.error("Timeout esperando login de WhatsApp Web")
        return False

    def _buscar_grupo(self, nombre_grupo: str) -> bool:
        """
        Busca y abre un grupo por nombre en WhatsApp Web.

        Args:
            nombre_grupo: Nombre exacto del grupo.

        Returns:
            True si se encontró y abrió el grupo.
        """
        try:
            # Hacer clic en la barra de búsqueda
            barra_busqueda = self.page.wait_for_selector(
                self.SELECTOR_BARRA_BUSQUEDA,
                timeout=self.NAVEGACION_TIMEOUT
            )
            barra_busqueda.click()
            time.sleep(1)

            # Escribir el nombre del grupo
            self.page.keyboard.type(nombre_grupo, delay=50)
            time.sleep(2)

            # Buscar el grupo en los resultados
            chats = self.page.query_selector_all(self.SELECTOR_LISTA_CHATS)
            for chat in chats:
                texto_chat = chat.inner_text()
                if nombre_grupo.lower() in texto_chat.lower():
                    chat.click()
                    time.sleep(2)
                    logger.info(f"Grupo abierto: {nombre_grupo}")
                    return True

            logger.warning(f"Grupo no encontrado: {nombre_grupo}")
            return False

        except Exception as e:
            logger.error(f"Error buscando grupo '{nombre_grupo}': {e}")
            return False

    def _hacer_scroll_infinito(self) -> int:
        """
        Hace scroll hacia arriba para cargar mensajes antiguos.

        Returns:
            Número de iteraciones de scroll realizadas.
        """
        iteraciones = 0
        max_iteraciones = 50

        try:
            panel_mensajes = self.page.wait_for_selector(
                self.SELECTOR_MENSAJES,
                timeout=self.NAVEGACION_TIMEOUT
            )

            for _ in range(max_iteraciones):
                self.page.evaluate(
                    'document.querySelector("div[data-testid=\'conversation-panel-messages\']")'
                    '.scrollTop = 0'
                )
                time.sleep(1)
                iteraciones += 1

                nuevo_scroll = self.page.evaluate(
                    'document.querySelector("div[data-testid=\'conversation-panel-messages\']")'
                    '.scrollHeight'
                )
                if nuevo_scroll <= 0:
                    break

        except Exception as e:
            logger.warning(f"Error durante scroll infinito: {e}")

        logger.info(f"Scroll completado: {iteraciones} iteraciones")
        return iteraciones

    def _extraer_mensajes(self) -> List[Dict]:
        """
        Extrae los mensajes visibles del panel de conversación.

        Returns:
            Lista de diccionarios con texto, autor y metadata.
        """
        mensajes = []

        try:
            burbujas = self.page.query_selector_all(self.SELECTOR_BURBUJA_TEXTO)

            for burbuja in burbujas:
                try:
                    spans_texto = burbuja.query_selector_all(self.SELECTOR_TEXTO_MENSAJE)
                    texto = ' '.join([span.inner_text() for span in spans_texto])

                    autor_span = burbuja.query_selector(self.SELECTOR_AUTOR_MENSAJE)
                    autor = autor_span.inner_text() if autor_span else 'Desconocido'

                    if texto.strip():
                        mensajes.append({
                            'texto': texto.strip(),
                            'autor': autor.strip(),
                        })

                except Exception as e:
                    logger.debug(f"Error extrayendo mensaje individual: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error extrayendo mensajes: {e}")

        logger.info(f"Mensajes extraídos: {len(mensajes)}")
        return mensajes

    def extraer_mensajes_grupo(
        self,
        nombre_grupo: str,
        cookie_path: str = '',
        dias_historico: int = 7
    ) -> List[Dict]:
        """
        Extrae mensajes de un grupo de WhatsApp Web.

        Flujo:
            1. Inicializar Playwright
            2. Conectar a Chrome (modo connect) o lanzar navegador (modo autonomo)
            3. Verificar autenticación en WhatsApp Web
            4. Buscar y abrir el grupo
            5. Hacer scroll para cargar histórico
            6. Extraer mensajes
            7. Guardar cookies (solo modo autonomo)

        Args:
            nombre_grupo: Nombre exacto del grupo en WhatsApp.
            cookie_path: Ruta al archivo JSON de cookies (solo modo autonomo).
            dias_historico: Días de histórico a extraer (default: 7).

        Returns:
            Lista de dicts con {texto, autor, fuente, extraido_en}.

        Raises:
            WhatsAppScraperError: Si ocurre un error crítico.
        """
        self.DIAS_HISTORICO = dias_historico
        resultado = []

        try:
            # 1. Inicializar Playwright
            self._init_playwright()

            # 2. Inicializar navegador según modo
            if self.modo == 'connect':
                self._init_browser_connect()
            else:
                self._init_browser_autonomo()

                # Cargar cookies si existen (solo modo autonomo)
                if cookie_path:
                    self._cargar_cookies(cookie_path)

                # Navegar a WhatsApp Web
                logger.info(f"Navegando a {self.WHATSAPP_WEB_URL}")
                self.page.goto(self.WHATSAPP_WEB_URL, timeout=self.NAVEGACION_TIMEOUT)

                # Esperar login
                if not self._esperar_login():
                    raise WhatsAppScraperError("No se pudo autenticar en WhatsApp Web")

                # Guardar cookies después del login exitoso
                if cookie_path:
                    self._guardar_cookies(cookie_path)

            # 3. Buscar y abrir el grupo
            if not self._buscar_grupo(nombre_grupo):
                raise WhatsAppScraperError(f"Grupo '{nombre_grupo}' no encontrado")

            # 4. Scroll para cargar histórico
            self._hacer_scroll_infinito()

            # 5. Extraer mensajes
            mensajes_crudos = self._extraer_mensajes()

            # 6. Formatear resultado
            fuente = nombre_grupo.lower().replace(' ', '_')
            for msg in mensajes_crudos:
                resultado.append({
                    'texto': msg['texto'],
                    'autor': msg['autor'],
                    'fuente': fuente,
                    'extraido_en': timezone.now().isoformat(),
                })

            logger.info(
                f"Extracción completada para '{nombre_grupo}': "
                f"{len(resultado)} mensajes"
            )
            return resultado

        except Exception as e:
            logger.error(f"Error en extracción de '{nombre_grupo}': {e}")
            raise WhatsAppScraperError(f"Error extrayendo mensajes: {str(e)}")

        finally:
            # Limpiar recursos (solo en modo autonomo cerramos el browser)
            if self.modo != 'connect':
                if self.browser:
                    self.browser.close()
                if self._playwright:
                    self._playwright.stop()
            # En modo connect, NO cerramos el browser del usuario
