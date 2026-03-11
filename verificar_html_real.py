#!/usr/bin/env python3
"""
Script para verificar el HTML real generado por el servidor
y ver si las propiedades de Propify están presentes.
"""
import requests
import sys
import os

# Agregar el directorio webapp al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

import django
django.setup()

def verificar_html_filtro_propify():
    """Verificar el HTML cuando se filtra solo por Propify"""
    print("=== VERIFICACIÓN HTML REAL CON FILTRO PROPIY ===")
    
    # Hacer petición al servidor local
    url = "http://localhost:8000/ingestas/propiedades/"
    params = {'fuente_propify': 'propify'}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"URL: {response.url}")
        
        if response.status_code == 200:
            html = response.text
            
            # Buscar indicadores de propiedades Propify en el HTML
            print("\n--- Análisis del HTML ---")
            
            # Contar tarjetas de propiedades
            card_count = html.count('property-card')
            print(f"Total de tarjetas 'property-card': {card_count}")
            
            # Buscar propiedades con data-es-propify="true"
            propify_cards = html.count('data-es-propify="true"')
            print(f"Tarjetas con data-es-propify=\"true\": {propify_cards}")
            
            # Buscar badges de Propify
            propify_badges = html.count('Propify')
            print(f"Ocurrencias de 'Propify' en el HTML: {propify_badges}")
            
            # Buscar coordenadas
            lat_count = html.count('data-lat=')
            lng_count = html.count('data-lng=')
            print(f"Atributos data-lat: {lat_count}, data-lng: {lng_count}")
            
            # Extraer un fragmento del HTML para inspección
            start_idx = html.find('<div class="properties-container"')
            if start_idx != -1:
                end_idx = html.find('</div>', start_idx + 5000)
                if end_idx != -1:
                    fragment = html[start_idx:end_idx + 6]
                    # Contar propiedades en el fragmento
                    prop_count = fragment.count('property-card')
                    print(f"\nPropiedades en el fragmento del contenedor: {prop_count}")
                    
                    # Mostrar las primeras 3 tarjetas
                    card_start = 0
                    for i in range(min(3, prop_count)):
                        card_start = fragment.find('property-card', card_start)
                        if card_start == -1:
                            break
                        card_end = fragment.find('property-card', card_start + 1)
                        if card_end == -1:
                            card_end = len(fragment)
                        
                        card_html = fragment[card_start:card_end]
                        print(f"\n--- Tarjeta {i+1} ---")
                        # Extraer información clave
                        if 'data-es-propify="true"' in card_html:
                            print("  ES PROPIY: SÍ")
                        else:
                            print("  ES PROPIY: NO")
                        
                        # Extraer título/precio
                        title_start = card_html.find('property-type')
                        if title_start != -1:
                            title_end = card_html.find('</span>', title_start)
                            if title_end != -1:
                                title = card_html[title_start:title_end]
                                print(f"  Tipo: {title[title.find('>')+1:]}")
                        
                        card_start = card_end
            
            # Verificar si hay propiedades locales/externas que no deberían estar
            if propify_cards == 0:
                print("\n¡ADVERTENCIA: No se encontraron tarjetas con data-es-propify=\"true\"!")
                print("Esto podría indicar que:")
                print("1. Las propiedades no están siendo incluidas en el contexto")
                print("2. El template no está renderizando correctamente")
                print("3. El filtro no está funcionando")
            
            # Guardar el HTML para inspección
            with open('html_output_propify.html', 'w', encoding='utf-8') as f:
                f.write(html)
            print(f"\nHTML guardado en 'html_output_propify.html'")
            
        else:
            print(f"Error: Status code {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"Error de conexión: {e}")
        print("Asegúrate de que el servidor esté corriendo en localhost:8000")

def verificar_html_sin_filtros():
    """Verificar el HTML sin filtros (todas las fuentes)"""
    print("\n=== VERIFICACIÓN HTML SIN FILTROS ===")
    
    url = "http://localhost:8000/ingestas/propiedades/"
    
    try:
        response = requests.get(url, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            html = response.text
            
            # Contar tarjetas
            card_count = html.count('property-card')
            print(f"Total de tarjetas 'property-card': {card_count}")
            
            # Contar por tipo
            propify_cards = html.count('data-es-propify="true"')
            externo_cards = html.count('data-es-externo="true"')
            print(f"Tarjetas Propify: {propify_cards}")
            print(f"Tarjetas Externas: {externo_cards}")
            
            # Guardar para comparación
            with open('html_output_todas.html', 'w', encoding='utf-8') as f:
                f.write(html)
            print(f"HTML guardado en 'html_output_todas.html'")
            
    except requests.exceptions.RequestException as e:
        print(f"Error de conexión: {e}")

if __name__ == "__main__":
    print("Iniciando verificación HTML real...")
    verificar_html_filtro_propify()
    verificar_html_sin_filtros()
    print("\n=== VERIFICACIÓN COMPLETADA ===")