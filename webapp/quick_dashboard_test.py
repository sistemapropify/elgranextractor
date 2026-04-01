#!/usr/bin/env python
"""
Test rápido del dashboard después de las correcciones.
"""
import requests
import json

def quick_test():
    """Test rápido del dashboard"""
    url = "http://localhost:8000/propifai/dashboard/visitas/"
    
    print("=== TEST RÁPIDO DEL DASHBOARD ===")
    
    try:
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            html = response.text
            
            # Verificar que los elementos críticos están presentes
            checks = [
                ('id="properties-tbody"', 'Tabla de propiedades'),
                ('function renderTableBatch', 'Función de renderizado'),
                ('function updateKPIs', 'Función de KPIs'),
                ('function setupEventListeners', 'Función de eventos'),
                ('propertiesData = ', 'Datos de propiedades'),
            ]
            
            print("\n1. Verificación de elementos:")
            all_ok = True
            for search_str, description in checks:
                if search_str in html:
                    print(f"   [OK] {description}")
                else:
                    print(f"   [ERROR] {description}")
                    all_ok = False
            
            # Verificar datos
            if 'propertiesData = ' in html:
                start = html.find('propertiesData = ') + len('propertiesData = ')
                end = html.find('];', start) + 1
                if end > start:
                    json_str = html[start:end]
                    try:
                        data = json.loads(json_str)
                        print(f"\n2. Datos: {len(data)} propiedades cargadas")
                        
                        # Contar propiedades con eventos
                        with_events = sum(1 for p in data if p.get('total_eventos', 0) > 0)
                        print(f"   - {with_events} propiedades con eventos")
                        
                        # Mostrar primera propiedad como ejemplo
                        if data:
                            first = data[0]
                            print(f"\n3. Ejemplo (primera propiedad):")
                            print(f"   Código: {first.get('code', 'N/A')}")
                            print(f"   Eventos: {first.get('total_eventos', 0)}")
                            print(f"   Lead: {first.get('tiene_lead', False)}")
                            print(f"   Propuesta: {first.get('tiene_propuesta', False)}")
                            
                    except json.JSONDecodeError:
                        print("\n[ERROR] No se pudo parsear JSON")
                else:
                    print("\n[ERROR] No se pudo extraer JSON")
            else:
                print("\n[ERROR] No se encontraron datos de propiedades")
            
            if all_ok:
                print("\n" + "="*50)
                print("RESULTADO: Dashboard listo para usar")
                print("="*50)
                print("\nAccede a: http://localhost:8000/propifai/dashboard/visitas/")
                print("La tabla debería mostrar todas las propiedades con sus eventos.")
            else:
                print("\n[ERROR] Hay problemas que deben ser corregidos")
                
        else:
            print(f"[ERROR] HTTP {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("[ERROR] No se pudo conectar al servidor")
    except Exception as e:
        print(f"[ERROR] {e}")

if __name__ == "__main__":
    quick_test()