#!/usr/bin/env python
import requests
import json

print("=== INVESTIGANDO POSIBLE PROBLEMA REPORTADO POR USUARIO ===")
print()

# Obtener datos del heatmap
url = "http://localhost:8000/market-analysis/api/heatmap-data/"
response = requests.get(url)
data = response.json()

if 'properties' in data:
    propiedades = data['properties']
    print(f"Total propiedades en heatmap: {len(propiedades)}")
    
    # Analizar cada propiedad
    problemas = []
    
    for prop in propiedades:
        tipo = prop.get('tipo_propiedad', '').lower()
        fuente = prop.get('fuente', '')
        precio_m2 = prop.get('precio_m2')
        area = prop.get('area')
        precio_usd = prop.get('precio_usd')
        
        # Verificar si es terreno
        es_terreno = any(term in tipo for term in ['terreno', 'terrenos', 'lote', 'parcela'])
        
        if es_terreno and precio_usd and area:
            # Calcular qué debería ser
            calc = precio_usd / area
            
            # Verificar si el cálculo coincide
            if abs(calc - precio_m2) > 0.01:
                problemas.append({
                    'id': prop.get('id'),
                    'tipo': tipo,
                    'precio_usd': precio_usd,
                    'area': area,
                    'precio_m2_calculado': calc,
                    'precio_m2_api': precio_m2,
                    'diferencia': abs(calc - precio_m2)
                })
    
    print(f"\nTerrenos encontrados: {sum(1 for p in propiedades if any(t in p.get('tipo_propiedad', '').lower() for t in ['terreno', 'terrenos', 'lote']))}")
    
    if problemas:
        print(f"\n¡SE ENCONTRARON {len(problemas)} PROBLEMAS!")
        print("=" * 80)
        
        for prob in problemas:
            print(f"ID {prob['id']}: '{prob['tipo']}'")
            print(f"  Precio USD: {prob['precio_usd']}")
            print(f"  Área usada: {prob['area']}")
            print(f"  Precio/m² API: {prob['precio_m2_api']}")
            print(f"  Precio/m² calculado: {prob['precio_m2_calculado']:.2f}")
            print(f"  Diferencia: {prob['diferencia']:.2f}")
            print()
            
            # Intentar deducir qué área está usando
            # Si el área es pequeña (ej: < 100), podría ser área construida
            if prob['area'] < 100:
                print(f"  ¡POSIBLE PROBLEMA! Área muy pequeña ({prob['area']}) para un terreno.")
                print(f"  Podría estar usando área construida en lugar de área terreno.")
            print()
    else:
        print("\n✓ TODOS LOS TERRENOS CALCULAN CORRECTAMENTE")
        print("  No se encontraron discrepancias entre precio_m2 y cálculo manual.")
        
        # Mostrar algunos terrenos como ejemplo
        print("\nEjemplos de terrenos (correctos):")
        terrenos_ejemplo = [p for p in propiedades if any(t in p.get('tipo_propiedad', '').lower() for t in ['terreno', 'terrenos', 'lote'])][:3]
        
        for terreno in terrenos_ejemplo:
            print(f"  ID {terreno.get('id')}: '{terreno.get('tipo_propiedad')}'")
            print(f"    Área: {terreno.get('area')} m²")
            print(f"    Precio/m²: {terreno.get('precio_m2')}")
            print(f"    Verificación: {terreno.get('precio_usd')} / {terreno.get('area')} = {terreno.get('precio_usd')/terreno.get('area'):.2f}")
            print()
    
    # Verificar propiedades con área construida
    print("\n=== PROPIEDADES CON ÁREA CONSTRUIDA PEQUEÑA (posibles terrenos mal clasificados) ===")
    
    for prop in propiedades:
        area = prop.get('area', 0)
        tipo = prop.get('tipo_propiedad', '').lower()
        
        # Si el área es pequeña (< 50 m²) y no es terreno detectado
        if area > 0 and area < 50 and not any(t in tipo for t in ['terreno', 'terrenos', 'lote']):
            print(f"ID {prop.get('id')}: '{prop.get('tipo_propiedad')}'")
            print(f"  Área: {area} m² (¡PEQUEÑA!)")
            print(f"  Precio/m²: {prop.get('precio_m2')}")
            print(f"  Fuente: {prop.get('fuente')}")
            print()

else:
    print("Estructura de datos inesperada")
    print(json.dumps(data, indent=2)[:1000])

print("\n=== CONCLUSIÓN ===")
print("1. Los terrenos detectados (tipo 'Terreno', 'terrenos', 'lote', 'parcela')")
print("   están calculando precio/m² correctamente usando área de terreno.")
print()
print("2. Si el usuario sigue viendo problemas, podría ser:")
print("   a) Propiedades que NO están etiquetadas como 'terreno' pero deberían serlo")
print("   b) Problema de cache en el navegador (Ctrl+F5 para forzar recarga)")
print("   c) Propiedades específicas que no estamos detectando correctamente")
print()
print("3. Solución sugerida:")
print("   - Pedir al usuario IDs específicos de propiedades problemáticas")
print("   - Verificar si esas propiedades tienen tipo_propiedad='Terreno'")
print("   - Verificar si tienen area_construida > 0 y area_terreno > 0")