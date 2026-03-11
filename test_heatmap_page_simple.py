#!/usr/bin/env python3
"""
Script para probar la página del heatmap y verificar que los componentes clave estén presentes.
"""
import urllib.request
from html.parser import HTMLParser

class HeatmapParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.has_google_maps_script = False
        self.has_heatmap_js = False
        self.has_map_div = False
        self.has_api_key = False
        self.api_key = None
    
    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        
        # Verificar script de Google Maps
        if tag == 'script' and 'src' in attrs_dict:
            src = attrs_dict['src']
            if 'maps.googleapis.com' in src:
                self.has_google_maps_script = True
                if 'key=' in src:
                    self.has_api_key = True
                    # Extraer la clave API
                    import re
                    match = re.search(r'key=([A-Za-z0-9_\-]+)', src)
                    if match:
                        self.api_key = match.group(1)
            
            if 'market_analysis/js/heatmap.js' in src:
                self.has_heatmap_js = True
        
        # Verificar div del mapa
        if tag == 'div' and 'id' in attrs_dict:
            if attrs_dict['id'] == 'heatmapMap':
                self.has_map_div = True

def test_heatmap_page():
    url = 'http://127.0.0.1:8000/market-analysis/heatmap/'
    
    print(f"Probando pagina: {url}")
    print("=" * 60)
    
    try:
        # Hacer la solicitud
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        response = urllib.request.urlopen(req, timeout=10)
        html_content = response.read().decode('utf-8')
        
        # Analizar el HTML
        parser = HeatmapParser()
        parser.feed(html_content)
        
        # Mostrar resultados
        print(f"OK - Pagina cargada correctamente (HTTP {response.status})")
        print(f"OK - Script de Google Maps: {parser.has_google_maps_script}")
        print(f"OK - Script heatmap.js: {parser.has_heatmap_js}")
        print(f"OK - Div del mapa (heatmapMap): {parser.has_map_div}")
        print(f"OK - Clave API en URL: {parser.has_api_key}")
        
        if parser.api_key:
            print(f"   Clave API detectada: {parser.api_key[:20]}...")
        
        # Verificar datos críticos
        if not parser.has_google_maps_script:
            print("ERROR: No se encontro el script de Google Maps")
            return False
            
        if not parser.has_heatmap_js:
            print("ERROR: No se encontro el script heatmap.js")
            return False
            
        if not parser.has_map_div:
            print("ERROR: No se encontro el div del mapa (heatmapMap)")
            return False
        
        # Verificar que no haya errores obvios en el HTML
        if 'Error al cargar Google Maps' in html_content:
            print("ADVERTENCIA: El HTML contiene mensajes de error de Google Maps")
            
        # Verificar que la API key esté presente
        if not parser.has_api_key:
            print("ADVERTENCIA: No se detecto clave API en el script de Google Maps")
            
        print("\n" + "=" * 60)
        print("OK - La pagina parece estar correctamente estructurada")
        print("\nRecomendaciones:")
        print("1. Abrir http://127.0.0.1:8000/market-analysis/heatmap/ en un navegador")
        print("2. Presionar F12 para abrir las herramientas de desarrollador")
        print("3. Verificar la consola para errores de JavaScript")
        print("4. Verificar la pestaña 'Network' para ver si se cargan los recursos")
        
        return True
        
    except Exception as e:
        print(f"ERROR - Error al cargar la pagina: {type(e).__name__}: {e}")
        return False

if __name__ == '__main__':
    test_heatmap_page()