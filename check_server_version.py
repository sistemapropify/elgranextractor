#!/usr/bin/env python
import requests
import re

print("=== VERIFICANDO VERSIÓN DEL SERVIDOR HEATMAP ===")
print()

# URL del heatmap
url = "http://127.0.0.1:8000/market-analysis/heatmap/"

try:
    response = requests.get(url, timeout=10)
    html = response.text
    
    print(f"Status: {response.status_code}")
    print(f"Tamaño HTML: {len(html)} caracteres")
    
    # Buscar evidencia de la lógica de terrenos en el HTML generado
    # El heatmap_view genera HTML con datos JSON incrustados
    
    # Buscar el JSON de heatmapData
    pattern = r'var heatmapData\s*=\s*JSON\.parse\(\'([^\']+)\'\)'
    match = re.search(pattern, html)
    
    if match:
        import json
        json_str = match.group(1).replace('\\"', '"').replace("\\'", "'").replace('\\\\', '\\')
        try:
            data = json.loads(json_str)
            print(f"Datos heatmap encontrados: {len(data)} puntos")
            
            # Buscar terrenos
            terrenos = [p for p in data if 'tipo_propiedad' in p and p['tipo_propiedad'] and 'terreno' in p['tipo_propiedad'].lower()]
            print(f"Terrenos en datos incrustados: {len(terrenos)}")
            
            if terrenos:
                # Verificar un terreno
                t = terrenos[0]
                print(f"\nEjemplo de terreno (ID {t.get('id')}):")
                print(f"  Tipo: {t.get('tipo_propiedad')}")
                print(f"  Precio/m²: {t.get('precio_m2')}")
                print(f"  Área construida: {t.get('area_construida')}")
                print(f"  Área terreno: {t.get('area_terreno')}")
                
                # Verificar cálculo
                if t.get('precio_usd') and t.get('precio_m2'):
                    # Intentar deducir qué área usó
                    if t.get('area_terreno') and t.get('area_terreno') > 0:
                        calc_terreno = t['precio_usd'] / t['area_terreno']
                        print(f"  Cálculo con área terreno: {t['precio_usd']} / {t['area_terreno']} = {calc_terreno:.2f}")
                        
                        if abs(calc_terreno - t['precio_m2']) < 0.01:
                            print("  ✓ CORRECTO: Usa área terreno")
                        else:
                            print("  ✗ POSIBLE ERROR: No coincide con área terreno")
                            
                            if t.get('area_construida') and t.get('area_construida') > 0:
                                calc_construida = t['precio_usd'] / t['area_construida']
                                print(f"  Cálculo con área construida: {t['precio_usd']} / {t['area_construida']} = {calc_construida:.2f}")
                                if abs(calc_construida - t['precio_m2']) < 0.01:
                                    print("  ✗ ERROR CONFIRMADO: Está usando área construida")
        except json.JSONDecodeError as e:
            print(f"Error decodificando JSON: {e}")
    else:
        print("No se encontró heatmapData en el HTML")
        
        # Buscar otra evidencia
        if "es_terreno" in html:
            print("✓ Encontrado 'es_terreno' en HTML (lógica de detección presente)")
        else:
            print("✗ 'es_terreno' no encontrado (posible versión antigua)")
            
        if "Si es terreno, usar solo área de terreno" in html:
            print("✓ Comentario de lógica encontrado")
        else:
            print("✗ Comentario de lógica no encontrado")
    
    # Verificar si hay código JavaScript que calcule precio/m²
    if "precio_usd / area" in html or "precio_usd/area" in html:
        print("\n✓ Encontrado cálculo de precio/m² en JavaScript")
    
    # Buscar la fecha/hora de generación
    import datetime
    print(f"\nHora de verificación: {datetime.datetime.now()}")
    
except Exception as e:
    print(f"Error: {e}")

print("\n=== CONCLUSIÓN ===")
print("Si 'es_terreno' no aparece en el HTML, el servidor puede estar ejecutando")
print("una versión antigua del código (cache o sin reinicio).")
print()
print("Solución: Reiniciar el servidor Django con:")
print("  cd webapp && py manage.py runserver --noreload 0.0.0.0:8000")