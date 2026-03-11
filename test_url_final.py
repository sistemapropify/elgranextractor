#!/usr/bin/env python
import requests
import sys

def test_url():
    print("=== Probando vista Propify temporal ===")
    
    # URL de la vista temporal
    url = "http://127.0.0.1:8000/ingestas/propiedades-propify/"
    
    try:
        print(f"Accediendo a: {url}")
        response = requests.get(url, timeout=10)
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            content = response.text
            
            print("\n=== Análisis del contenido ===")
            
            # Verificar elementos clave
            checks = [
                ("Título Propify", 'Propiedades Propify' in content or 'Catálogo Exclusivo Propify' in content),
                ("Badges PROPIFY", 'PROPIFY' in content or 'propify-badge' in content.lower()),
                ("Tarjetas de propiedades", 'property-card' in content),
                ("Coordenadas", 'data-lat' in content and 'data-lng' in content),
                ("Mensaje de éxito", '¡Propiedades Propify encontradas!' in content or 'Propiedades Propify encontradas' in content),
            ]
            
            for check_name, check_result in checks:
                if check_result:
                    print(f"OK - {check_name}")
                else:
                    print(f"FALLO - {check_name}")
            
            # Contar tarjetas
            card_count = content.count('property-card')
            print(f"\nTarjetas de propiedades encontradas: {card_count}")
            
            # Contar coordenadas
            lat_count = content.count('data-lat')
            print(f"Propiedades con coordenadas: {lat_count}")
            
            # Verificar si hay propiedades
            if 'No se encontraron propiedades Propify' in content:
                print("\nADVERTENCIA: El mensaje 'No se encontraron propiedades Propify' aparece")
                print("Esto podría significar que:")
                print("  1. No hay propiedades en la base de datos")
                print("  2. Hay un error en la conexión a la base de datos")
                print("  3. El modelo PropifaiProperty no está configurado correctamente")
            
            print("\n=== URLs disponibles ===")
            print("1. Vista temporal Propify: http://127.0.0.1:8000/ingestas/propiedades-propify/")
            print("2. Vista original con filtro Propify: http://127.0.0.1:8000/ingestas/propiedades/?fuente_propify=propify")
            print("3. Vista independiente (si funciona): http://127.0.0.1:8000/propifai/propiedades/")
            
            return True
            
        else:
            print(f"ERROR: Status {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("ERROR: No se pudo conectar al servidor")
        print("Asegúrate de que el servidor esté corriendo en http://127.0.0.1:8000/")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

if __name__ == "__main__":
    success = test_url()
    sys.exit(0 if success else 1)