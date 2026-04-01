#!/usr/bin/env python
"""
Verificar si los elementos script con datos se están generando en el HTML
"""
import os
import sys
import django
import re

# Configurar Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from django.test import Client

def verificar_html_real():
    """Hacer una petición real al servidor y verificar el HTML"""
    print("=== VERIFICACIÓN DE ELEMENTOS SCRIPT EN HTML REAL ===")
    
    client = Client()
    response = client.get('/analisis-crm/')
    
    print(f"Status code: {response.status_code}")
    print(f"Content type: {response['Content-Type']}")
    
    html = response.content.decode('utf-8')
    
    # Buscar los elementos script
    print("\n1. Buscando script con id='days-data':")
    days_pattern = r'<script[^>]*id="days-data"[^>]*>(.*?)</script>'
    days_match = re.search(days_pattern, html, re.DOTALL | re.IGNORECASE)
    
    if days_match:
        days_content = days_match.group(1).strip()
        print(f"   ✓ ENCONTRADO")
        print(f"   Contenido (primeros 150 chars): {days_content[:150]}...")
        
        # Verificar si está vacío
        if not days_content or days_content.isspace():
            print("   ¡ADVERTENCIA! El contenido está vacío o solo tiene espacios")
        else:
            # Intentar parsear JSON
            import json
            try:
                days_list = json.loads(days_content)
                print(f"   JSON válido, longitud: {len(days_list)}")
                print(f"   Primeros 5 elementos: {days_list[:5]}")
                
                # Buscar 05/03
                if '05/03' in days_list:
                    idx = days_list.index('05/03')
                    print(f"   '05/03' encontrado en índice: {idx}")
                else:
                    print(f"   '05/03' NO encontrado en la lista")
                    print(f"   Elementos disponibles: {days_list}")
            except json.JSONDecodeError as e:
                print(f"   ERROR parseando JSON: {e}")
                print(f"   Contenido problemático: {days_content[:100]}")
    else:
        print("   ✗ NO ENCONTRADO")
        # Buscar cualquier script que pueda contener datos
        print("   Buscando cualquier script con datos...")
        all_scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL | re.IGNORECASE)
        print(f"   Total de scripts encontrados: {len(all_scripts)}")
        
        for i, script in enumerate(all_scripts[:5]):  # Mostrar primeros 5
            script = script.strip()
            if script and len(script) > 20:  # No mostrar scripts vacíos o muy cortos
                print(f"   Script {i+1} (primeros 100 chars): {script[:100]}...")
    
    print("\n2. Buscando script con id='counts-data':")
    counts_pattern = r'<script[^>]*id="counts-data"[^>]*>(.*?)</script>'
    counts_match = re.search(counts_pattern, html, re.DOTALL | re.IGNORECASE)
    
    if counts_match:
        counts_content = counts_match.group(1).strip()
        print(f"   ✓ ENCONTRADO")
        print(f"   Contenido (primeros 150 chars): {counts_content[:150]}...")
        
        # Verificar si está vacío
        if not counts_content or counts_content.isspace():
            print("   ¡ADVERTENCIA! El contenido está vacío o solo tiene espacios")
        else:
            # Intentar parsear JSON
            import json
            try:
                counts_list = json.loads(counts_content)
                print(f"   JSON válido, longitud: {len(counts_list)}")
                print(f"   Primeros 5 elementos: {counts_list[:5]}")
                
                # Si tenemos days_list, buscar el valor correspondiente
                if 'days_list' in locals():
                    if '05/03' in days_list:
                        idx = days_list.index('05/03')
                        if idx < len(counts_list):
                            print(f"   Valor para '05/03' (índice {idx}): {counts_list[idx]}")
                        else:
                            print(f"   ERROR: Índice {idx} fuera de rango (longitud: {len(counts_list)})")
            except json.JSONDecodeError as e:
                print(f"   ERROR parseando JSON: {e}")
    else:
        print("   ✗ NO ENCONTRADO")
    
    print("\n3. Verificando si hay datos de ejemplo hardcodeados en JavaScript:")
    example_patterns = [
        r"chartDays\s*=\s*\[\s*['\"]01/03['\"]",
        r"chartCounts\s*=\s*\[\s*12\s*,\s*8\s*,\s*15\s*,\s*20\s*,\s*10\s*\]",
        r"datos de ejemplo",
        r"fallback"
    ]
    
    for pattern in example_patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        if matches:
            print(f"   ¡ADVERTENCIA! Patrón encontrado: {pattern}")
            print(f"   Esto sugiere que el fallback se está ejecutando")
    
    print("\n4. Verificando mensajes de debug en el HTML:")
    debug_pattern = r'console\.(log|warn|error)\([\'\"].*?DEBUG.*?[\'\"]'
    debug_matches = re.findall(debug_pattern, html, re.IGNORECASE)
    
    if debug_matches:
        print(f"   Se encontraron {len(debug_matches)} mensajes de debug en el JavaScript")
        # Extraer algunos mensajes de debug
        debug_msgs = re.findall(r'console\.(log|warn|error)\(([^)]+)\)', html)
        for msg_type, msg_content in debug_msgs[:3]:  # Mostrar primeros 3
            print(f"   {msg_type.upper()}: {msg_content[:100]}...")
    else:
        print("   No se encontraron mensajes de debug")
    
    return html

def main():
    print("VERIFICACIÓN DE ELEMENTOS SCRIPT EN EL HTML GENERADO")
    print("=" * 70)
    
    html = verificar_html_real()
    
    print("\n" + "=" * 70)
    print("INSTRUCCIONES PARA EL USUARIO:")
    print("1. Abre la consola del navegador (F12)")
    print("2. Ve a la pestaña 'Console'")
    print("3. Recarga la página /analisis-crm/")
    print("4. Deberías ver mensajes que empiezan con 'DEBUG:'")
    print("5. Si ves 'Usando datos de ejemplo (fallback activado)', hay un problema")
    print("6. Si ves 'Datos cargados desde Django exitosamente', los datos son correctos")
    print("\nComparte lo que ves en la consola para diagnosticar el problema.")

if __name__ == '__main__':
    main()