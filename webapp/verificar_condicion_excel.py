#!/usr/bin/env python
"""
Verificar EXACTAMENTE qué valores hay en la columna 'condicion' del Excel.
"""
import os
import sys
import pandas as pd

excel_path = os.path.join('requerimientos', 'data', 'propiedadesraw_corregido (2).xlsx')

print("=== VERIFICACIÓN DETALLADA DE LA COLUMNA 'CONDICION' ===")
print(f"Archivo: {excel_path}")
print("="*70)

# Leer el Excel completo
df = pd.read_excel(excel_path)

# Verificar si existe la columna 'condicion'
if 'condicion' not in df.columns:
    print("ERROR: No existe la columna 'condicion' en el Excel.")
    print("Columnas disponibles:", list(df.columns))
    sys.exit(1)

# Mostrar información general
print(f"Total de filas: {len(df)}")
print(f"Valores únicos en 'condicion': {df['condicion'].nunique()}")
print("\nDistribución de valores:")
distribucion = df['condicion'].value_counts(dropna=False)
for valor, count in distribucion.items():
    porcentaje = (count / len(df)) * 100
    print(f"  '{valor}': {count} registros ({porcentaje:.1f}%)")

# Mostrar ejemplos de cada valor
print("\n" + "="*70)
print("EJEMPLOS POR TIPO DE CONDICIÓN:")

for valor in df['condicion'].dropna().unique():
    print(f"\n--- CONDICIÓN: '{valor}' ---")
    ejemplos = df[df['condicion'] == valor].head(3)
    for idx, row in ejemplos.iterrows():
        print(f"  Fila {idx+1}:")
        print(f"    Tipo: {row.get('tipo_propiedad', 'N/A')}")
        print(f"    Precio: {row.get('precio_usd', 'N/A')}")
        print(f"    Departamento: {row.get('departamento', 'N/A')}")
        print(f"    Distrito: {row.get('distrito', 'N/A')}")

# Verificar valores problemáticos
print("\n" + "="*70)
print("ANÁLISIS DE VALORES PROBLEMÁTICOS:")

# Buscar variaciones de "alquiler"
valores_alquiler = []
for idx, row in df.iterrows():
    val = row['condicion']
    if pd.isna(val):
        continue
    val_str = str(val).lower().strip()
    if 'alquiler' in val_str or 'rent' in val_str or 'arriendo' in val_str:
        valores_alquiler.append((idx, val))

if valores_alquiler:
    print(f"Se encontraron {len(valores_alquiler)} registros con 'alquiler' o similar:")
    for idx, val in valores_alquiler[:10]:  # Mostrar primeros 10
        print(f"  Fila {idx+1}: '{val}'")
else:
    print("No se encontraron registros con 'alquiler' o similar.")

# Buscar variaciones de "venta"
valores_venta = []
for idx, row in df.iterrows():
    val = row['condicion']
    if pd.isna(val):
        continue
    val_str = str(val).lower().strip()
    if 'venta' in val_str or 'sale' in val_str or 'vende' in val_str:
        valores_venta.append((idx, val))

print(f"\nRegistros con 'venta' o similar: {len(valores_venta)}")

# Mostrar primeros 5 registros crudos
print("\n" + "="*70)
print("PRIMEROS 5 REGISTROS CRUDOS (columna 'condicion'):")
for idx, row in df.head(5).iterrows():
    print(f"  Fila {idx+1}: condicion='{row['condicion']}'")

print("\n" + "="*70)
print("VERIFICACIÓN COMPLETADA.")