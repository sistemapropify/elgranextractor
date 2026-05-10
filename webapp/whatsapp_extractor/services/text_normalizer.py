"""
Servicio de normalización y validación de texto para mensajes de WhatsApp.

Pre-procesa el texto crudo de los mensajes antes del análisis con IA.
Implementa detección de basura, validación de requerimientos inmobiliarios
y limpieza de texto.

Funciones principales:
    - limpiar_texto(): Eliminar emojis, URLs, HTML tags, espacios excesivos
    - detectar_basura(): Detectar mensajes irrelevantes
    - es_requerimiento_valido(): Validar keywords inmobiliarias
"""
import re
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class TextNormalizer:
    """
    Normalizador de texto para mensajes de WhatsApp inmobiliarios.

    Realiza limpieza, validación y detección de contenido relevante
    en mensajes extraídos de grupos de WhatsApp.
    """

    # Patrones de basura comunes en grupos inmobiliarios
    PATRONES_BASURA = [
        # Saludos y despedidas genéricas
        r'\bbuenos\s*días\b',
        r'\bbuenas\s*tardes\b',
        r'\bbuenas\s*noches\b',
        r'\bgracias\b',
        r'\bde\s*nada\b',
        r'\bpor\s*favor\b',
        r'\bcon\s*gusto\b',
        # Spam y promociones genéricas
        r'\bcomparte\s*por\s*favor\b',
        r'\bpásalo\s*a\s*tus\s*grupos\b',
        r'\bcadena\b',
        r'\breenviado\b',
        # Reacciones a mensajes
        r'^\s*👍\s*$',
        r'^\s*❤️\s*$',
        r'^\s*🙏\s*$',
        r'^\s*ok\s*$',
        r'^\s*okey\s*$',
        r'^\s*si\s*$',
        r'^\s*no\s*$',
        r'^\s*gracias\s*$',
        # Números de teléfono solos
        r'^\s*\+?\d{9,15}\s*$',
        # Enlaces genéricos (no inmobiliarios)
        r'^\s*https?://(?!.*(?:propiedad|casa|departamento|terreno|alquiler|venta)).*\s*$',
    ]

    # Keywords que indican un requerimiento inmobiliario válido
    KEYWORDS_REQUERIMIENTO = [
        # Verbos de acción
        r'\bbusco\b', r'\bbuscamos\b', r'\bnecesito\b', r'\bnecesitamos\b',
        r'\bquiero\b', r'\bqueremos\b', r'\bestoy\s*buscando\b',
        r'\bandamos\s*buscando\b', r'\brequiero\b', r'\brequerimos\b',
        r'\bofrezco\b', r'\bofrecemos\b', r'\bvendo\b', r'\bventa\b',
        r'\balquilo\b', r'\balquiler\b',
        # Tipos de propiedad
        r'\bdepartamento\b', r'\bcasa\b', r'\bterreno\b', r'\boficina\b',
        r'\blocal\b', r'\blocal\s*comercial\b', r'\balmacén\b', r'\balmacen\b',
        r'\bpropiedad\b', r'\binmueble\b', r'\bcuarto\b', r'\bhabitación\b',
        r'\bhabitacion\b', r'\bpenthouse\b', r'\bduplex\b', r'\bdúplex\b',
        # Condiciones
        r'\bcompra\b', r'\bcompro\b', r'\balquiler\b', r'\balquilo\b',
        r'\banticrético\b', r'\banticresis\b',
        # Ubicaciones (Arequipa)
        r'\bCayma\b', r'\bYanahuara\b', r'\bCercado\b', r'\bMiraflores\b',
        r'\bJosé\s*Luis\s*Bustamante\b', r'\bBustamante\b',
        r'\bSachaca\b', r'\bCerro\s*Colorado\b', r'\bMariano\s*Melgar\b',
        r'\bPaucarpata\b', r'\bSocabaya\b', r'\bHunter\b', r'\bTiabaya\b',
        r'\bArequipa\b',
        # Características
        r'\bdormitorios\b', r'\bhabitaciones\b', r'\bcuartos\b',
        r'\bbaños\b', r'\bbanos\b', r'\bcochera\b', r'\bgarage\b',
        r'\bestacionamiento\b', r'\bascensor\b', r'\bamoblado\b',
        r'\bamueblado\b', r'\bárea\b', r'\barea\b', r'\bmetros\b',
        r'\bm2\b', r'\bmt2\b',
        # Presupuesto
        r'\bpresupuesto\b', r'\bprecio\b', r'\bdólares\b', r'\bdolares\b',
        r'\bsoles\b', r'\busd\b', r'\bpen\b', r'\bs/\.?\b',
        # Urgencia
        r'\bURGENTE\b', r'\bUrgente\b', r'\burgente\b',
        r'\boportunidad\b', r'\bremate\b',
    ]

    # Compilar patrones para eficiencia
    _patrones_basura_compilados = [
        re.compile(p, re.IGNORECASE) for p in PATRONES_BASURA
    ]
    _keywords_compiladas = [
        re.compile(k, re.IGNORECASE) for k in KEYWORDS_REQUERIMIENTO
    ]

    # Longitud mínima para considerar un mensaje válido
    LONGITUD_MINIMA = 30

    # Cantidad mínima de keywords para considerar válido
    KEYWORDS_MINIMAS = 2

    @classmethod
    def limpiar_texto(cls, texto: str) -> str:
        """
        Limpia el texto eliminando elementos no deseados.

        Operaciones:
            1. Eliminar emojis y caracteres especiales
            2. Eliminar URLs
            3. Eliminar HTML tags
            4. Normalizar espacios
            5. Eliminar saltos de línea excesivos
            6. Trim

        Args:
            texto: Texto crudo del mensaje.

        Returns:
            Texto limpio y normalizado.
        """
        if not texto:
            return ''

        # 1. Eliminar HTML tags
        texto = re.sub(r'<[^>]+>', ' ', texto)

        # 2. Eliminar URLs
        texto = re.sub(r'https?://\S+', '', texto)
        texto = re.sub(r'www\.\S+', '', texto)

        # 3. Eliminar emojis (rangos Unicode de emojis)
        emoji_pattern = re.compile(
            '['
            '\U0001F600-\U0001F64F'  # Emoticons
            '\U0001F300-\U0001F5FF'  # Símbolos y pictogramas
            '\U0001F680-\U0001F6FF'  # Transporte y mapas
            '\U0001F1E0-\U0001F1FF'  # Banderas
            '\U00002702-\U000027B0'  # Dingbats
            '\U000024C2-\U0001F251'  # Varios
            '\u2600-\u26FF'          # Símbolos misceláneos
            '\u2700-\u27BF'          # Dingbats
            '\uFE00-\uFE0F'          # Variación selectores
            '\u200D'                 # Zero-width joiner
            ']+',
            flags=re.UNICODE
        )
        texto = emoji_pattern.sub(' ', texto)

        # 4. Eliminar caracteres de control (excepto saltos de línea)
        texto = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', texto)

        # 5. Normalizar espacios
        texto = re.sub(r'\s+', ' ', texto)

        # 6. Trim
        texto = texto.strip()

        return texto

    @classmethod
    def detectar_basura(cls, texto: str) -> bool:
        """
        Detecta si un mensaje es basura/irrelevante.

        Evalúa el texto contra patrones de basura comunes en
        grupos inmobiliarios de WhatsApp.

        Args:
            texto: Texto del mensaje a evaluar.

        Returns:
            True si el mensaje se considera basura.
        """
        if not texto or not texto.strip():
            return True

        texto_limpio = cls.limpiar_texto(texto)

        # Verificar contra patrones de basura
        for patron in cls._patrones_basura_compilados:
            if patron.search(texto_limpio):
                logger.debug(f"Basura detectada por patrón: {patron.pattern}")
                return True

        return False

    @classmethod
    def es_requerimiento_valido(cls, texto: str) -> bool:
        """
        Valida si un mensaje contiene un requerimiento inmobiliario válido.

        Criterios:
            - Longitud mínima: > 30 caracteres
            - Cantidad mínima de keywords: >= 2

        Args:
            texto: Texto del mensaje a validar.

        Returns:
            True si el mensaje parece un requerimiento válido.
        """
        if not texto or not texto.strip():
            return False

        texto_limpio = cls.limpiar_texto(texto)

        # Validar longitud mínima
        if len(texto_limpio) < cls.LONGITUD_MINIMA:
            logger.debug(
                f"Mensaje rechazado por longitud: {len(texto_limpio)} "
                f"< {cls.LONGITUD_MINIMA}"
            )
            return False

        # Contar keywords inmobiliarias
        keywords_encontradas = 0
        for keyword in cls._keywords_compiladas:
            if keyword.search(texto_limpio):
                keywords_encontradas += 1

        if keywords_encontradas < cls.KEYWORDS_MINIMAS:
            logger.debug(
                f"Mensaje rechazado por keywords: {keywords_encontradas} "
                f"< {cls.KEYWORDS_MINIMAS}"
            )
            return False

        logger.debug(
            f"Mensaje válido: {keywords_encontradas} keywords, "
            f"{len(texto_limpio)} caracteres"
        )
        return True

    @classmethod
    def clasificar_mensaje(cls, texto: str) -> dict:
        """
        Clasifica un mensaje y retorna un reporte detallado.

        Args:
            texto: Texto del mensaje a clasificar.

        Returns:
            Dict con:
                - es_valido: bool
                - es_basura: bool
                - keywords_encontradas: list[str]
                - longitud: int
                - texto_limpio: str
                - razon_rechazo: str (si aplica)
        """
        resultado = {
            'es_valido': False,
            'es_basura': True,
            'keywords_encontradas': [],
            'longitud': 0,
            'texto_limpio': '',
            'razon_rechazo': '',
        }

        if not texto or not texto.strip():
            resultado['razon_rechazo'] = 'Texto vacío'
            return resultado

        texto_limpio = cls.limpiar_texto(texto)
        resultado['texto_limpio'] = texto_limpio
        resultado['longitud'] = len(texto_limpio)

        # Detectar basura
        if cls.detectar_basura(texto_limpio):
            resultado['razon_rechazo'] = 'Contenido clasificado como basura'
            return resultado
        resultado['es_basura'] = False

        # Contar keywords
        keywords = []
        for keyword in cls._keywords_compiladas:
            if keyword.search(texto_limpio):
                keywords.append(keyword.pattern)
        resultado['keywords_encontradas'] = keywords

        # Validar longitud
        if len(texto_limpio) < cls.LONGITUD_MINIMA:
            resultado['razon_rechazo'] = (
                f"Longitud insuficiente: {len(texto_limpio)} "
                f"< {cls.LONGITUD_MINIMA}"
            )
            return resultado

        # Validar keywords mínimas
        if len(keywords) < cls.KEYWORDS_MINIMAS:
            resultado['razon_rechazo'] = (
                f"Keywords insuficientes: {len(keywords)} "
                f"< {cls.KEYWORDS_MINIMAS}"
            )
            return resultado

        resultado['es_valido'] = True
        return resultado
