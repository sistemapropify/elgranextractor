"""
Servicio de extracción de texto desde PDFs.
Detecta si el PDF tiene texto nativo o está escaneado (requiere OCR).
"""

import logging
import io
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# Intentar importar bibliotecas de PDF
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    logger.warning("pdfplumber no está instalado. Instalar con: pip install pdfplumber")

try:
    from PyPDF2 import PdfReader
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False
    logger.warning("PyPDF2 no está instalado. Instalar con: pip install PyPDF2")


class ExtractorPDF:
    """
    Extractor de texto desde archivos PDF.
    
    Funcionalidades:
    - Detecta si el PDF tiene texto nativo o es escaneado
    - Extrae texto de PDFs nativos (gratuito)
    - Marca PDFs escaneados para OCR posterior (costo adicional)
    """
    
    # Umbral mínimo de caracteres para considerar que un PDF tiene texto
    UMBRAL_CARACTERES_MINIMO = 100
    
    def __init__(self):
        """Inicializa el extractor de PDFs."""
        self.pdfplumber_disponible = PDFPLUMBER_AVAILABLE
        self.pypdf2_disponible = PYPDF2_AVAILABLE
        
        if not self.pdfplumber_disponible and not self.pypdf2_disponible:
            logger.error("No hay bibliotecas de PDF disponibles. Instalar pdfplumber o PyPDF2")
    
    def extraer_informacion_pdf(
        self, 
        contenido_binario: bytes
    ) -> Dict[str, Any]:
        """
        Extrae información completa de un PDF.
        
        Args:
            contenido_binario: Contenido del PDF en bytes
            
        Returns:
            Diccionario con información extraída:
            {
                'tiene_texto': bool,
                'es_escaneado': bool,
                'texto_extraido': str,
                'num_paginas': int,
                'num_caracteres': int,
                'metadata': dict,
                'error': str (si hubo error)
            }
        """
        resultado = {
            'tiene_texto': False,
            'es_escaneado': False,
            'texto_extraido': '',
            'num_paginas': 0,
            'num_caracteres': 0,
            'metadata': {},
            'error': None,
        }
        
        if not self.pdfplumber_disponible and not self.pypdf2_disponible:
            resultado['error'] = 'No hay bibliotecas de PDF disponibles'
            return resultado
        
        try:
            # Intentar con pdfplumber primero (mejor extracción)
            if self.pdfplumber_disponible:
                return self._extraer_con_pdfplumber(contenido_binario)
            else:
                return self._extraer_con_pypdf2(contenido_binario)
                
        except Exception as e:
            logger.error(f"Error extrayendo información de PDF: {e}")
            resultado['error'] = str(e)
            return resultado
    
    def _extraer_con_pdfplumber(self, contenido_binario: bytes) -> Dict[str, Any]:
        """
        Extrae texto usando pdfplumber (recomendado).
        
        Args:
            contenido_binario: Contenido del PDF en bytes
            
        Returns:
            Diccionario con información extraída
        """
        resultado = {
            'tiene_texto': False,
            'es_escaneado': False,
            'texto_extraido': '',
            'num_paginas': 0,
            'num_caracteres': 0,
            'metadata': {},
            'error': None,
        }
        
        try:
            # Crear objeto de archivo en memoria
            pdf_file = io.BytesIO(contenido_binario)
            
            # Abrir PDF con pdfplumber
            with pdfplumber.open(pdf_file) as pdf:
                resultado['num_paginas'] = len(pdf.pages)
                
                # Extraer metadata si está disponible
                if pdf.metadata:
                    resultado['metadata'] = {
                        'title': pdf.metadata.get('Title', ''),
                        'author': pdf.metadata.get('Author', ''),
                        'subject': pdf.metadata.get('Subject', ''),
                        'creator': pdf.metadata.get('Creator', ''),
                        'producer': pdf.metadata.get('Producer', ''),
                    }
                
                # Extraer texto de todas las páginas
                textos_paginas = []
                for i, pagina in enumerate(pdf.pages):
                    try:
                        texto_pagina = pagina.extract_text()
                        if texto_pagina:
                            textos_paginas.append(texto_pagina)
                    except Exception as e:
                        logger.warning(f"Error extrayendo texto de página {i+1}: {e}")
                        continue
                
                # Combinar texto de todas las páginas
                texto_completo = '\n\n'.join(textos_paginas)
                resultado['texto_extraido'] = texto_completo
                resultado['num_caracteres'] = len(texto_completo)
                
                # Determinar si tiene texto nativo o está escaneado
                if resultado['num_caracteres'] >= self.UMBRAL_CARACTERES_MINIMO:
                    resultado['tiene_texto'] = True
                    resultado['es_escaneado'] = False
                else:
                    resultado['tiene_texto'] = False
                    resultado['es_escaneado'] = True
                
                logger.info(
                    f"PDF procesado: {resultado['num_paginas']} páginas, "
                    f"{resultado['num_caracteres']} caracteres, "
                    f"{'nativo' if resultado['tiene_texto'] else 'escaneado'}"
                )
                
        except Exception as e:
            logger.error(f"Error en _extraer_con_pdfplumber: {e}")
            resultado['error'] = str(e)
        
        return resultado
    
    def _extraer_con_pypdf2(self, contenido_binario: bytes) -> Dict[str, Any]:
        """
        Extrae texto usando PyPDF2 (alternativa).
        
        Args:
            contenido_binario: Contenido del PDF en bytes
            
        Returns:
            Diccionario con información extraída
        """
        resultado = {
            'tiene_texto': False,
            'es_escaneado': False,
            'texto_extraido': '',
            'num_paginas': 0,
            'num_caracteres': 0,
            'metadata': {},
            'error': None,
        }
        
        try:
            # Crear objeto de archivo en memoria
            pdf_file = io.BytesIO(contenido_binario)
            
            # Crear lector PDF
            reader = PdfReader(pdf_file)
            resultado['num_paginas'] = len(reader.pages)
            
            # Extraer metadata
            if reader.metadata:
                resultado['metadata'] = {
                    'title': reader.metadata.get('/Title', ''),
                    'author': reader.metadata.get('/Author', ''),
                    'subject': reader.metadata.get('/Subject', ''),
                    'creator': reader.metadata.get('/Creator', ''),
                    'producer': reader.metadata.get('/Producer', ''),
                }
            
            # Extraer texto de todas las páginas
            textos_paginas = []
            for i, pagina in enumerate(reader.pages):
                try:
                    texto_pagina = pagina.extract_text()
                    if texto_pagina:
                        textos_paginas.append(texto_pagina)
                except Exception as e:
                    logger.warning(f"Error extrayendo texto de página {i+1}: {e}")
                    continue
            
            # Combinar texto
            texto_completo = '\n\n'.join(textos_paginas)
            resultado['texto_extraido'] = texto_completo
            resultado['num_caracteres'] = len(texto_completo)
            
            # Determinar tipo
            if resultado['num_caracteres'] >= self.UMBRAL_CARACTERES_MINIMO:
                resultado['tiene_texto'] = True
                resultado['es_escaneado'] = False
            else:
                resultado['tiene_texto'] = False
                resultado['es_escaneado'] = True
            
            logger.info(
                f"PDF procesado con PyPDF2: {resultado['num_paginas']} páginas, "
                f"{resultado['num_caracteres']} caracteres"
            )
            
        except Exception as e:
            logger.error(f"Error en _extraer_con_pypdf2: {e}")
            resultado['error'] = str(e)
        
        return resultado
    
    def validar_pdf(self, contenido_binario: bytes) -> Tuple[bool, Optional[str]]:
        """
        Valida si el contenido es un PDF válido.
        
        Args:
            contenido_binario: Contenido a validar
            
        Returns:
            Tupla (es_valido, mensaje_error)
        """
        if not contenido_binario:
            return False, "Contenido vacío"
        
        # Verificar firma PDF (%PDF-)
        if not contenido_binario.startswith(b'%PDF-'):
            return False, "No tiene firma PDF válida"
        
        # Verificar tamaño mínimo
        if len(contenido_binario) < 100:
            return False, "Archivo demasiado pequeño para ser un PDF válido"
        
        # Intentar abrir con biblioteca
        try:
            if self.pdfplumber_disponible:
                pdf_file = io.BytesIO(contenido_binario)
                with pdfplumber.open(pdf_file) as pdf:
                    _ = len(pdf.pages)  # Verificar que se pueda leer
                return True, None
            elif self.pypdf2_disponible:
                pdf_file = io.BytesIO(contenido_binario)
                reader = PdfReader(pdf_file)
                _ = len(reader.pages)
                return True, None
            else:
                # Sin bibliotecas, solo verificar firma
                return True, None
        except Exception as e:
            return False, f"Error al validar PDF: {str(e)}"
    
    def extraer_metadatos_rapido(self, contenido_binario: bytes) -> Dict[str, Any]:
        """
        Extrae solo metadatos sin procesar todo el contenido (rápido).
        
        Args:
            contenido_binario: Contenido del PDF
            
        Returns:
            Diccionario con metadatos básicos
        """
        metadatos = {
            'num_paginas': 0,
            'tamaño_bytes': len(contenido_binario),
            'es_pdf_valido': False,
        }
        
        try:
            pdf_file = io.BytesIO(contenido_binario)
            
            if self.pdfplumber_disponible:
                with pdfplumber.open(pdf_file) as pdf:
                    metadatos['num_paginas'] = len(pdf.pages)
                    metadatos['es_pdf_valido'] = True
            elif self.pypdf2_disponible:
                reader = PdfReader(pdf_file)
                metadatos['num_paginas'] = len(reader.pages)
                metadatos['es_pdf_valido'] = True
                
        except Exception as e:
            logger.error(f"Error extrayendo metadatos rápidos: {e}")
        
        return metadatos
    
    def necesita_ocr(self, info_pdf: Dict[str, Any]) -> bool:
        """
        Determina si un PDF necesita OCR basado en la información extraída.
        
        Args:
            info_pdf: Información extraída del PDF
            
        Returns:
            True si necesita OCR, False si no
        """
        return info_pdf.get('es_escaneado', False) or not info_pdf.get('tiene_texto', False)
    
    def generar_resumen_extraccion(self, info_pdf: Dict[str, Any]) -> str:
        """
        Genera un resumen legible de la extracción.
        
        Args:
            info_pdf: Información extraída
            
        Returns:
            Resumen en texto
        """
        if info_pdf.get('error'):
            return f"Error: {info_pdf['error']}"
        
        tipo = 'PDF Nativo' if info_pdf.get('tiene_texto') else 'PDF Escaneado'
        paginas = info_pdf.get('num_paginas', 0)
        caracteres = info_pdf.get('num_caracteres', 0)
        
        resumen = f"{tipo} - {paginas} página(s)"
        
        if info_pdf.get('tiene_texto'):
            resumen += f" - {caracteres} caracteres extraídos"
        else:
            resumen += " - Requiere OCR"
        
        return resumen


# Función de utilidad para uso directo
def extraer_texto_pdf(contenido_binario: bytes) -> Dict[str, Any]:
    """
    Función de utilidad para extraer texto de un PDF.
    
    Args:
        contenido_binario: Contenido del PDF en bytes
        
    Returns:
        Diccionario con información extraída
    """
    extractor = ExtractorPDF()
    return extractor.extraer_informacion_pdf(contenido_binario)
