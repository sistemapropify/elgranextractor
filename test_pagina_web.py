#!/usr/bin/env python
"""
Test para verificar la página web directamente.
"""
import requests
import time

print("=== TEST DE PÁGINA WEB ===\n")

url = "http://localhost:8000/ingestas/propiedades/"
print(f"Accediendo a: {url}")

try:
    # Primera solicitud: sin parámetros
    print("\n1. Solicitud sin parámetros (todas las fuentes):")
    response1 = requests.get(url, timeout=10)
    print(f"   Status: {response1.status_code}")
    print(f"   Tamaño: {len(response1.text)} bytes")
    
    # Buscar indicadores de propiedades Propify en el HTML
    if 'Propify' in response1.text:
        print("   ✓ 'Propify' encontrado en HTML")
    else:
        print("   ✗ 'Propify' NO encontrado en HTML")
    
    if 'es_propify' in response1.text:
        print("   ✓ 'es_propify' encontrado en HTML")
    else:
        print("   ✗ 'es_propify' NO encontrado en HTML")
    
    # Contar propiedades en el HTML (aproximadamente)
    import re
    property_cards = re.findall(r'property-card', response1.text)
    print(f"   Número de 'property-card' encontradas: {len(property_cards)}")
    
    # Segunda solicitud: solo Propify
    print("\n2. Solicitud solo Propify:")
    response2 = requests.get(url, params={'fuente_propify': 'propify'}, timeout=10)
    print(f"   Status: {response2.status_code}")
    
    # Verificar conteo en HTML
    if 'propiedades (' in response2.text:
        # Buscar el patrón de conteo
        import re
        match = re.search(r'propiedades\s*\((\d+)\s*locales', response2.text)
        if match:
            print(f"   Conteo de locales en HTML: {match.group(1)}")
    
    # Buscar "Propify" en el HTML de respuesta
    if 'Propify' in response2.text:
        print("   ✓ 'Propify' encontrado en HTML")
    else:
        print("   ✗ 'Propify' NO encontrado en HTML - esto es un problema")
        
    # Guardar una muestra del HTML para inspección
    with open('test_pagina_propify.html', 'w', encoding='utf-8') as f:
        f.write(response2.text[:5000])  # Primeros 5000 caracteres
    print("   Muestra de HTML guardada en 'test_pagina_propify.html'")
    
except requests.exceptions.ConnectionError:
    print("   ✗ No se pudo conectar al servidor. Asegúrate de que el servidor Django esté corriendo en localhost:8000")
except Exception as e:
    print(f"   ✗ Error: {e}")

print("\n=== FIN DEL TEST ===")