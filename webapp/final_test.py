#!/usr/bin/env python
"""
Test final sin caracteres Unicode
"""
import requests

def test_heatmap_final():
    print("=== TEST FINAL HEATMAP ===")
    
    # Probar puerto 8000 (principal)
    url = "http://localhost:8000/market-analysis/heatmap/"
    
    try:
        response = requests.get(url, timeout=5)
        content = response.text
        size = len(response.content)
        
        print(f"URL: {url}")
        print(f"Status: {response.status_code}")
        print(f"Size: {size} bytes")
        print()
        
        # Verificaciones
        checks = [
            ("HEATMAP FUNCIONAL", "Titulo nuevo"),
            ("VERSION DIRECTA HTML", "Version directa"),
            ("maps.googleapis.com", "Google Maps API"),
            ("initializeHeatmap", "Funcion JavaScript"),
        ]
        
        print("VERIFICACIONES:")
        new_version_found = False
        for text, desc in checks:
            found = text in content
            status = "OK" if found else "FALLO"
            print(f"  {status:6} {desc:20} -> {'SI' if found else 'NO'}")
            if text == "HEATMAP FUNCIONAL" and found:
                new_version_found = True
        
        print()
        print("RESULTADO:")
        if new_version_found:
            print("¡EXITO! La nueva versión del heatmap está funcionando.")
            print()
            print("INSTRUCCIONES PARA EL USUARIO:")
            print("1. Abra este URL en su navegador:")
            print(f"   {url}")
            print("2. Debería ver un mapa de Google con un heatmap de colores")
            print("3. Use el deslizador para ajustar la opacidad")
            print("4. Haga clic en 'Actualizar datos' o 'Ayuda' para probar")
            print()
            print("NOTA: Esta versión genera HTML directamente para evitar")
            print("problemas de cache de Django.")
        else:
            print("FALLO: Sigue sirviendo la versión antigua (33,257 bytes).")
            print()
            print("SOLUCION RECOMENDADA:")
            print("1. Detenga TODOS los servidores Django (Ctrl+C en cada terminal)")
            print("2. Ejecute solo un servidor:")
            print("   cd webapp && py manage.py runserver")
            print("3. Espere a que inicie")
            print("4. Abra: http://localhost:8000/market-analysis/heatmap/")
            print("5. Presione Ctrl+F5 en el navegador para forzar recarga")
            
    except Exception as e:
        print(f"ERROR: {e}")
        print()
        print("El servidor no está respondiendo en el puerto 8000.")
        print("Asegúrese de que al menos un servidor Django esté corriendo.")

if __name__ == "__main__":
    test_heatmap_final()