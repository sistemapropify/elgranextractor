#!/usr/bin/env python
"""
Script para verificar que el JavaScript del dashboard se ejecuta correctamente.
"""
import requests
import json

def test_javascript_execution():
    """Test que verifica la ejecución del JavaScript"""
    url = "http://localhost:8000/propifai/dashboard/visitas/"
    
    print("=== VERIFICACIÓN DE EJECUCIÓN JAVASCRIPT ===")
    
    try:
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            html = response.text
            
            # Extraer los datos de propiedades del JavaScript
            if "propertiesData = " in html:
                start = html.find("propertiesData = ") + len("propertiesData = ")
                # Buscar el final del array
                bracket_count = 0
                i = start
                while i < len(html):
                    if html[i] == '[':
                        bracket_count += 1
                    elif html[i] == ']':
                        bracket_count -= 1
                        if bracket_count == 0:
                            end = i + 1
                            break
                    i += 1
                else:
                    end = html.find("];", start) + 1
                
                if end > start:
                    json_str = html[start:end]
                    try:
                        properties = json.loads(json_str)
                        print(f"[OK] Datos de propiedades parseados correctamente")
                        print(f"  Total de propiedades: {len(properties)}")
                        
                        # Contar propiedades con eventos
                        with_events = sum(1 for p in properties if p.get('total_eventos', 0) > 0)
                        print(f"  Propiedades con eventos: {with_events}")
                        
                        # Mostrar algunas propiedades de ejemplo
                        print("\n  Ejemplos de propiedades:")
                        for i, prop in enumerate(properties[:3]):
                            print(f"    {i+1}. {prop.get('code', 'N/A')}: {prop.get('total_eventos', 0)} eventos, "
                                  f"Lead: {prop.get('tiene_lead', False)}, "
                                  f"Propuesta: {prop.get('tiene_propuesta', False)}")
                        
                        # Verificar que los datos tienen la estructura esperada
                        required_fields = ['id', 'code', 'total_eventos', 'primera_visita', 'ultima_visita']
                        sample_prop = properties[0] if properties else {}
                        missing_fields = [field for field in required_fields if field not in sample_prop]
                        
                        if not missing_fields:
                            print(f"\n[OK] Todos los campos requeridos están presentes")
                        else:
                            print(f"\n[ERROR] Campos faltantes: {missing_fields}")
                            
                    except json.JSONDecodeError as e:
                        print(f"[ERROR] Error al parsear JSON: {e}")
                        print(f"  Fragmento problemático: {json_str[:200]}...")
                else:
                    print("[ERROR] No se pudo extraer datos JSON")
            else:
                print("[ERROR] Variable propertiesData no encontrada en el HTML")
                
            # Verificar que el tbody está presente y vacío (será llenado por JavaScript)
            if 'id="properties-tbody"' in html:
                print("\n[OK] Elemento tbody encontrado (id='properties-tbody')")
                
                # Verificar que está vacío inicialmente (como debería ser)
                tbody_start = html.find('id="properties-tbody"')
                tbody_end = html.find('</tbody>', tbody_start)
                tbody_content = html[tbody_start:tbody_end+8] if tbody_end > tbody_start else ""
                
                if '<!-- Datos cargados por JavaScript -->' in tbody_content:
                    print("[OK] Tbody está vacío inicialmente (será llenado por JavaScript)")
                else:
                    print("[ADVERTENCIA] Tbody podría tener contenido estático")
                    
            else:
                print("\n[ERROR] Elemento tbody NO encontrado")
                
        else:
            print(f"[ERROR] Error HTTP: {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("[ERROR] No se pudo conectar al servidor")
    except Exception as e:
        print(f"[ERROR] Error inesperado: {e}")

if __name__ == "__main__":
    test_javascript_execution()