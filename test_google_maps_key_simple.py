#!/usr/bin/env python3
"""
Script para probar si la clave de Google Maps API es válida.
"""
import urllib.request
import json

API_KEY = "AIzaSyBrL1QF7vTl9zF8FmCUumfRpFJcaYokO7Q"
TEST_URL = f"https://maps.googleapis.com/maps/api/js?key={API_KEY}&libraries=visualization"

print(f"Probando clave de Google Maps API: {API_KEY}")
print(f"URL de prueba: {TEST_URL}")

try:
    # Intentar cargar la API (solo verificar que no haya error 400/403)
    req = urllib.request.Request(TEST_URL, headers={'User-Agent': 'Mozilla/5.0'})
    response = urllib.request.urlopen(req, timeout=10)
    
    print(f"OK - HTTP {response.status}: La clave parece válida (la API se carga)")
    print(f"Content-Type: {response.headers.get('Content-Type', 'desconocido')}")
    
    # Leer un poco del contenido para verificar
    content = response.read(500)
    if b'Google Maps JavaScript API' in content:
        print("OK - Contenido parece ser la API de Google Maps")
    else:
        print("ADVERTENCIA - El contenido no parece ser la API de Google Maps")
        
except urllib.error.HTTPError as e:
    print(f"ERROR - HTTP {e.code}: {e.reason}")
    if e.code == 403:
        print("   Posibles causas:")
        print("   - La clave API no es válida")
        print("   - La clave está restringida a dominios específicos")
        print("   - La API 'Maps JavaScript API' no está habilitada")
        print("   - Se ha excedido la cuota de uso")
    # Leer el cuerpo del error para más detalles
    try:
        error_body = e.read().decode('utf-8')
        print(f"   Detalles: {error_body[:200]}")
    except:
        pass
except Exception as e:
    print(f"ERROR - {type(e).__name__}: {e}")

print("\n--- Verificación adicional ---")
print("Esta clave se usa en:")
print("1. Módulo ACM (funciona)")
print("2. Módulo Market Analysis (problema reportado)")
print("\nPosibles diferencias:")
print("- El módulo ACM usa la clave en acm_analisis.html")
print("- Market Analysis la usa en heatmap.html")
print("- Mismo dominio (localhost), debería funcionar igual")