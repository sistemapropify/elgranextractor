#!/usr/bin/env python
"""
Probar si el gráfico final funciona con datos reales.
"""
import requests
import re
import json

def test_final_graph():
    url = "http://localhost:8000/analisis-crm/"
    print(f"Haciendo solicitud a {url}")
    
    try:
        response = requests.get(url, timeout=5)
        print(f"Status code: {response.status_code}")
        
        # Buscar los elementos script generados por json_script
        days_pattern = r'<script id="days-data".*?>(.*?)</script>'
        counts_pattern = r'<script id="counts-data".*?>(.*?)</script>'
        
        days_match = re.search(days_pattern, response.text, re.DOTALL)
        counts_match = re.search(counts_pattern, response.text, re.DOTALL)
        
        if days_match and counts_match:
            days_content = days_match.group(1).strip()
            counts_content = counts_match.group(1).strip()
            
            print(f"\n=== DATOS ENCONTRADOS ===")
            print(f"days-data content: '{days_content}'")
            print(f"counts-data content: '{counts_content}'")
            
            # Verificar si están vacíos
            if days_content == '""':
                print("¡ADVERTENCIA: days-data está vacío (cadena vacía)!")
            else:
                # Intentar parsear
                try:
                    days = json.loads(days_content)
                    print(f"Días parseados: {days}")
                    print(f"Número de días: {len(days)}")
                except json.JSONDecodeError as e:
                    print(f"ERROR parseando days JSON: {e}")
                    
            if counts_content == '""':
                print("¡ADVERTENCIA: counts-data está vacío (cadena vacía)!")
            else:
                try:
                    counts = json.loads(counts_content)
                    print(f"Conteos parseados: {counts}")
                    print(f"Número de conteos: {len(counts)}")
                except json.JSONDecodeError as e:
                    print(f"ERROR parseando counts JSON: {e}")
                    
            # Verificar si los datos coinciden con lo esperado
            if days_content != '""' and counts_content != '""':
                try:
                    days = json.loads(days_content)
                    counts = json.loads(counts_content)
                    if len(days) == len(counts) and len(days) > 0:
                        print(f"\n✓ Datos válidos encontrados: {len(days)} días con conteos")
                        print(f"  Ejemplo: {days[:3]}... -> {counts[:3]}...")
                        print(f"  Total de leads en el mes: {sum(counts)}")
                        return True
                    else:
                        print(f"\n✗ Datos inconsistentes: días={len(days)}, conteos={len(counts)}")
                except:
                    pass
        else:
            print("\n✗ No se encontraron los elementos script de datos")
            
        # Verificar si hay errores en la consola de JavaScript
        if 'console.error' in response.text:
            print("\nSe encontraron console.error en el script")
            
        return False
            
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == '__main__':
    success = test_final_graph()
    if success:
        print("\n=== PRUEBA EXITOSA ===")
        print("El gráfico debería cargarse correctamente con datos reales.")
    else:
        print("\n=== PRUEBA FALLIDA ===")
        print("Hay problemas con los datos del gráfico.")