#!/usr/bin/env python
"""
Inspecciona el archivo Excel requerimientos_inmobiliarios.xlsx sin Django.
"""
import pandas as pd
import os

def main():
    ruta = os.path.join('data', 'requerimientos_inmobiliarios.xlsx')
    if not os.path.exists(ruta):
        ruta = os.path.join('webapp', 'requerimientos', 'data', 'requerimientos_inmobiliarios.xlsx')
    
    print(f"Leyendo archivo: {ruta}")
    
    try:
        # Leer sin header para ver filas crudas
        df_raw = pd.read_excel(ruta, sheet_name=0, header=None)
        print(f"Dimensiones: {df_raw.shape}")
        print("\nPrimeras 5 filas crudas (mostrando primeras 10 columnas):")
        for i in range(min(5, len(df_raw))):
            row = df_raw.iloc[i]
            values = []
            for j in range(min(10, len(row))):
                val = row.iloc[j]
                if pd.isna(val):
                    values.append('NaN')
                else:
                    values.append(str(val)[:30])
            print(f"Fila {i}: {values}")
        
        # Leer con header en fila 0 (asumiendo que la primera fila es encabezado)
        df = pd.read_excel(ruta, sheet_name=0, header=0)
        print(f"\nColumnas encontradas ({len(df.columns)}):")
        for i, col in enumerate(df.columns):
            print(f"  {i}: '{col}'")
        
        print("\nPrimeras 3 filas de datos:")
        for i in range(min(3, len(df))):
            print(f"\n--- Fila {i} ---")
            for col in df.columns[:12]:  # Mostrar primeras 12 columnas
                val = df.iloc[i][col]
                if pd.isna(val):
                    display = 'NaN'
                else:
                    display = str(val)[:50]
                print(f"  {col}: {display}")
        
        # Verificar valores únicos en columnas clave
        print("\nValores únicos en algunas columnas:")
        for col in ['Fuente', 'Tipo Original', 'Condicion', 'Tipo Propiedad', 'Moneda']:
            if col in df.columns:
                unique_vals = df[col].dropna().unique()
                print(f"{col} ({len(unique_vals)} valores): {list(unique_vals[:10])}")
        
        # Contar filas totales
        print(f"\nTotal filas en Excel: {len(df)}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()