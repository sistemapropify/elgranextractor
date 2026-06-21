"""
Servicio de detección de tipos de contenido para el sistema de captura.
Identifica el tipo de documento basado en URL, headers HTTP y contenido.
"""

import logging
import mimetypes
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urlparse
import re

logger = logging.getLogger(__name__)


class DetectorTiposContenido:
    """
    Detector de tipos de contenido para clasificar documentos capturados.
    
    Identifica:
    - SEMILLA_LISTADO: Páginas con múltiples enlaces
    - DOCUMENTO_DIRECTO_HTML: Artículo o página individual
    - DOCUMENTO_DIRECTO_PDF: PDF individual
    - API_FEED: RSS, JSON, XML
    """
    
    # Patrones de URL que indican listados/búsquedas
    PATRONES_LISTADO = [
        r'\?s=',  # Búsqueda WordPress
        r'/search',
        r'/buscar',
        r'/listado',
        r'/catalogo',
        r'/archivo',
        r'/category',
        r'/tag',
        r'\?page=',
        r'/page/',
        r'\?q=',
        r'/resultados',
    ]
    
    # Patrones que sugieren contenido individual
    PATRONES_ARTICULO = [
        r'/\d{4}/\d{2}/\d{2}/',  # Fecha en URL (blogs)
        r'/(articulo|post|noticia|proyecto)/',
        r'-\d+\.html?$',  # ID numérico al final
        r'/id/\d+',
    ]
    
    # Content-types conocidos
    CONTENT_TYPES_PDF = [
        'application/pdf',
        'application/x-pdf',
    ]
    
    CONTENT_TYPES_HTML = [
        'text/html',
        'application/xhtml+xml',
    ]
    
    CONTENT_TYPES_JSON = [
        'application/json',
        'application/ld+json',
    ]
    
    CONTENT_TYPES_XML = [
        'application/xml',
        'text/xml',
        'application/rss+xml',
        'application/atom+xml',
    ]
    
    def detectar_tipo_desde_url(self, url: str) -> str:
        """
        Detecta el tipo de fuente basándose solo en la URL.
        
        Args:
            url: URL a analizar
            
        Returns:
            Tipo detectado: 'semilla_listado', 'documento_directo_html', 
                           'documento_directo_pdf', 'api_feed'
        """
        url_lower = url.lower()
        
        # Verificar si es PDF por extensión
        if url_lower.endswith('.pdf'):
            return 'documento_directo_pdf'
        
        # Verificar si es feed por extensión
        if url_lower.endswith(('.xml', '.rss', '.atom', '.json')):
            return 'api_feed'
        
        # Verificar patrones de listado
        for patron in self.PATRONES_LISTADO:
            if re.search(patron, url_lower):
                return 'semilla_listado'
        
        # Verificar patrones de artículo individual
        for patron in self.PATRONES_ARTICULO:
            if re.search(patron, url_lower):
                return 'documento_directo_html'
        
        # Por defecto, asumir listado (para portales)
        return 'semilla_listado'
    
    def detectar_tipo_desde_headers(
        self, 
        content_type: str, 
        headers: Optional[Dict[str, str]] = None
    ) -> Tuple[str, str]:
        """
        Detecta el tipo de documento desde los headers HTTP.
        
        Args:
            content_type: Header Content-Type
            headers: Diccionario completo de headers (opcional)
            
        Returns:
            Tupla (tipo_fuente, tipo_documento)
        """
        if not content_type:
            return 'documento_directo_html', 'html'
        
        content_type_lower = content_type.lower()
        
        # Detectar PDF
        if any(ct in content_type_lower for ct in self.CONTENT_TYPES_PDF):
            return 'documento_directo_pdf', 'pdf_nativo'
        
        # Detectar JSON
        if any(ct in content_type_lower for ct in self.CONTENT_TYPES_JSON):
            return 'api_feed', 'json'
        
        # Detectar XML/RSS
        if any(ct in content_type_lower for ct in self.CONTENT_TYPES_XML):
            return 'api_feed', 'xml'
        
        # Detectar HTML
        if any(ct in content_type_lower for ct in self.CONTENT_TYPES_HTML):
            # Necesitaríamos analizar contenido para saber si es listado o artículo
            return 'documento_directo_html', 'html'
        
        # Por defecto
        return 'documento_directo_html', 'otro'
    
    def detectar_tipo_completo(
        self, 
        url: str, 
        content_type: Optional[str] = None,
        contenido: Optional[bytes] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Detección completa del tipo de contenido usando todas las fuentes disponibles.
        
        Args:
            url: URL del contenido
            content_type: Content-Type del response HTTP
            contenido: Contenido descargado (bytes)
            headers: Headers HTTP completos
            
        Returns:
            Diccionario con información de detección:
            {
                'tipo_fuente': 'semilla_listado' | 'documento_directo_html' | ...,
                'tipo_documento': 'html' | 'pdf_nativo' | 'json' | ...,
                'confianza': 'alta' | 'media' | 'baja',
                'es_listado': bool,
                'requiere_analisis_contenido': bool
            }
        """
        resultado = {
            'tipo_fuente': None,
            'tipo_documento': None,
            'confianza': 'baja',
            'es_listado': False,
            'requiere_analisis_contenido': False,
        }
        
        # 1. Detección por headers (más confiable)
        if content_type:
            tipo_fuente, tipo_doc = self.detectar_tipo_desde_headers(content_type, headers)
            resultado['tipo_fuente'] = tipo_fuente
            resultado['tipo_documento'] = tipo_doc
            
            # Si es PDF, JSON o XML, alta confianza
            if tipo_doc in ['pdf_nativo', 'json', 'xml']:
                resultado['confianza'] = 'alta'
                resultado['es_listado'] = False
                return resultado
            
            resultado['confianza'] = 'media'
        
        # 2. Detección por URL
        tipo_url = self.detectar_tipo_desde_url(url)
        
        # Si coinciden, aumentar confianza
        if resultado['tipo_fuente'] == tipo_url:
            resultado['confianza'] = 'alta'
        else:
            # URL tiene prioridad para distinguir listado vs artículo en HTML
            if resultado['tipo_documento'] == 'html':
                resultado['tipo_fuente'] = tipo_url
                resultado['confianza'] = 'media'
        
        # 3. Detección por contenido (si está disponible)
        if contenido and resultado['tipo_documento'] == 'html':
            es_listado = self._analizar_si_es_listado(contenido)
            resultado['es_listado'] = es_listado
            
            if es_listado:
                resultado['tipo_fuente'] = 'semilla_listado'
                resultado['confianza'] = 'alta'
            else:
                resultado['tipo_fuente'] = 'documento_directo_html'
                resultado['confianza'] = 'alta'
        elif resultado['tipo_documento'] == 'html':
            # HTML sin contenido para analizar
            resultado['requiere_analisis_contenido'] = True
        
        # Valores por defecto si aún no están definidos
        if not resultado['tipo_fuente']:
            resultado['tipo_fuente'] = 'documento_directo_html'
        if not resultado['tipo_documento']:
            resultado['tipo_documento'] = 'html'
        
        return resultado
    
    def _analizar_si_es_listado(self, contenido: bytes) -> bool:
        """
        Analiza el contenido HTML para determinar si es un listado o artículo individual.
        
        Args:
            contenido: Contenido HTML en bytes
            
        Returns:
            True si es un listado, False si es artículo individual
        """
        try:
            # Decodificar contenido
            try:
                html = contenido.decode('utf-8')
            except UnicodeDecodeError:
                html = contenido.decode('latin-1', errors='ignore')
            
            html_lower = html.lower()
            
            # Contar elementos que sugieren listado
            num_articulos = html_lower.count('<article')
            num_items_lista = html_lower.count('class="item"') + html_lower.count('class="post"')
            num_enlaces_internos = html_lower.count('<a href')
            
            # Si tiene muchos artículos o items, probablemente es listado
            if num_articulos > 3 or num_items_lista > 5:
                return True
            
            # Si tiene muchos enlaces, probablemente es listado
            if num_enlaces_internos > 20:
                # Verificar si tiene paginación
                tiene_paginacion = any(palabra in html_lower for palabra in 
                                      ['pagination', 'paginación', 'next page', 'página siguiente'])
                if tiene_paginacion:
                    return True
            
            # Buscar indicadores de artículo individual
            tiene_contenido_articulo = any(clase in html_lower for clase in 
                                          ['entry-content', 'post-content', 'article-body', 
                                           'main-content', 'content-area'])
            
            if tiene_contenido_articulo and num_articulos <= 1:
                return False
            
            # Por defecto, si hay múltiples enlaces, asumir listado
            return num_enlaces_internos > 15
            
        except Exception as e:
            logger.error(f"Error analizando contenido HTML: {e}")
            return False
    
    def clasificar_categoria_semantica(
        self, 
        url: str, 
        titulo: Optional[str] = None,
        contenido: Optional[str] = None
    ) -> str:
        """
        Clasifica el documento en una categoría semántica.
        
        Categorías:
        - oferta: Ofertas de propiedades
        - legal: Normativa y leyes
        - infraestructura: Obras públicas
        - inteligencia: Análisis de mercado
        - riesgo: Contexto socio-ambiental
        - actores: Constructoras y agentes
        
        Args:
            url: URL del documento
            titulo: Título del documento (opcional)
            contenido: Contenido del documento (opcional)
            
        Returns:
            Categoría detectada
        """
        texto = f"{url} {titulo or ''} {contenido[:500] if contenido else ''}".lower()
        
        # Palabras clave por categoría
        keywords = {
            'legal': [
                'ley', 'decreto', 'ordenanza', 'resolución', 'norma', 'reglamento',
                'congreso', 'municipalidad', 'oficial', 'legal', 'jurídico'
            ],
            'oferta': [
                'venta', 'alquiler', 'precio', 'm²', 'dormitorios', 'baños',
                'inmueble', 'propiedad', 'departamento', 'casa', 'terreno'
            ],
            'infraestructura': [
                'obra', 'proyecto', 'construcción', 'vía', 'carretera', 'puente',
                'metro', 'infraestructura', 'desarrollo', 'urbanización'
            ],
            'inteligencia': [
                'análisis', 'mercado', 'tendencia', 'estudio', 'informe',
                'investigación', 'estadística', 'precios', 'demanda'
            ],
            'riesgo': [
                'desastre', 'conflicto', 'riesgo', 'emergencia', 'indeci',
                'peligro', 'problema', 'crisis', 'protesta'
            ],
            'actores': [
                'constructora', 'inmobiliaria', 'empresa', 'desarrollador',
                'inversionista', 'grupo', 'compañía'
            ],
        }
        
        # Contar coincidencias por categoría
        puntuaciones = {}
        for categoria, palabras in keywords.items():
            puntuacion = sum(1 for palabra in palabras if palabra in texto)
            puntuaciones[categoria] = puntuacion
        
        # Verificar dominios específicos
        if any(d in url for d in ['elperuano.pe', 'congreso.gob.pe', 'gob.pe']):
            puntuaciones['legal'] = puntuaciones.get('legal', 0) + 5
        
        if any(d in url for d in ['urbania.pe', 'adondevivir.com', 'properati']):
            puntuaciones['oferta'] = puntuaciones.get('oferta', 0) + 5
        
        # Retornar categoría con mayor puntuación
        if puntuaciones:
            categoria_detectada = max(puntuaciones.items(), key=lambda x: x[1])
            if categoria_detectada[1] > 0:
                return categoria_detectada[0]
        
        # Por defecto
        return 'inteligencia'
