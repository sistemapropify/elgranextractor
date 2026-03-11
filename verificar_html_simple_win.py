#!/usr/bin/env python3
"""
Verificación simple del HTML para Windows (sin Unicode)
"""
import urllib.request
import urllib.parse
import sys

def verificar_html():
    print("=== VERIFICACION DIRECTA DEL HTML ===")
    
    # URL con filtro solo Propify
    url = "http://localhost:8000/ingestas/propiedades/"
    params = {'fuente_propify': 'propify'}
    query_string = urllib.parse.urlencode(params)
    full_url = f"{url}?{query_string}"
    
    print(f"URL: {full_url}")
    
    try:
        # Hacer la petición
        req = urllib.request.Request(full_url)
        response = urllib.request.urlopen(req, timeout=30)
        html = response.read().decode('utf-8')
        
        print(f"Status: {response.status}")
        print(f"Tamano HTML: {len(html)} bytes")
        
        # Análisis crítico
        print("\n--- ANALISIS CRITICO ---")
        
        # 1. ¿Existe el contenedor de propiedades?
        if '<div class="properties-container"' in html:
            print("OK - Contenedor de propiedades encontrado")
        else:
            print("ERROR - Contenedor de propiedades NO encontrado")
            
        # 2. ¿Hay tarjetas de propiedades?
        card_count = html.count('property-card')
        print(f"Total de tarjetas 'property-card': {card_count}")
        
        # 3. ¿Hay tarjetas con data-es-propify="true"?
        propify_true = html.count('data-es-propify="true"')
        propify_false = html.count('data-es-propify="false"')
        print(f"Tarjetas con data-es-propify=\"true\": {propify_true}")
        print(f"Tarjetas con data-es-propify=\"false\": {propify_false}")
        
        # 4. ¿Se muestra el badge "Propify"?
        propify_badge_count = html.count('>Propify<')
        print(f"Badges 'Propify' encontrados: {propify_badge_count}")
        
        # 5. ¿Hay coordenadas en las tarjetas?
        lat_count = html.count('data-lat=')
        lng_count = html.count('data-lng=')
        print(f"Atributos data-lat: {lat_count}, data-lng: {lng_count}")
        
        # 6. Buscar fragmento específico de Propify
        if '<!-- Diseno especial para Propify -->' in html:
            print("OK - Diseno especial para Propify encontrado en HTML")
        else:
            print("ERROR - Diseno especial para Propify NO encontrado")
            
        # 7. Verificar si hay propiedades locales/externas que no deberían estar
        if propify_true == 0 and card_count > 0:
            print("\nPROBLEMA CRITICO: Hay tarjetas pero NINGUNA es Propify!")
            print("Esto significa que:")
            print("1. Las propiedades Propify no se estan incluyendo en el template")
            print("2. El campo es_propify no se esta estableciendo correctamente")
            print("3. Hay un error en la logica de filtrado")
        elif propify_true > 0:
            print(f"\nOK - Se encontraron {propify_true} propiedades Propify en el HTML")
        
        # Extraer un fragmento para inspección
        print("\n--- BUSCANDO PRIMERA TARJETA PROPIY ---")
        # Buscar la primera ocurrencia de data-es-propify="true"
        pos = html.find('data-es-propify="true"')
        if pos != -1:
            # Encontrar el inicio de la tarjeta (retroceder hasta property-card)
            start = html.rfind('property-card', 0, pos)
            if start != -1:
                # Encontrar el final de la tarjeta
                end = html.find('property-card', start + 1)
                if end == -1:
                    end = min(start + 2000, len(html))
                
                fragment = html[start:end]
                print("Fragmento de tarjeta Propify encontrado:")
                print("-" * 50)
                # Mostrar líneas importantes
                lines = fragment.split('\n')
                for line in lines[:20]:  # Primeras 20 líneas
                    line_stripped = line.strip()
                    if line_stripped and ('data-' in line_stripped or 'class="' in line_stripped or 'Propify' in line_stripped):
                        print(line_stripped[:200])
                print("-" * 50)
            else:
                print("No se pudo encontrar el inicio de la tarjeta")
        else:
            print("No se encontro data-es-propify=\"true\" en el HTML")
            
            # Buscar cualquier tarjeta para ver qué hay
            pos2 = html.find('property-card')
            if pos2 != -1:
                end2 = html.find('property-card', pos2 + 1)
                if end2 == -1:
                    end2 = min(pos2 + 1000, len(html))
                fragment2 = html[pos2:end2]
                print("\nPrimera tarjeta encontrada (cualquiera):")
                print("-" * 50)
                lines2 = fragment2.split('\n')
                for line in lines2[:15]:
                    line_stripped = line.strip()
                    if line_stripped:
                        print(line_stripped[:150])
                print("-" * 50)
        
        # Verificar JavaScript
        print("\n--- VERIFICACION DE JAVASCRIPT ---")
        if 'addMarker' in html:
            print("OK - Funcion addMarker encontrada")
            # Buscar referencia a esPropify
            if 'esPropify' in html:
                print("OK - JavaScript maneja esPropify")
            else:
                print("ERROR - JavaScript NO maneja esPropify")
        else:
            print("ERROR - Funcion addMarker NO encontrada")
            
        # Guardar un fragmento del HTML para inspección
        with open('html_fragmento.txt', 'w', encoding='utf-8') as f:
            # Guardar solo las primeras 50000 caracteres
            f.write(html[:50000])
        print(f"\nFragmento de HTML guardado en 'html_fragmento.txt'")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verificar_html()