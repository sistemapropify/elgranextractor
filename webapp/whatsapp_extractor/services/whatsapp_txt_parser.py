"""
Servicio de parsing para archivos de exportación de WhatsApp (.txt).

Parsea el formato nativo de exportación de texto de WhatsApp:
    - Formato: YYYY-MM-DD HH:MM - Nombre: Mensaje
    - Formato alternativo: DD/MM/YYYY HH:MM - Nombre: Mensaje
    - Maneja mensajes multi-línea (continuación sin timestamp)
    - Filtra encabezados automáticos de exportación
    - Soporte completo para Unicode español latinoamericano

Uso:
    parser = WhatsAppTxtParser()
    mensajes = parser.parsear_archivo(ruta_archivo)
    for msg in mensajes:
        print(msg['autor'], msg['fecha_hora'], msg['texto'])
"""
import re
import os
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


@dataclass
class MensajeParseado:
    """Representa un mensaje parseado de un archivo de exportación WhatsApp."""
    texto: str
    autor: str
    fecha_hora: str  # ISO format: "2024-01-15T14:30:00"
    fecha: str       # "2024-01-15"
    hora: str        # "14:30:00"
    raw: str = ''    # Línea original sin procesar
    idx: int = 0     # Índice secuencial en el archivo


class WhatsAppTxtParserError(Exception):
    """Error base del parser de WhatsApp."""
    pass


