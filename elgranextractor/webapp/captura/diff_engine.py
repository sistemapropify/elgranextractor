"""
Motor de diferencias para comparar contenido web y detectar cambios.

Este módulo proporciona funcionalidades avanzadas para comparar dos capturas
de contenido web, detectar cambios significativos y generar análisis detallados
de las diferencias.
"""

import re
import difflib
import hashlib
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import json

from .models import CapturaCruda, EventoDeteccion


@dataclass
class FragmentoCambiado:
    """Representa un fragmento específico que ha cambiado entre dos versiones."""
    tipo: str  # 'texto', 'enlace', 'imagen', 'estructura'
    contenido_anterior: str
    contenido_nuevo: str
    contexto_anterior: str
    contexto_nuevo: str
    posicion_linea: Optional[Tuple[int, int]] = None
    relevancia: float = 0.0  # 0-1, donde 1 es más relevante


@dataclass
class ResultadoComparacion:
    """Resultado completo de la comparación entre dos capturas."""
    captura_anterior: CapturaCruda
    captura_nueva: CapturaCruda
    similitud_porcentaje: float
    tipo_cambio: str
    severidad: str
    metricas: Dict[str, Any]
    fragmentos_cambiados: List[FragmentoCambiado]
    resumen_cambio: str
    hash_comparacion: str


