import requests
import json

def test_api_externa():
    """Prueba la API externa para obtener propiedades"""
    url = "http://localhost/dashboard/api/properties/with-docs/"
    headers = {
        "Authorization": "Bearer ItBJSnE6F7gIG5uhnPh0mtXmQ9yjE8ZgqtIjTU"
    }
    
    try:
        print(f"Probando API: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        print(f"Headers: {response.headers.get('content-type')}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Respuesta exitosa. Estructura de datos:")
            print(f"Tipo: {type(data)}")
            
            if isinstance(data, dict):
                print(f"Claves: {list(data.keys())}")
                # Mostrar estructura de las propiedades si existe
                if 'results' in data:
                    print(f"Número de propiedades: {len(data.get('results', []))}")
                    if data.get('results'):
                        primera_propiedad = data['results'][0]
                        print(f"\nPrimera propiedad:")
                        print(json.dumps(primera_propiedad, indent=2, ensure_ascii=False))
                elif 'data' in data:
                    print(f"Número de propiedades: {len(data.get('data', []))}")
                    if data.get('data'):
                        primera_propiedad = data['data'][0]
                        print(f"\nPrimera propiedad:")
                        print(json.dumps(primera_propiedad, indent=2, ensure_ascii=False))
                else:
                    # Asumir que es una lista
                    if isinstance(data, list):
                        print(f"Número de propiedades: {len(data)}")
                        if data:
                            print(f"\nPrimera propiedad:")
                            print(json.dumps(data[0], indent=2, ensure_ascii=False))
                    else:
                        print(f"\nContenido completo (primeros 1000 chars):")
                        print(json.dumps(data, indent=2, ensure_ascii=False)[:1000])
            elif isinstance(data, list):
                print(f"Número de propiedades: {len(data)}")
                if data:
                    print(f"\nPrimera propiedad:")
                    print(json.dumps(data[0], indent=2, ensure_ascii=False))
        else:
            print(f"Error en la respuesta: {response.text[:500]}")
            
    except requests.exceptions.RequestException as e:
        print(f"Error de conexión: {e}")
    except json.JSONDecodeError as e:
        print(f"Error decodificando JSON: {e}")
        print(f"Respuesta cruda: {response.text[:500]}")

if __name__ == "__main__":
    test_api_externa()