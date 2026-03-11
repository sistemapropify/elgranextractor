#!/usr/bin/env python
"""
Verificación final accediendo al servidor real.
"""
import requests
import re
import time

print("=== VERIFICACIÓN FINAL DEL SERVIDOR ===")
print()

# URL del servidor local
base_url = "http://localhost:8000"

# Caso 1: Solo Propify
url = f"{base_url}/ingestas/propiedades/?fuente_propify=propify"
print(f"Caso 1: Solo Propify seleccionado")
print(f"URL: {url}")
print()

try:
    # Hacer request
    start_time = time.time()
    response = requests.get(url, timeout=30)
    elapsed = time.time() - start_time
    
    print(f"Tiempo de respuesta: {elapsed:.2f} segundos")
    print(f"Status code: {response.status_code}")
    
    if response.status_code == 200:
        content = response.text
        
        # Análisis
        print(f"\n=== RESULTADOS ===")
        
        # Buscar contador
        conteo_match = re.search(r'(\d+)\s*propify', content, re.IGNORECASE)
        if conteo_match:
            conteo = int(conteo_match.group(1))
            print(f"Contador propify en HTML: {conteo}")
            
            if conteo == 0:
                print("¡PROBLEMA: El contador muestra 0 propify!")
            elif conteo == 43:
                print("✓ PERFECTO: El contador muestra 43 propify (todas las propiedades)")
            else:
                print(f"✓ OK: El contador muestra {conteo} propify")
        else:
            print("¡PROBLEMA: No se encontró el contador propify!")
            
        # Buscar tarjetas Propify
        propify_cards = len(re.findall(r'data-es-propify="true"', content))
        print(f"Tarjetas con data-es-propify='true': {propify_cards}")
        
        if propify_cards == 0:
            print("¡PROBLEMA: No hay tarjetas con data-es-propify='true'!")
        elif propify_cards == 12:
            print("✓ PERFECTO: 12 tarjetas Propify en la página (paginación correcta)")
        else:
            print(f"✓ OK: {propify_cards} tarjetas Propify encontradas")
            
        # Buscar texto "Propify" en las tarjetas
        propify_badges = len(re.findall(r'<span[^>]*class="[^"]*badge[^"]*"[^>]*>.*?Propify.*?</span>', content, re.IGNORECASE | re.DOTALL))
        print(f"Badges 'Propify' en tarjetas: {propify_badges}")
        
        # Verificar que las tarjetas Propify tengan coordenadas
        if propify_cards > 0:
            # Extraer primera tarjeta Propify
            propify_match = re.search(r'data-es-propify="true".*?</div>\s*</div>\s*</div>', content, re.DOTALL)
            if propify_match:
                card_html = propify_match.group(0)
                
                # Verificar coordenadas
                lat_match = re.search(r'data-lat="([^"]+)"', card_html)
                lng_match = re.search(r'data-lng="([^"]+)"', card_html)
                
                if lat_match and lng_match:
                    lat = lat_match.group(1)
                    lng = lng_match.group(1)
                    print(f"✓ Coordenadas en tarjeta Propify: lat={lat}, lng={lng}")
                else:
                    print("¡PROBLEMA: Tarjeta Propify no tiene coordenadas!")
                    
                # Verificar ID
                id_match = re.search(r'data-property-id="([^"]+)"', card_html)
                if id_match:
                    print(f"✓ ID de propiedad Propify: {id_match.group(1)}")
                    
        # Verificar mapa JavaScript
        map_markers = len(re.findall(r'addMarker\([^)]*\)', content))
        print(f"Llamadas a addMarker() en JavaScript: {map_markers}")
        
        if map_markers > 0:
            print("✓ JavaScript para mapa está presente")
            
            # Verificar si hay marcadores Propify
            propify_markers = len(re.findall(r'addMarker\([^)]*esPropify[^)]*true[^)]*\)', content))
            if propify_markers > 0:
                print(f"✓ Marcadores Propify en JavaScript: {propify_markers}")
        
        print(f"\n=== RESUMEN ===")
        if propify_cards > 0 and (conteo_match and int(conteo_match.group(1)) > 0):
            print("¡ÉXITO: Las propiedades Propify SÍ se están mostrando en la interfaz!")
            print(f"- {propify_cards} tarjetas Propify visibles")
            print(f"- Contador: {conteo_match.group(1)} propiedades Propify")
            print(f"- Coordenadas presentes para mostrar en mapa")
        else:
            print("¡PROBLEMA: Las propiedades Propify NO se están mostrando correctamente!")
            
    else:
        print(f"ERROR: Status {response.status_code}")
        
except requests.exceptions.Timeout:
    print("¡TIMEOUT! El servidor está tardando demasiado.")
except Exception as e:
    print(f"ERROR: {e}")

print()
print("=== VERIFICACIÓN COMPLETADA ===")