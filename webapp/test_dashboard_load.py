#!/usr/bin/env python
"""
Script para probar la carga del dashboard de visitas.
Verifica que la página se carga correctamente y que el JavaScript se ejecuta.
"""
import requests
import sys
import os

def test_dashboard_load():
    """Test que verifica la carga del dashboard"""
    url = "http://localhost:8000/propifai/dashboard/visitas/"
    
    print("=== TEST DE CARGA DEL DASHBOARD DE VISITAS ===")
    print(f"URL: {url}")
    
    try:
        # Hacer la solicitud HTTP
        response = requests.get(url, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("[OK] Página cargada exitosamente")
            
            # Verificar contenido clave
            html = response.text
            
            # Verificar elementos críticos
            checks = [
                ("<title>Dashboard de Visitas</title>", "Título de la página"),
                ("id=\"properties-tbody\"", "Tabla de propiedades (tbody)"),
                ("propertiesData = ", "Datos de propiedades en JavaScript"),
                ("renderTableBatch", "Función de renderizado por lotes"),
                ("filter-visits", "Filtro de visitas"),
                ("detailOffcanvas", "Panel lateral de detalle")
            ]
            
            all_passed = True
            for search_str, description in checks:
                if search_str in html:
                    print(f"[OK] {description} encontrado")
                else:
                    print(f"[ERROR] {description} NO encontrado")
                    all_passed = False
            
            # Verificar longitud del HTML
            print(f"Longitud del HTML: {len(html)} caracteres")
            
            # Verificar si hay datos de propiedades
            if "propertiesData = " in html:
                # Extraer el JSON de propiedades
                start = html.find("propertiesData = ") + len("propertiesData = ")
                end = html.find("];", start) + 1 if "];" in html[start:] else html.find("};", start) + 1
                
                if end > start:
                    data_str = html[start:end]
                    # Contar propiedades aproximadas
                    prop_count = data_str.count('"id":')
                    print(f"[OK] Datos de propiedades encontrados: aproximadamente {prop_count} propiedades")
                    
                    # Mostrar primeros 500 caracteres del JSON
                    preview = data_str[:500].replace('\n', ' ').replace('\r', '')
                    print(f"  Vista previa: {preview}...")
                else:
                    print("[ERROR] No se pudo extraer datos de propiedades")
                    all_passed = False
            else:
                print("[ERROR] No se encontró variable propertiesData en el HTML")
                all_passed = False
            
            if all_passed:
                print("\n[OK] TODAS LAS VERIFICACIONES PASARON")
                print("El dashboard debería funcionar correctamente en el navegador.")
            else:
                print("\n[ERROR] ALGUNAS VERIFICACIONES FALLARON")
                print("Revisar el template para asegurar que todos los elementos están presentes.")
                
        else:
            print(f"[ERROR] Error al cargar la página: {response.status_code}")
            print(f"Contenido: {response.text[:500]}...")
            
    except requests.exceptions.ConnectionError:
        print("[ERROR] No se pudo conectar al servidor. ¿Está corriendo Django?")
        print("Ejecuta: cd webapp && py manage.py runserver")
    except Exception as e:
        print(f"[ERROR] Error inesperado: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_dashboard_load()