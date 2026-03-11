#!/usr/bin/env python
"""
Analizar el HTML real generado por el servidor.
"""
import os
import sys
import django
from django.test import Client
from django.conf import settings

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

# Agregar testserver a ALLOWED_HOSTS para que funcione el test client
settings.configure(**settings.__dict__)
settings.ALLOWED_HOSTS.append('testserver')

django.setup()

print("=== ANÁLISIS DEL HTML REAL ===")
print()

# Crear cliente de prueba
client = Client()

# URL a probar (solo Propify)
url = "/ingestas/propiedades/?fuente_propify=propify"
print(f"Accediendo a: {url}")

try:
    response = client.get(url)
    print(f"Status code: {response.status_code}")
    
    if response.status_code == 200:
        content = response.content.decode('utf-8', errors='ignore')
        
        # Guardar HTML para análisis
        with open('html_output_propify.html', 'w', encoding='utf-8') as f:
            f.write(content)
        print("HTML guardado en 'html_output_propify.html'")
        
        # Buscar contadores
        import re
        
        # Buscar "propify" en todo el HTML
        propify_matches = re.findall(r'propify', content, re.IGNORECASE)
        print(f"'propify' aparece {len(propify_matches)} veces en el HTML")
        
        # Buscar contador específico
        conteo_match = re.search(r'(\d+)\s*propify', content, re.IGNORECASE)
        if conteo_match:
            print(f"Contador encontrado: {conteo_match.group(1)} propify")
        else:
            print("Contador NO encontrado")
            
        # Buscar tarjetas de propiedades
        property_cards = re.findall(r'class="property-card"', content)
        print(f"Total tarjetas de propiedades: {len(property_cards)}")
        
        # Buscar tarjetas Propify específicamente
        propify_cards = re.findall(r'data-es-propify="true"', content)
        print(f"Tarjetas con data-es-propify='true': {len(propify_cards)}")
        
        # Buscar "Propify" como texto en las tarjetas
        propify_text = re.findall(r'Propify', content)
        print(f"Texto 'Propify' aparece {len(propify_text)} veces")
        
        # Extraer fragmentos de tarjetas Propify
        if propify_cards:
            print("\n=== FRAGMENTOS DE TARJETAS PROPIY ===")
            # Encontrar todas las posiciones de data-es-propify="true"
            for match in re.finditer(r'data-es-propify="true"', content):
                start = max(0, match.start() - 500)
                end = min(len(content), match.start() + 1000)
                fragment = content[start:end]
                
                # Extraer información relevante
                card_match = re.search(r'class="property-card".*?data-es-propify="true".*?</div>\s*</div>\s*</div>', 
                                      fragment, re.DOTALL)
                if card_match:
                    card_html = card_match.group(0)
                    # Extraer ID
                    id_match = re.search(r'data-property-id="([^"]+)"', card_html)
                    id = id_match.group(1) if id_match else "N/A"
                    
                    # Extraer tipo
                    tipo_match = re.search(r'property-type[^>]*>([^<]+)<', card_html)
                    tipo = tipo_match.group(1).strip() if tipo_match else "N/A"
                    
                    # Extraer precio
                    precio_match = re.search(r'property-price[^>]*>([^<]+)<', card_html)
                    precio = precio_match.group(1).strip() if precio_match else "N/A"
                    
                    print(f"\nTarjeta Propify encontrada:")
                    print(f"  ID: {id}")
                    print(f"  Tipo: {tipo}")
                    print(f"  Precio: {precio}")
                    print(f"  Fragmento (primeros 200 chars): {card_html[:200]}...")
        else:
            print("\n=== NO SE ENCONTRARON TARJETAS PROPIY ===")
            print("Buscando cualquier tarjeta de propiedad...")
            
            # Buscar cualquier tarjeta
            card_matches = list(re.finditer(r'class="property-card"', content))
            if card_matches:
                print(f"Se encontraron {len(card_matches)} tarjetas de propiedades")
                # Mostrar primera tarjeta
                first_match = card_matches[0]
                start = max(0, first_match.start() - 200)
                end = min(len(content), first_match.start() + 800)
                fragment = content[start:end]
                print(f"\nPrimera tarjeta (primeros 300 chars):")
                print(f"{fragment[:300]}...")
                
                # Verificar si tiene data-es-propify
                if 'data-es-propify' in fragment:
                    print("¡Esta tarjeta TIENE data-es-propify!")
                else:
                    print("Esta tarjeta NO tiene data-es-propify")
            else:
                print("No se encontraron tarjetas de propiedades en absoluto")
                
        # Verificar contexto Django
        print("\n=== VERIFICANDO CONTEXTO DJANGO ===")
        if hasattr(response, 'context'):
            context = response.context
            print(f"Contexto disponible: {context}")
            
            if 'page' in context:
                page = context['page']
                print(f"Página: {page}")
                print(f"Objetos en página: {len(page.object_list) if page.object_list else 0}")
                
            if 'conteo_propify' in context:
                print(f"conteo_propify en contexto: {context['conteo_propify']}")
            else:
                print("conteo_propify NO está en el contexto")
                
            if 'todas_propiedades' in context:
                todas = context['todas_propiedades']
                print(f"todas_propiedades en contexto: {len(todas) if todas else 0}")
                
                # Contar Propify
                if todas:
                    propify_count = sum(1 for p in todas if hasattr(p, 'get') and p.get('es_propify', False))
                    print(f"Propiedades Propify en todas_propiedades: {propify_count}")
    else:
        print(f"ERROR: Status code {response.status_code}")
        
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

print()
print("=== ANÁLISIS COMPLETADO ===")