class WhatsAppTxtParser:
    """
    Parser dedicado al formato nativo de exportación de texto de WhatsApp.

    Formatos soportados:
        1. Formato estándar Android (24h):
           2024-01-15 14:30 - Juan Pérez: Hola, busco departamento en Cayma

        2. Formato iOS/Android con AM/PM:
           1/15/2024, 2:30 PM - Juan Pérez: Hola, busco...

        3. Formato con corchetes:
           [15/01/2024 14:30:00] Juan Pérez: Hola, busco...

        4. Formato DD/MM/YYYY sin AM/PM:
           15/01/2024 14:30 - Juan Pérez: Hola, busco...

    Atributos de clase:
        PATRONES: Lista de tuplas (nombre, regex compilado) para detectar timestamps.
        PATRONES_SISTEMA: Lista de patrones para filtrar mensajes del sistema.
        PATRONES_ENCABEZADO: Lista de patrones para filtrar encabezados de exportación.
        CODIFICACIONES: Lista de codificaciones a probar al leer archivos.
        MAX_TAMANIO_ARCHIVO: Tamaño máximo de archivo en bytes (100 MB).
    """

    # Patrones de timestamp en orden de especificidad (del más específico al menos)
    PATRON_FORMATO_1 = re.compile(
        r'^(\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2})\s*-\s*([^:]+):\s*(.*)',
        re.UNICODE
    )
    PATRON_FORMATO_2 = re.compile(
        r'^(\d{1,2}/\d{1,2}/\d{2,4},?\s+\d{1,2}:\d{2}(?:\s*[AP]M)?)\s*-\s*([^:]+):\s*(.*)',
        re.IGNORECASE | re.UNICODE
    )
    PATRON_FORMATO_3 = re.compile(
        r'^\[(\d{1,2}/\d{1,2}/\d{2,4},?\s+\d{1,2}:\d{2}(?::\d{2})?(?:[\s\u202f\xa0]*[aApP][\.\s\u202f\xa0]*[mM][\.\s\u202f\xa0]*)?)\]\s*([^:]+):\s*(.*)',
        re.UNICODE
    )
    PATRON_FORMATO_4 = re.compile(
        r'^(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2})\s*-\s*([^:]+):\s*(.*)',
        re.UNICODE
    )
    PATRON_FORMATO_5 = re.compile(
        r'^(\d{1,2}/\d{1,2}/\d{2,4},?\s+\d{1,2}:\d{2}(?:\s*[AP]M)?)\s*-\s*([^:]+):\s*(.*)',
        re.UNICODE
    )

    PATRONES = [
        ('formato_1', PATRON_FORMATO_1),
        ('formato_2', PATRON_FORMATO_2),
        ('formato_3', PATRON_FORMATO_3),
        ('formato_4', PATRON_FORMATO_4),
        ('formato_5', PATRON_FORMATO_5),
    ]

    # Patrones de mensajes del sistema (se filtran)
    PATRONES_SISTEMA = [
        re.compile(r'Mensajes y llamadas cifrados', re.IGNORECASE | re.UNICODE),
        re.compile(r'Este chat contiene mensajes cifrados', re.IGNORECASE | re.UNICODE),
        re.compile(r'Los mensajes y las llamadas están cifrados', re.IGNORECASE | re.UNICODE),
        re.compile(r'se unió usando el enlace de invitación', re.IGNORECASE | re.UNICODE),
        re.compile(r'creó el grupo', re.IGNORECASE | re.UNICODE),
        re.compile(r'cambió el nombre del grupo', re.IGNORECASE | re.UNICODE),
        re.compile(r'cambió la descripción del grupo', re.IGNORECASE | re.UNICODE),
        re.compile(r'eliminó este grupo', re.IGNORECASE | re.UNICODE),
        re.compile(r'te añadió', re.IGNORECASE | re.UNICODE),
        re.compile(r'eliminó a', re.IGNORECASE | re.UNICODE),
        re.compile(r'abandonó el grupo', re.IGNORECASE | re.UNICODE),
        re.compile(r'salió del grupo', re.IGNORECASE | re.UNICODE),
        re.compile(r'Los mensajes y llamadas ahora están cifrados', re.IGNORECASE | re.UNICODE),
        re.compile(r'Seguridad del chat', re.IGNORECASE | re.UNICODE),
    ]

    # Patrones de encabezado de exportación
    PATRONES_ENCABEZADO = [
        re.compile(r'^\s*WhatsApp Chat', re.IGNORECASE | re.UNICODE),
        re.compile(r'^\s*Chat de WhatsApp', re.IGNORECASE | re.UNICODE),
        re.compile(r'^\s*Exportado el', re.IGNORECASE | re.UNICODE),
        re.compile(r'^\s*Exported on', re.IGNORECASE | re.UNICODE),
    ]

    # Codificaciones a probar al leer archivos
    CODIFICACIONES = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']

    # Tamaño máximo de archivo: 100 MB
    MAX_TAMANIO_ARCHIVO = 100 * 1024 * 1024

    @classmethod
    def parsear_archivo(cls, ruta: str) -> List[Dict]:
        """
        Parsea un archivo de exportación de WhatsApp y retorna lista de mensajes.

        Args:
            ruta: Ruta al archivo .txt de exportación de WhatsApp.

        Returns:
            List[Dict]: Lista de diccionarios con keys:
                - 'texto': str — Contenido del mensaje
                - 'autor': str — Nombre del remitente
                - 'fecha_hora': str — Timestamp en ISO format
                - 'fecha': str — Fecha en formato YYYY-MM-DD
                - 'hora': str — Hora en formato HH:MM:SS
                - 'raw': str — Línea original
                - 'idx': int — Índice secuencial

        Raises:
            WhatsAppTxtParserError: Si el archivo no existe, es muy grande,
                                    o tiene formato inválido.
            FileNotFoundError: Si la ruta no existe.
        """
        cls._validar_archivo(ruta)
        contenido = cls._leer_archivo(ruta)
        return cls.parsear_texto(contenido)

    @classmethod
    def parsear_texto(cls, texto: str) -> List[Dict]:
        """
        Parsea texto crudo de exportación WhatsApp y retorna lista de mensajes.

        Args:
            texto: Contenido completo del archivo de exportación.

        Returns:
            List[Dict]: Lista de mensajes parseados.
        """
        lineas = texto.split('\n')
        return cls._parsear_lineas(lineas)

    @classmethod
    def _validar_archivo(cls, ruta: str) -> None:
        """
        Valida que el archivo exista, sea legible y no exceda el tamaño máximo.

        Args:
            ruta: Ruta al archivo.

        Raises:
            FileNotFoundError: Si el archivo no existe.
            WhatsAppTxtParserError: Si el archivo es muy grande.
        """
        if not os.path.exists(ruta):
            raise FileNotFoundError(f'Archivo no encontrado: {ruta}')

        if not os.access(ruta, os.R_OK):
            raise WhatsAppTxtParserError(f'No se puede leer el archivo: {ruta}')

        tamaño = os.path.getsize(ruta)
        if tamaño > cls.MAX_TAMANIO_ARCHIVO:
            raise WhatsAppTxtParserError(
                f'Archivo demasiado grande: {tamaño} bytes '
                f'(máximo {cls.MAX_TAMANIO_ARCHIVO} bytes)'
            )

        if tamaño == 0:
            raise WhatsAppTxtParserError(f'Archivo vacío: {ruta}')

    @classmethod
    def _leer_archivo(cls, ruta: str) -> str:
        """
        Lee el archivo probando múltiples codificaciones.

        Args:
            ruta: Ruta al archivo.

        Returns:
            str: Contenido del archivo como string.

        Raises:
            WhatsAppTxtParserError: Si no se puede leer con ninguna codificación.
        """
        errores = []
        for encoding in cls.CODIFICACIONES:
            try:
                with open(ruta, 'r', encoding=encoding) as f:
                    contenido = f.read()
                logger.debug(f'Archivo leído con codificación: {encoding}')
                return contenido
            except (UnicodeDecodeError, UnicodeError) as e:
                errores.append(f'{encoding}: {str(e)}')
                continue

        raise WhatsAppTxtParserError(
            f'No se pudo leer el archivo con ninguna codificación. '
            f'Errores: {"; ".join(errores)}'
        )

    @classmethod
    def _parsear_lineas(cls, lineas: List[str]) -> List[Dict]:
        """
        Parsea las líneas del archivo en mensajes estructurados.

        Args:
            lineas: Lista de líneas del archivo.

        Returns:
            List[Dict]: Lista de mensajes parseados.
        """
        mensajes: List[Dict] = []
        mensaje_actual: Optional[Dict] = None
        idx = 0

        for linea in lineas:
            linea_stripped = linea.rstrip('\n\r')

            # Saltar líneas vacías
            if not linea_stripped:
                continue

            # Saltar encabezados de exportación
            if cls._es_encabezado_exportacion(linea_stripped):
                continue

            # Intentar matchear timestamp
            match = cls._match_timestamp(linea_stripped)

            if match:
                # Guardar mensaje anterior si existe
                if mensaje_actual is not None:
                    mensajes.append(mensaje_actual)

                # Crear nuevo mensaje
                timestamp_str, autor, texto = match
                fecha_hora_iso = cls._parsear_fecha_hora(timestamp_str)

                if fecha_hora_iso is None:
                    logger.warning(
                        f'No se pudo parsear timestamp: "{timestamp_str}" — '
                        f'se omite la línea'
                    )
                    continue

                # Saltar mensajes del sistema
                if cls._es_mensaje_sistema(texto):
                    continue

                idx += 1
                fecha, hora = fecha_hora_iso.split('T')
                autor_limpio = autor.strip()
                # Detectar si el autor del encabezado es un número de teléfono
                # (ej: "+51 958 063 438" o "958063438")
                telefono_autor = cls._extraer_telefono(autor_limpio)
                mensaje_actual = {
                    'texto': texto.strip(),
                    'autor': autor_limpio,
                    'fecha_hora': fecha_hora_iso,
                    'fecha': fecha,
                    'hora': hora,
                    'raw': linea_stripped,
                    'idx': idx,
                    'agente_telefono': telefono_autor,
                }

            elif mensaje_actual is not None:
                # Es continuación de mensaje anterior (multi-línea)
                mensaje_actual['texto'] += '\n' + linea_stripped

        # Guardar el último mensaje
        if mensaje_actual is not None:
            mensajes.append(mensaje_actual)

        logger.info(f'Parseados {len(mensajes)} mensajes de {len(lineas)} líneas')
        return mensajes

    @classmethod
    def _match_timestamp(cls, linea: str) -> Optional[Tuple[str, str, str]]:
        """
        Intenta matchear un timestamp al inicio de la línea.

        Args:
            linea: Línea a analizar.

        Returns:
            Optional[Tuple[str, str, str]]: (timestamp_str, autor, texto) o None.
        """
        for nombre_patron, patron in cls.PATRONES:
            match = patron.match(linea)
            if match:
                timestamp_str = match.group(1).strip()
                autor = match.group(2).strip()
                texto = match.group(3).strip()
                return (timestamp_str, autor, texto)

        return None

    @classmethod
    def _parsear_fecha_hora(cls, timestamp_str: str) -> Optional[str]:
        """
        Convierte un timestamp de WhatsApp a formato ISO (YYYY-MM-DDTHH:MM:SS).

        Args:
            timestamp_str: String de timestamp en formato WhatsApp.

        Returns:
            Optional[str]: Timestamp en ISO format o None si no se puede parsear.
        """
        timestamp_str = timestamp_str.strip()

        # Formato 1: YYYY-MM-DD HH:MM
        try:
            dt = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M')
            return dt.isoformat()
        except ValueError:
            pass

        # Formato 2: DD/MM/YYYY HH:MM AM/PM o DD/MM/YY HH:MM AM/PM
        try:
            # Intentar con AM/PM primero
            dt = datetime.strptime(timestamp_str, '%d/%m/%Y %I:%M %p')
            return dt.isoformat()
        except ValueError:
            pass

        try:
            dt = datetime.strptime(timestamp_str, '%d/%m/%y %I:%M %p')
            return dt.isoformat()
        except ValueError:
            pass

        # Formato 3: DD/MM/YYYY HH:MM (24h)
        try:
            dt = datetime.strptime(timestamp_str, '%d/%m/%Y %H:%M')
            return dt.isoformat()
        except ValueError:
            pass

        # Formato 4: DD/MM/YY HH:MM (24h)
        try:
            dt = datetime.strptime(timestamp_str, '%d/%m/%y %H:%M')
            return dt.isoformat()
        except ValueError:
            pass

        # Formato 5: DD/MM/YYYY HH:MM:SS (con segundos)
        try:
            dt = datetime.strptime(timestamp_str, '%d/%m/%Y %H:%M:%S')
            return dt.isoformat()
        except ValueError:
            pass

        # Formato 6: Con coma después de la fecha: "15/01/2024, 14:30"
        try:
            # Remover coma después de la fecha
            limpio = re.sub(r'(\d{4}),\s+', r'\1 ', timestamp_str)
            dt = datetime.strptime(limpio, '%d/%m/%Y %H:%M')
            return dt.isoformat()
        except ValueError:
            pass

        # Formato 7: Con coma y AM/PM: "15/01/2024, 2:30 PM"
        try:
            limpio = re.sub(r'(\d{4}),\s+', r'\1 ', timestamp_str)
            dt = datetime.strptime(limpio, '%d/%m/%Y %I:%M %p')
            return dt.isoformat()
        except ValueError:
            pass

        # Formato 8: Con coma después de año de 2 dígitos: "12/6/24, 10:51"
        try:
            # Remover coma después de cualquier año (2 o 4 dígitos)
            limpio = re.sub(r'(\d{1,4}),\s+', r'\1 ', timestamp_str)
            dt = datetime.strptime(limpio, '%d/%m/%y %H:%M')
            return dt.isoformat()
        except ValueError:
            pass

        # Formato 9: Con coma y año de 2 dígitos con AM/PM: "12/6/24, 10:51 PM"
        try:
            limpio = re.sub(r'(\d{1,4}),\s+', r'\1 ', timestamp_str)
            dt = datetime.strptime(limpio, '%d/%m/%y %I:%M %p')
            return dt.isoformat()
        except ValueError:
            pass

        # --- Formatos para iOS con coma, segundos y AM/PM con puntos (a. m. / p. m.) ---
        # Estos formatos usan \u202f (espacio estrecho) y \xa0 (non-breaking space)
        # antes/entre a.m./p.m.
        # Ej: "11/05/26, 7:16:03 a. m." o "11/05/26, 7:16:03 p. m."
        # Ej: "11/05/26, 7:16:03 a. m." (con \xa0 entre a. y m.)
        # Primero normalizar: quitar \u202f, \xa0 y espacios alrededor de a.m./p.m.

        # Formato 10: DD/MM/YY, HH:MM:SS a. m. (con segundos, AM/PM con puntos y \u202f/\xa0)
        try:
            # Normalizar: reemplazar \u202f y \xa0 por espacio, quitar coma
            limpio = re.sub(r'[\u202f\xa0]', ' ', timestamp_str)
            limpio = re.sub(r'(\d{1,4}),\s+', r'\1 ', limpio)
            # Convertir "a. m." → "AM" (incluyendo punto final opcional)
            limpio = re.sub(r'\s*a\s*\.\s*m\s*\.?\s*', ' AM', limpio, flags=re.IGNORECASE)
            limpio = re.sub(r'\s*p\s*\.\s*m\s*\.?\s*', ' PM', limpio, flags=re.IGNORECASE)
            limpio = limpio.strip()
            dt = datetime.strptime(limpio, '%d/%m/%y %I:%M:%S %p')
            return dt.isoformat()
        except ValueError:
            pass

        # Formato 11: DD/MM/YY, HH:MM:SS (con segundos, sin AM/PM)
        try:
            limpio = re.sub(r'(\d{1,4}),\s+', r'\1 ', timestamp_str)
            dt = datetime.strptime(limpio, '%d/%m/%y %H:%M:%S')
            return dt.isoformat()
        except ValueError:
            pass

        # Formato 12: DD/MM/YYYY, HH:MM:SS a. m. (año 4 dígitos, con segundos, AM/PM con puntos)
        try:
            limpio = re.sub(r'[\u202f\xa0]', ' ', timestamp_str)
            limpio = re.sub(r'(\d{1,4}),\s+', r'\1 ', limpio)
            limpio = re.sub(r'\s*a\s*\.\s*m\s*\.?\s*', ' AM', limpio, flags=re.IGNORECASE)
            limpio = re.sub(r'\s*p\s*\.\s*m\s*\.?\s*', ' PM', limpio, flags=re.IGNORECASE)
            limpio = limpio.strip()
            dt = datetime.strptime(limpio, '%d/%m/%Y %I:%M:%S %p')
            return dt.isoformat()
        except ValueError:
            pass

        # Formato 13: DD/MM/YYYY, HH:MM:SS (año 4 dígitos, con segundos, sin AM/PM)
        try:
            limpio = re.sub(r'(\d{1,4}),\s+', r'\1 ', timestamp_str)
            dt = datetime.strptime(limpio, '%d/%m/%Y %H:%M:%S')
            return dt.isoformat()
        except ValueError:
            pass

        logger.warning(f'No se pudo parsear timestamp: "{timestamp_str}"')
        return None

    @classmethod
    def _es_mensaje_sistema(cls, texto: str) -> bool:
        """
        Verifica si el texto corresponde a un mensaje del sistema de WhatsApp.

        Args:
            texto: Texto del mensaje.

        Returns:
            bool: True si es mensaje del sistema.
        """
        for patron in cls.PATRONES_SISTEMA:
            if patron.search(texto):
                return True
        return False

    @classmethod
    def _es_encabezado_exportacion(cls, linea: str) -> bool:
        """
        Verifica si la línea es un encabezado de exportación de WhatsApp.

        Args:
            linea: Línea a verificar.

        Returns:
            bool: True si es encabezado.
        """
        for patron in cls.PATRONES_ENCABEZADO:
            if patron.match(linea):
                return True
        return False

    @classmethod
    def detectar_formato(cls, ruta: str) -> str:
        """
        Detecta qué formato de exportación WhatsApp tiene el archivo.

        Args:
            ruta: Ruta al archivo.

        Returns:
            str: Nombre del formato detectado, o 'desconocido'.
        """
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                primeras_lineas = [f.readline() for _ in range(20)]
        except (UnicodeDecodeError, UnicodeError):
            try:
                with open(ruta, 'r', encoding='latin-1') as f:
                    primeras_lineas = [f.readline() for _ in range(20)]
            except Exception:
                return 'desconocido'

        for linea in primeras_lineas:
            for nombre_patron, patron in cls.PATRONES:
                if patron.match(linea):
                    return nombre_patron

        return 'desconocido'

    @classmethod
    def obtener_estadisticas(cls, ruta: str) -> Dict:
        """
        Obtiene estadísticas básicas del archivo de exportación.

        Args:
            ruta: Ruta al archivo.

        Returns:
            Dict: Estadísticas del archivo.
        """
        stats = {
            'ruta': ruta,
            'tamaño_bytes': 0,
            'total_lineas': 0,
            'total_mensajes': 0,
            'autores_unicos': set(),
            'formato_detectado': 'desconocido',
            'fecha_inicio': None,
            'fecha_fin': None,
        }

        if not os.path.exists(ruta):
            return stats

        stats['tamaño_bytes'] = os.path.getsize(ruta)
        stats['formato_detectado'] = cls.detectar_formato(ruta)

        try:
            mensajes = cls.parsear_archivo(ruta)
            stats['total_mensajes'] = len(mensajes)

            autores = set()
            fechas = []

            for msg in mensajes:
                autores.add(msg['autor'])
                if msg.get('fecha'):
                    fechas.append(msg['fecha'])

            stats['autores_unicos'] = sorted(autores)
            if fechas:
                stats['fecha_inicio'] = min(fechas)
                stats['fecha_fin'] = max(fechas)

        except Exception as e:
            logger.error(f'Error obteniendo estadísticas: {e}')

        return stats

    @staticmethod
    def _extraer_telefono(texto: str) -> str:
        """
        Extrae un número de teléfono de un texto (autor o mensaje).

        Detecta formatos como:
        - +51 958 063 438
        - 958063438
        - 959 032 882
        - 986132898

        Args:
            texto: Texto del cual extraer el teléfono.

        Returns:
            str: Número de teléfono limpio (solo dígitos) o cadena vacía.
        """
        if not texto:
            return ''
        # Limpiar caracteres de control Unicode como ⁨ y ⁩ que aparecen en menciones
        limpio = re.sub(r'[\u2068\u2069\u200e\u200f]', '', texto)
        # Buscar patrón de teléfono: +51 seguido de 9 dígitos, o 9 dígitos
        patron_telefono = re.compile(
            r'(?:\+51)?\s*(\d{3})\s*(\d{3})\s*(\d{3})'
        )
        match = patron_telefono.search(limpio)
        if match:
            return f"+51 {match.group(1)} {match.group(2)} {match.group(3)}"
        # Intentar solo dígitos (mínimo 7)
        solo_digitos = re.sub(r'\D', '', limpio)
        if len(solo_digitos) >= 7:
            return solo_digitos
        return ''
