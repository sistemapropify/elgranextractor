#!/usr/bin/env python
import requests
import json

print("=== VERIFICACIÓN EN VIVO DEL HEATMAP ===")
print()

# URL del heatmap
url = "http://localhost:8000/market-analysis/api/heatmap-data/"
print(f"Consultando: {url}")

try:
    # Hacer solicitud GET
    response = requests.get(url, timeout=10)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        
        # Verificar estructura
        if 'propiedades' in data:
            propiedades = data['propiedades']
            print(f"Total propiedades: {len(propiedades)}")
            
            # Buscar terrenos
            terrenos = []
            for prop in propiedades:
                # Verificar si es terreno
                tipo = prop.get('tipo_propiedad', '').lower()
                fuente = prop.get('fuente', '')
                
                es_terreno = any(term in tipo for term in ['terreno', 'terrenos', 'lote', 'parcela'])
                
                if es_terreno:
                    terrenos.append(prop)
            
            print(f"Terrenos encontrados: {len(terrenos)}")
            
            if terrenos:
                print("\nANÁLISIS DE TERRENOS:")
                print("-" * 80)
                
                for i, terreno in enumerate(terrenos[:5]):  # Mostrar primeros 5
                    print(f"Terreno {i+1}:")
                    print(f"  ID: {terreno.get('id')}")
                    print(f"  Tipo: '{terreno.get('tipo_propiedad')}'")
                    print(f"  Fuente: {terreno.get('fuente')}")
                    print(f"  Precio/m²: {terreno.get('precio_m2')}")
                    print(f"  Precio USD: {terreno.get('precio_usd')}")
                    print(f"  Área: {terreno.get('area')}")
                    
                    # Calcular qué área debería usar
                    if terreno.get('fuente') == 'local':
                        # Remax - debería usar area_terreno
                        precio = terreno.get('precio_usd')
                        area = terreno.get('area')
                        if precio and area and area > 0:
                            calc = precio / area
                            print(f"  Cálculo: {precio} / {area} = {calc:.2f}")
                            if abs(calc - terreno.get('precio_m2', 0)) > 0.01:
                                print(f"  ¡ADVERTENCIA! precio_m2 no coincide con cálculo")
                    print()
            else:
                print("\nNo se encontraron terrenos en los datos. Probando sin filtro...")
                
                # Mostrar algunas propiedades para verificar
                print("\nPrimeras 5 propiedades (todas):")
                for i, prop in enumerate(propiedades[:5]):
                    print(f"Prop {i+1}: ID={prop.get('id')}, tipo='{prop.get('tipo_propiedad')}', "
                          f"precio_m2={prop.get('precio_m2')}, area={prop.get('area')}")
        
        else:
            print("Estructura de datos inesperada:")
            print(json.dumps(data, indent=2)[:500])
    
    else:
        print(f"Error: {response.text[:200]}")

except Exception as e:
    print(f"Error al conectar: {e}")
    print("\nProbando con Python requests directamente...")
    
    # Intentar con urllib
    import urllib.request
    try:
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
            print(f"Datos obtenidos. Total propiedades: {len(data.get('propiedades', []))}")
            
            # Buscar terrenos
            terrenos = [p for p in data.get('propiedades', []) 
                       if any(term in p.get('tipo_propiedad', '').lower() 
                             for term in ['terreno', 'terrenos', 'lote'])]
            
            print(f"Terrenos encontrados: {len(terrenos)}")
            if terrenos:
                print("\nEjemplo de terreno:")
                t = terrenos[0]
                print(f"  ID: {t.get('id')}")
                print(f"  Tipo: '{t.get('tipo_propiedad')}'")
                print(f"  Precio/m²: {t.get('precio_m2')}")
                print(f"  Área: {t.get('area')}")
                
                # Verificar cálculo
                if t.get('precio_usd') and t.get('area'):
                    calc = t['precio_usd'] / t['area']
                    print(f"  Cálculo manual: {t['precio_usd']} / {t['area']} = {calc:.2f}")
    except Exception as e2:
        print(f"Error con urllib: {e2}")

print()
print("=== VERIFICACIÓN DE CÓDIGO ===")
print("Revisando si los cambios se aplicaron correctamente...")

# Leer el archivo views.py para verificar
import os
views_path = "webapp/market_analysis/views.py"
if os.path.exists(views_path):
    with open(views_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
        # Buscar las secciones corregidas
        if "Si es terreno, usar solo área de terreno" in content:
            print("✓ Lógica de terrenos encontrada en views.py")
        else:
            print("✗ Lógica de terrenos NO encontrada")
            
        # Contar ocurrencias de la lógica
        count_terreno = content.count("es_terreno = any(term in tipo_propiedad")
        print(f"  Ocurrencias de detección de terrenos: {count_terreno}")
        
        # Verificar api_heatmap_data
        if "Calcular área con detección de terrenos" in content:
            print("✓ api_heatmap_data tiene detección de terrenos")
        else:
            print("✗ api_heatmap_data puede no tener detección de terrenos")
else:
    print(f"Archivo {views_path} no encontrado")