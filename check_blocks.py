#!/usr/bin/env python3
import urllib.request

url = 'http://127.0.0.1:8000/market-analysis/heatmap/'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
response = urllib.request.urlopen(req)
html = response.read().decode('utf-8')

# Buscar bloques específicos
print("=== BUSCANDO BLOQUES EN HTML RENDERIZADO ===")
print("\n1. Buscando 'extra_js' en HTML:")
if 'extra_js' in html:
    print("   ENCONTRADO")
    # Encontrar contexto alrededor
    idx = html.find('extra_js')
    print(f"   Contexto: ...{html[max(0, idx-50):min(len(html), idx+200)]}...")
else:
    print("   NO ENCONTRADO")

print("\n2. Buscando 'google' en HTML:")
if 'google' in html.lower():
    print("   ENCONTRADO")
    idx = html.lower().find('google')
    print(f"   Contexto: ...{html[max(0, idx-30):min(len(html), idx+100)]}...")
else:
    print("   NO ENCONTRADO")

print("\n3. Buscando 'heatmap.js' en HTML:")
if 'heatmap.js' in html:
    print("   ENCONTRADO")
    idx = html.find('heatmap.js')
    print(f"   Contexto: ...{html[max(0, idx-30):min(len(html), idx+100)]}...")
else:
    print("   NO ENCONTRADO")

print("\n4. Buscando 'AIzaSy' (clave API) en HTML:")
if 'AIzaSy' in html:
    print("   ENCONTRADO")
    idx = html.find('AIzaSy')
    print(f"   Contexto: ...{html[max(0, idx-20):min(len(html), idx+50)]}...")
else:
    print("   NO ENCONTRADO")

print("\n5. Buscando '{%' (template tags sin renderizar) en HTML:")
if '{%' in html:
    print("   ENCONTRADO - ERROR: Hay tags de template sin renderizar!")
    idx = html.find('{%')
    print(f"   Contexto: ...{html[max(0, idx-20):min(len(html), idx+50)]}...")
else:
    print("   NO ENCONTRADO - Bueno, los tags se renderizaron correctamente")

print("\n=== RESUMEN ===")
if '{%' in html:
    print("ERROR: El template no se está renderizando completamente.")
    print("Posible error de sintaxis en el template.")
else:
    print("El template se renderizó completamente (sin tags sin procesar).")
    if 'AIzaSy' not in html:
        print("PERO: La clave API no está en el HTML renderizado.")
        print("Esto significa que el bloque extra_js no se está insertando.")