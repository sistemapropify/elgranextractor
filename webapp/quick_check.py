#!/usr/bin/env python
"""
Verificación rápida de la nueva versión
"""
import requests

url = "http://localhost:8000/market-analysis/heatmap/"

try:
    print("Probando:", url)
    response = requests.get(url, timeout=5)
    
    print(f"Status: {response.status_code}")
    print(f"Tamaño: {len(response.content)} bytes")
    
    content = response.text
    
    # Buscar indicadores clave de la NUEVA versión
    if "HEATMAP FUNCIONANDO CORRECTAMENTE" in content:
        print("\n✅ ¡ÉXITO! Se está sirviendo la VERSIÓN NUEVA")
        print("   El heatmap debería funcionar correctamente.")
        print("\n   Abra el URL en su navegador y debería ver:")
        print("   - Un mensaje 'HEATMAP FUNCIONANDO CORRECTAMENTE'")
        print("   - Un mapa de Google Maps")
        print("   - Controles interactivos")
        print("   - Un heatmap de colores")
        
        # Verificar Google Maps
        if "maps.googleapis.com" in content:
            print("   ✅ Google Maps API incluida")
        else:
            print("   ⚠️  Google Maps API NO encontrada")
            
    elif "Heatmap de Precio por m" in content:
        print("\n⚠️  Se está sirviendo la VERSIÓN ANTIGUA (cacheada)")
        print("   Tamaño: 33,257 bytes (template antiguo)")
        print("\n   PROBLEMA: Hay múltiples servidores Django corriendo.")
        print("   SOLUCIÓN: Detenga TODOS los servidores y ejecute solo uno.")
        
    else:
        print("\n❓ Versión desconocida")
        print("   Muestra de contenido (primeros 200 caracteres):")
        print(content[:200])
        
except Exception as e:
    print(f"\n❌ Error: {e}")
    print("\n   Asegúrese de que el servidor Django esté corriendo.")
    print("   Ejecute: cd webapp && py manage.py runserver")