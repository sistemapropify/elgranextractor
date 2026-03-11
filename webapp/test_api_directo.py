#!/usr/bin/env python
"""
Script para probar la API externa directamente con requests.
"""
import requests
import json
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

API_URL = os.getenv('API_EXTERNA_URL', 'http://localhost/dashboard/api/properties/with-docs/')
API_KEY = os.getenv('API_EXTERNA_KEY', 'ItBJSnE6F7gIG5uhnPh0mtXmQ9yjE8ZgqtIjTU')

def test_api():
    print("=== Probando API Externa Directamente ===")
    print(f"URL: {API_URL}")
    print(f"API Key: {API_KEY[:20]}...")
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    try:
        response = requests.get(API_URL, headers=headers, timeout=10, verify=False)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Respuesta JSON recibida (tipo: {type(data)})")
            
            # Intentar extraer propiedades
            if isinstance(data, dict):
                if 'results' in data:
                    items = data['results']
                elif 'data' in data:
                    items = data['data']
                elif 'properties' in data:
                    items = data['properties']
                elif 'items' in data:
                    items = data['items']
                else:
                    items = [data]
            elif isinstance(data, list):
                items = data
            else:
                items = []
            
            print(f"Se encontraron {len(items)} elementos")
            
            if items:
                print("\nPrimeros elementos:")
                for i, item in enumerate(items[:3]):
                    print(f"\n[{i+1}]")
                    print(f"  ID: {item.get('id', item.get('property_id', 'N/A'))}")
                    print(f"  Tipo: {item.get('property_type', item.get('type', 'N/A'))}")
                    print(f"  Precio: {item.get('price_usd', item.get('price', 'N/A'))}")
                    print(f"  Descripción: {str(item.get('description', item.get('descripcion', 'N/A')))[:50]}...")
        else:
            print(f"Error: {response.text[:200]}")
            
    except requests.exceptions.ConnectionError as e:
        print(f"Error de conexión: {e}")
        print("Asegúrate de que la API esté ejecutándose en la URL especificada.")
    except requests.exceptions.Timeout as e:
        print(f"Timeout: {e}")
    except json.JSONDecodeError as e:
        print(f"Error decodificando JSON: {e}")
        print(f"Respuesta cruda: {response.text[:200]}")
    except Exception as e:
        print(f"Error inesperado: {e}")
    
    print("\n=== Prueba completada ===")

if __name__ == '__main__':
    test_api()