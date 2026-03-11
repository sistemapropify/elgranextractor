#!/usr/bin/env python
"""
Acceso directo al servidor local para verificar qué está pasando.
"""
import requests
import re
import time

print("=== ACCESO DIRECTO AL SERVIDOR LOCAL ===")
print()

# URL del servidor local
base_url = "http://localhost:8000"
url = f"{base_url}/ingestas/propiedades/?fuente_propify=propify"

print(f"Accediendo a: {url}")
print()

try:
    # Hacer request con timeout corto
    start_time = time.time()
    response = requests.get(url, timeout=30)
    elapsed = time.time() - start_time
    
    print(f"Tiempo de respuesta: {elapsed:.2f} segundos")
    print(f"Status code: {response.status_code}")
    
    if response.status_code == 200:
        content = response.text
        
        # Análisis rápido
        print(f"\n=== ANÁLISIS RÁPIDO ===")
        print(f"Tamaño HTML: {len(content)} caracteres")
        
        # Buscar contador
        conteo_match = re.search(r'(\d+)\s*propify', content, re.IGNORECASE)
        if conteo_match:
            print(f"Contador propify: {conteo_match.group(1)}")
        else:
            print("Contador NO encontrado")
            
        # Buscar tarjetas
        property_cards = len(re.findall(r'class="property-card"', content))
        print(f"Tarjetas de propiedades: {property_cards}")
        
        propify_cards = len(re.findall(r'data-es-propify="true"', content))
        print(f"Tarjetas con data-es-propify='true': {propify_cards}")
        
        # Buscar texto "Propify"
        propify_text = len(re.findall(r'Propify', content, re.IGNORECASE))
        print(f"Texto 'Propify' aparece {propify_text} veces")
        
        # Verificar si hay propiedades
        if property_cards == 0:
            print("\n¡CRÍTICO: NO HAY TARJETAS DE PROPIEDADES!")
            
            # Buscar mensaje de error o vacío
            if 'No hay propiedades' in content or 'empty-state' in content:
                print("Se encontró mensaje de 'no hay propiedades'")
            
            # Extraer fragmento para ver qué hay
            print("\nFragmento del HTML (primeros 1000 chars):")
            print(content[:1000])
        else:
            print(f"\nSe encontraron {property_cards} tarjetas de propiedades")
            
            # Extraer primera tarjeta
            card_match = re.search(r'<div[^>]*class="property-card"[^>]*>.*?</div>\s*</div>\s*</div>', content, re.DOTALL)
            if card_match:
                card_html = card_match.group(0)
                print(f"\nPrimera tarjeta (primeros 200 chars):")
                print(card_html[:200])
                
                # Verificar si es Propify
                if 'data-es-propify="true"' in card_html:
                    print("¡ESTA TARJETA ES PROPIY!")
                    
                    # Extraer más detalles
                    id_match = re.search(r'data-property-id="([^"]+)"', card_html)
                    if id_match:
                        print(f"ID: {id_match.group(1)}")
                else:
                    print("Esta tarjeta NO es Propify")
    else:
        print(f"ERROR: Status {response.status_code}")
        print(f"Contenido de error: {response.text[:500]}")
        
except requests.exceptions.Timeout:
    print("¡TIMEOUT! El servidor está tardando demasiado en responder.")
    print("Esto confirma que la vista tiene problemas de rendimiento.")
except Exception as e:
    print(f"ERROR: {e}")

print()
print("=== ANÁLISIS COMPLETADO ===")