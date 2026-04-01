#!/usr/bin/env python
"""
Script para inspeccionar el archivo Excel y verificar la columna de condición.
"""
import os
import sys
import pandas as pd

excel_path = os.path.join('requerimientos', 'data', 'propiedadesraw_corregido (2).xlsx')

print(f"Inspeccionando archivo: {excel_path}")
print("="*60)

try:
    # Leer solo las primeras filas para ver estructura
    df = pd.read_excel(excel_path, nrows=5)
    
    print(f"Total de columnas: {len(df.columns)}")
    print(f"Total de filas (muestra): {len(df)}")
    print("\nColumnas encontradas:")
    for i, col in enumerate(df.columns, 1):
        print(f"{i:2}. {col}")
    
    print("\n" + "="*60)
    print("Buscando columnas relacionadas con condición/operación:")
    
    posibles = ['condicion', 'Condición', 'Operación', 'Venta/Alquiler', 'Tipo Operación', 'condición', 'tipo_operacion', 'tipo operacion']
    encontradas = []
    
    for col in df.columns:
        col_lower = str(col).lower()
        for posible in posibles:
            if posible.lower() in col_lower:
                encontradas.append(col)
                break
    
    if encontradas:
        print(f"Columnas de condición encontradas: {encontradas}")
        print("\nValores únicos en la(s) columna(s):")
        for col in encontradas:
            valores = df[col].dropna().unique()
            print(f"\nColumna '{col}':")
            for val in valores[:10]:  # Mostrar primeros 10 valores
                print(f"  - {val}")
            if len(valores) > 10:
                print(f"  ... y {len(valores)-10} más")
    else:
        print("No se encontraron columnas específicas de condición.")
        print("\nPrimeras filas del DataFrame:")
        print(df.head())
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
print("Inspección completada.")