class MotorDiferencias:
    """
    Motor principal para comparar contenido web y detectar cambios.
    
    Implementa múltiples estrategias de comparación:
    1. Comparación por hash (rápida)
    2. Comparación de texto limpio
    3. Comparación estructural (HTML)
    4. Comparación semántica (palabras clave)
    """
    
    def __init__(self, umbral_cambio_significativo: float = 0.95):
        """
        Inicializa el motor de diferencias.
        
        Args:
            umbral_cambio_significativo: Porcentaje de similitud por debajo del cual
                se considera un cambio significativo (0-1).
        """
        self.umbral_cambio_significativo = umbral_cambio_significativo
        
        # Patrones regex para análisis de contenido
        self.patron_enlaces = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
        self.patron_imagenes = re.compile(r'src=["\']([^"\']+)["\']', re.IGNORECASE)
        self.patron_scripts = re.compile(r'<script[^>]*>.*?</script>', re.DOTALL | re.IGNORECASE)
        self.patron_estilos = re.compile(r'<style[^>]*>.*?</style>', re.DOTALL | re.IGNORECASE)
        self.patron_comentarios = re.compile(r'<!--.*?-->', re.DOTALL)
        self.patron_etiquetas_html = re.compile(r'<[^>]+>')
        
    def comparar_capturas(self, captura_anterior: CapturaCruda, 
                         captura_nueva: CapturaCruda) -> ResultadoComparacion:
        """
        Compara dos capturas y genera un análisis detallado de las diferencias.
        
        Args:
            captura_anterior: Captura más antigua
            captura_nueva: Captura más reciente
            
        Returns:
            ResultadoComparacion con análisis completo
        """
        # Verificación básica
        if captura_anterior.fuente != captura_nueva.fuente:
            raise ValueError("Las capturas deben ser de la misma fuente")
        
        # 1. Comparación rápida por hash
        if captura_anterior.hash_sha256 == captura_nueva.hash_sha256:
            return self._crear_resultado_sin_cambios(captura_anterior, captura_nueva)
        
        # 2. Extraer y limpiar contenido
        contenido_anterior = self._limpiar_contenido(captura_anterior.contenido_html)
        contenido_nuevo = self._limpiar_contenido(captura_nueva.contenido_html)
        
        # 3. Calcular similitud
        similitud = self._calcular_similitud(contenido_anterior, contenido_nuevo)
        
        # 4. Determinar tipo de cambio
        tipo_cambio = self._determinar_tipo_cambio(
            contenido_anterior, contenido_nuevo, similitud
        )
        
        # 5. Extraer fragmentos cambiados
        fragmentos = self._extraer_fragmentos_cambiados(
            contenido_anterior, contenido_nuevo
        )
        
        # 6. Calcular métricas detalladas
        metricas = self._calcular_metricas_detalladas(
            captura_anterior, captura_nueva, contenido_anterior, contenido_nuevo
        )
        
        # 7. Determinar severidad
        severidad = self._determinar_severidad(similitud, tipo_cambio, metricas)
        
        # 8. Generar resumen
        resumen = self._generar_resumen_cambio(
            similitud, tipo_cambio, severidad, metricas, fragmentos
        )
        
        # 9. Crear hash de comparación
        hash_comparacion = self._generar_hash_comparacion(
            captura_anterior, captura_nueva, similitud
        )
        
        return ResultadoComparacion(
            captura_anterior=captura_anterior,
            captura_nueva=captura_nueva,
            similitud_porcentaje=similitud * 100,
            tipo_cambio=tipo_cambio,
            severidad=severidad,
            metricas=metricas,
            fragmentos_cambiados=fragmentos,
            resumen_cambio=resumen,
            hash_comparacion=hash_comparacion
        )
    
    def _limpiar_contenido(self, contenido_html: str) -> str:
        """
        Limpia el contenido HTML para comparación.
        
        Args:
            contenido_html: Contenido HTML crudo
            
        Returns:
            Contenido limpio para comparación
        """
        if not contenido_html:
            return ""
        
        # 1. Eliminar scripts y estilos
        contenido = self.patron_scripts.sub('', contenido_html)
        contenido = self.patron_estilos.sub('', contenido)
        
        # 2. Eliminar comentarios HTML
        contenido = self.patron_comentarios.sub('', contenido)
        
        # 3. Extraer texto (opcional, dependiendo del tipo de comparación)
        # Para comparación estructural, mantenemos las etiquetas
        # Para comparación de texto, las eliminamos
        
        # 4. Normalizar espacios en blanco
        contenido = re.sub(r'\s+', ' ', contenido)
        
        # 5. Convertir a minúsculas (para comparación case-insensitive)
        contenido = contenido.lower()
        
        return contenido.strip()
    
    def _calcular_similitud(self, texto1: str, texto2: str) -> float:
        """
        Calcula la similitud entre dos textos usando SequenceMatcher.
        
        Args:
            texto1: Primer texto
            texto2: Segundo texto
            
        Returns:
            Porcentaje de similitud (0-1)
        """
        if not texto1 or not texto2:
            return 0.0
        
        # Usar difflib para calcular similitud
        matcher = difflib.SequenceMatcher(None, texto1, texto2)
        return matcher.ratio()
    
    def _determinar_tipo_cambio(self, contenido_anterior: str, 
                               contenido_nuevo: str, similitud: float) -> str:
        """
        Determina el tipo de cambio basado en el análisis del contenido.
        
        Args:
            contenido_anterior: Contenido anterior limpio
            contenido_nuevo: Contenido nuevo limpio
            similitud: Porcentaje de similitud
            
        Returns:
            Tipo de cambio ('contenido', 'estructura', 'enlaces', 'metadatos', 'error')
        """
        # Extraer enlaces de ambos contenidos
        enlaces_anterior = set(self.patron_enlaces.findall(contenido_anterior))
        enlaces_nuevo = set(self.patron_enlaces.findall(contenido_nuevo))
        
        # Extraer imágenes
        imagenes_anterior = set(self.patron_imagenes.findall(contenido_anterior))
        imagenes_nuevo = set(self.patron_imagenes.findall(contenido_nuevo))
        
        # Calcular diferencias
        enlaces_agregados = enlaces_nuevo - enlaces_anterior
        enlaces_eliminados = enlaces_anterior - enlaces_nuevo
        imagenes_agregadas = imagenes_nuevo - imagenes_anterior
        imagenes_eliminadas = imagenes_anterior - imagenes_nuevo
        
        # Determinar tipo basado en las diferencias
        if similitud < 0.5:
            return 'estructura'  # Cambio estructural significativo
        
        if len(enlaces_agregados) > 5 or len(enlaces_eliminados) > 5:
            return 'enlaces'  # Cambio masivo en enlaces
        
        if len(imagenes_agregadas) > 3 or len(imagenes_eliminadas) > 3:
            return 'estructura'  # Cambio significativo en imágenes
        
        # Extraer estructura de etiquetas
        etiquetas_anterior = self._extraer_estructura_etiquetas(contenido_anterior)
        etiquetas_nuevo = self._extraer_estructura_etiquetas(contenido_nuevo)
        
        if etiquetas_anterior != etiquetas_nuevo:
            return 'estructura'
        
        # Por defecto, cambio de contenido
        return 'contenido'
    
    def _extraer_estructura_etiquetas(self, contenido: str) -> List[str]:
        """
        Extrae la estructura de etiquetas HTML del contenido.
        
        Args:
            contenido: Contenido HTML limpio
            
        Returns:
            Lista de etiquetas en orden de aparición
        """
        # Encontrar todas las etiquetas HTML
        etiquetas = self.patron_etiquetas_html.findall(contenido)
        
        # Extraer solo los nombres de las etiquetas (sin atributos)
        nombres_etiquetas = []
        for etiqueta in etiquetas:
            # Extraer nombre de etiqueta (primer palabra después de <)
            match = re.match(r'<([^\s>/]+)', etiqueta)
            if match:
                nombres_etiquetas.append(match.group(1).lower())
        
        return nombres_etiquetas
    
    def _extraer_fragmentos_cambiados(self, contenido_anterior: str, 
                                     contenido_nuevo: str) -> List[FragmentoCambiado]:
        """
        Extrae fragmentos específicos que han cambiado entre dos versiones.
        
        Args:
            contenido_anterior: Contenido anterior
            contenido_nuevo: Contenido nuevo
            
        Returns:
            Lista de FragmentoCambiado
        """
        fragmentos = []
        
        # Usar difflib para obtener diferencias detalladas
        differ = difflib.Differ()
        diff = list(differ.compare(
            contenido_anterior.splitlines(),
            contenido_nuevo.splitlines()
        ))
        
        # Procesar diferencias
        lineas_anterior = contenido_anterior.splitlines()
        lineas_nuevo = contenido_nuevo.splitlines()
        
        for i, (linea_ant, linea_nueva) in enumerate(zip(lineas_anterior, lineas_nuevo)):
            if linea_ant != linea_nueva:
                # Determinar tipo de cambio en esta línea
                tipo = self._determinar_tipo_cambio_linea(linea_ant, linea_nueva)
                
                # Extraer contexto (líneas anteriores y posteriores)
                contexto_ant = self._extraer_contexto(lineas_anterior, i)
                contexto_nuevo = self._extraer_contexto(lineas_nuevo, i)
                
                fragmento = FragmentoCambiado(
                    tipo=tipo,
                    contenido_anterior=linea_ant,
                    contenido_nuevo=linea_nueva,
                    contexto_anterior=contexto_ant,
                    contexto_nuevo=contexto_nuevo,
                    posicion_linea=(i, i),
                    relevancia=self._calcular_relevancia_cambio(linea_ant, linea_nueva)
                )
                fragmentos.append(fragmento)
        
        # Limitar a los fragmentos más relevantes
        fragmentos.sort(key=lambda x: x.relevancia, reverse=True)
        return fragmentos[:10]  # Devolver solo los 10 más relevantes
    
    def _determinar_tipo_cambio_linea(self, linea_ant: str, linea_nueva: str) -> str:
        """
        Determina el tipo de cambio en una línea específica.
        
        Args:
            linea_ant: Línea anterior
            linea_nueva: Línea nueva
            
        Returns:
            Tipo de cambio ('texto', 'enlace', 'imagen', 'estructura')
        """
        # Verificar si es un enlace
        if 'href=' in linea_ant or 'href=' in linea_nueva:
            return 'enlace'
        
        # Verificar si es una imagen
        if 'src=' in linea_ant or 'src=' in linea_nueva:
            return 'imagen'
        
        # Verificar si es una etiqueta HTML
        if '<' in linea_ant or '<' in linea_nueva:
            return 'estructura'
        
        # Por defecto, texto
        return 'texto'
    
    def _extraer_contexto(self, lineas: List[str], indice: int, 
                         lineas_contexto: int = 2) -> str:
        """
        Extrae contexto alrededor de una línea específica.
        
        Args:
            lineas: Lista de líneas
            indice: Índice de la línea central
            lineas_contexto: Número de líneas de contexto a cada lado
            
        Returns:
            Contexto como string
        """
        inicio = max(0, indice - lineas_contexto)
        fin = min(len(lineas), indice + lineas_contexto + 1)
        return '\n'.join(lineas[inicio:fin])
    
    def _calcular_relevancia_cambio(self, contenido_ant: str, contenido_nuevo: str) -> float:
        """
        Calcula la relevancia de un cambio (0-1).
        
        Args:
            contenido_ant: Contenido anterior
            contenido_nuevo: Contenido nuevo
            
        Returns:
            Puntuación de relevancia
        """
        # Factores de relevancia
        factores = []
        
        # 1. Longitud del cambio
        len_ant = len(contenido_ant)
        len_nuevo = len(contenido_nuevo)
        cambio_longitud = abs(len_nuevo - len_ant) / max(len_ant, len_nuevo, 1)
        factores.append(cambio_longitud)
        
        # 2. Presencia de palabras clave importantes
        palabras_clave = ['precio', 'oferta', 'disponible', 'contacto', 'teléfono', 'email']
        contiene_palabra_clave = any(
            palabra in contenido_ant.lower() or palabra in contenido_nuevo.lower()
            for palabra in palabras_clave
        )
        factores.append(1.0 if contiene_palabra_clave else 0.3)
        
        # 3. Tipo de contenido
        if 'href=' in contenido_ant or 'href=' in contenido_nuevo:
            factores.append(0.8)  # Enlaces son importantes
        elif 'src=' in contenido_ant or 'src=' in contenido_nuevo:
            factores.append(0.7)  # Imágenes son moderadamente importantes
        elif '<' in contenido_ant or '<' in contenido_nuevo:
            factores.append(0.6)  # Estructura HTML
        else:
            factores.append(0.4)  # Texto plano
        
        # Promedio ponderado
        pesos = [0.4, 0.3, 0.3]  # Ponderaciones
        relevancia = sum(f * p for f, p in zip(factores, pesos))
        
        return min(1.0, relevancia)
    
    def _calcular_metricas_detalladas(self, captura_ant: CapturaCruda,
                                     captura_nueva: CapturaCruda,
                                     contenido_ant: str, contenido_nuevo: str) -> Dict[str, Any]:
        """
        Calcula métricas detalladas de la comparación.
        
        Args:
            captura_ant: Captura anterior
            captura_nueva: Captura nueva
            contenido_ant: Contenido anterior limpio
            contenido_nuevo: Contenido nuevo limpio
            
        Returns:
            Diccionario con métricas detalladas
        """
        metricas = {}
        
        # Métricas básicas de las capturas
        metricas['palabras_anterior'] = captura_ant.num_palabras or 0
        metricas['palabras_nueva'] = captura_nueva
