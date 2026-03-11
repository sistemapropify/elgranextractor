#!/usr/bin/env python
"""
Test simple para verificar el método de intercalado.
"""

print("=== TEST DE INTERCALADO SIMPLE ===\n")

# Simular el algoritmo de intercalado
listas_propiedades = [
    ('local', [{'id': f'L{i}', 'es_propify': False} for i in range(5)]),
    ('propify', [{'id': f'P{i}', 'es_propify': True} for i in range(3)]),
]

print("1. Listas de entrada:")
for fuente, props in listas_propiedades:
    print(f"   - {fuente}: {len(props)} propiedades")

# Algoritmo de intercalado actual
todas_propiedades = []
max_len = max(len(propiedades) for _, propiedades in listas_propiedades)

print(f"\n2. Intercalando (max_len={max_len}):")
for i in range(max_len):
    for fuente, propiedades in listas_propiedades:
        if i < len(propiedades):
            prop = propiedades[i].copy()
            prop['_fuente_original'] = fuente
            todas_propiedades.append(prop)
            print(f"   i={i}: Agregando de {fuente} - {prop['id']}")

print(f"\n3. Resultado: {len(todas_propiedades)} propiedades")
print(f"   Orden: {[p['id'] for p in todas_propiedades]}")

# Verificar el problema: cuando solo hay Propify
print("\n4. Test con solo Propify:")
listas_solo_propify = [
    ('propify', [{'id': f'P{i}', 'es_propify': True} for i in range(3)]),
]

todas_solo_propify = []
max_len = max(len(propiedades) for _, propiedades in listas_solo_propify)

for i in range(max_len):
    for fuente, propiedades in listas_solo_propify:
        if i < len(propiedades):
            prop = propiedades[i].copy()
            prop['_fuente_original'] = fuente
            todas_solo_propify.append(prop)

print(f"   Resultado: {len(todas_solo_propify)} propiedades")
print(f"   Orden: {[p['id'] for p in todas_solo_propify]}")

# El problema: cuando solo hay una fuente, el algoritmo funciona correctamente
# Pero cuando hay múltiples fuentes con diferentes tamaños, el intercalado puede no ser óptimo
print("\n5. Problema potencial:")
print("   - Si hay 857 locales y 43 Propify, max_len = 857")
print("   - Para i=0: agregar local[0], luego propify[0]")
print("   - Para i=1: agregar local[1], luego propify[1]")
print("   - ...")
print("   - Para i=42: agregar local[42], luego propify[42] (última Propify)")
print("   - Para i=43..856: solo agregar locales (ya no hay más Propify)")
print("   - Resultado: Las 43 Propify aparecen en las primeras 86 posiciones")
print("   - Con paginación de 12: primera página tendrá 6 locales y 6 Propify (si i<12)")
print("   - ¡Esto debería funcionar! Las Propify aparecerían en la primera página")