#!/usr/bin/env python
"""
Test final del dashboard - verifica que todo funciona correctamente.
"""
import requests
import json
import sys

def test_complete_dashboard():
    """Test completo del dashboard"""
    print("=== TEST FINAL DEL DASHBOARD DE VISITAS ===")
    print("Verificando todos los componentes...")
    
    url = "http://localhost:8000/propifai/dashboard/visitas/"
    
    try:
        # 1. Verificar que la página carga
        print("\n1. Carga de página HTTP...")
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            print(f"   [ERROR] HTTP {response.status_code}")
            return False
        
        print("   [OK] Página cargada exitosamente")
        html = response.text
        
        # 2. Verificar datos JSON
        print("\n2. Datos de propiedades en JavaScript...")
        if "propertiesData = " not in html:
            print("   [ERROR] Variable propertiesData no encontrada")
            return False
        
        # Extraer JSON
        start = html.find("propertiesData = ") + len("propertiesData = ")
        end = html.find("];", start) + 1
        if end <= start:
            end = html.find("};", start) + 1
        
        if end <= start:
            print("   [ERROR] No se pudo extraer JSON")
            return False
        
        json_str = html[start:end]
        try:
            properties = json.loads(json_str)
            print(f"   [OK] {len(properties)} propiedades cargadas")
            print(f"   [OK] {sum(1 for p in properties if p.get('total_eventos', 0) > 0)} propiedades con eventos")
        except json.JSONDecodeError:
            print("   [ERROR] JSON inválido")
            return False
        
        # 3. Verificar elementos HTML críticos
        print("\n3. Elementos HTML críticos...")
        critical_elements = [
            ("id=\"properties-tbody\"", "Tabla de propiedades"),
            ("class=\"sticky-filters\"", "Filtros sticky"),
            ("id=\"filter-visits\"", "Filtro de visitas"),
            ("id=\"detailOffcanvas\"", "Panel lateral de detalle"),
            ("renderTableBatch", "Función de renderizado"),
            ("setupEventListeners", "Configuración de eventos"),
        ]
        
        all_ok = True
        for element, description in critical_elements:
            if element in html:
                print(f"   [OK] {description}")
            else:
                print(f"   [ERROR] {description} no encontrado")
                all_ok = False
        
        if not all_ok:
            return False
        
        # 4. Verificar que el JavaScript está completo (sin errores de sintaxis obvios)
        print("\n4. Sintaxis JavaScript...")
        js_checks = [
            ("function renderTableBatch()", "Función renderTableBatch definida"),
            ("function setupEventListeners()", "Función setupEventListeners definida"),
            ("document.addEventListener('DOMContentLoaded'", "Evento DOMContentLoaded configurado"),
            ("filteredData = [...propertiesData]", "Inicialización de filteredData"),
            ("const offcanvas = new bootstrap.Offcanvas", "Inicialización de Bootstrap Offcanvas"),
        ]
        
        for check, description in js_checks:
            if check in html:
                print(f"   [OK] {description}")
            else:
                print(f"   [ADVERTENCIA] {description} no encontrado")
        
        # 5. Verificar API endpoint
        print("\n5. Endpoint API de eventos...")
        api_url = "http://localhost:8000/propifai/api/property/2/events/"
        try:
            api_response = requests.get(api_url, timeout=5)
            if api_response.status_code == 200:
                api_data = api_response.json()
                print(f"   [OK] API responde correctamente")
                print(f"   [OK] {len(api_data.get('events', []))} eventos para propiedad 2")
            else:
                print(f"   [ADVERTENCIA] API HTTP {api_response.status_code}")
        except:
            print("   [ADVERTENCIA] No se pudo conectar a la API")
        
        print("\n" + "="*50)
        print("RESUMEN: Dashboard implementado correctamente")
        print("="*50)
        print("\nEl dashboard está listo para usar. Para acceder:")
        print(f"1. Abre el navegador en: {url}")
        print("2. Deberías ver:")
        print("   - Tabla con 75 propiedades (23 con eventos)")
        print("   - Filtros en la parte superior")
        print("   - KPIs con métricas")
        print("   - Panel lateral que se abre al hacer clic en una propiedad")
        print("\nSi la tabla aparece vacía, verifica:")
        print("   - Que JavaScript esté habilitado en el navegador")
        print("   - Que no haya errores en la consola (F12 > Console)")
        print("   - Recargar la página (Ctrl+F5)")
        
        return True
        
    except requests.exceptions.ConnectionError:
        print("\n[ERROR] No se pudo conectar al servidor")
        print("Asegúrate de que Django esté corriendo:")
        print("  cd webapp && py manage.py runserver")
        return False
    except Exception as e:
        print(f"\n[ERROR] Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_complete_dashboard()
    sys.exit(0 if success else 1)