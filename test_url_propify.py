#!/usr/bin/env python
import requests
import sys

def test_url():
    print("=== Probando vista Propify independiente ===")
    
    # URL de la nueva vista
    url = "http://127.0.0.1:8000/propifai/propiedades/"
    
    try:
        print(f"Accediendo a: {url}")
        response = requests.get(url, timeout=10)
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            content = response.text
            
            # Buscar indicadores clave
            print("\n=== Análisis del contenido ===")
            
            # Verificar título
            if 'Propiedades Propify' in content or 'Catálogo Exclusivo Propify' in content:
                print("✓ Título de Propify encontrado")
            else:
                print("✗ Título de Propify NO encontrado")
                
            # Verificar badges Propify
            if 'PROPIFY' in content or 'propify-badge' in content.lower():
                print("✓ Badges Propify encontrados")
            else:
                print("✗ Badges Propify NO encontrados")
                
            # Verificar tarjetas de propiedades
            card_count = content.count('property-card')
            print(f"✓ Tarjetas de propiedades encontradas: {card_count}")
            
            # Verificar mensaje de éxito
            if '¡Propiedades Propify encontradas!' in content:
                print("✓ Mensaje de éxito encontrado")
            else:
                print("✗ Mensaje de éxito NO encontrado")
                
            # Verificar coordenadas en data attributes
            if 'data-lat' in content and 'data-lng' in content:
                lat_count = content.count('data-lat')
                print(f"✓ Propiedades con coordenadas: {lat_count}")
            else:
                print("✗ No se encontraron coordenadas")
                
            # Guardar muestra del HTML
            with open('propify_output.html', 'w', encoding='utf-8') as f:
                f.write(content[:10000])  # Primeros 10k caracteres
            print("\n✓ Muestra de HTML guardada en propify_output.html")
            
            # URLs para probar
            print("\n=== URLs para probar manualmente ===")
            print("1. Vista principal: http://127.0.0.1:8000/propifai/propiedades/")
            print("2. Vista simple: http://127.0.0.1:8000/propifai/propiedades-simple/")
            print("3. Vista original (con filtros): http://127.0.0.1:8000/ingestas/propiedades/?fuente_propify=propify")
            
        else:
            print(f"✗ Error: Status {response.status_code}")
            print("Posibles causas:")
            print("  - El servidor no está corriendo")
            print("  - La URL no existe")
            print("  - Error en la vista")
            
    except requests.exceptions.ConnectionError:
        print("✗ No se pudo conectar al servidor")
        print("Asegúrate de que el servidor esté corriendo en http://127.0.0.1:8000/")
    except Exception as e:
        print(f"✗ Error: {e}")

if __name__ == "__main__":
    test_url()