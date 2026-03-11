#!/usr/bin/env python
"""
Inspecciona el archivo Excel requerimientos_inmobiliarios.xlsx
para entender su estructura y mapear columnas.
"""
import pandas as pd
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

import django
django.setup()

def main():
    ruta = 'data/requerimientos_inmobiliarios.xlsx'
    if not os.path.exists(ruta):
        ruta = os.path.join('webapp', 'requerimientos', 'data', 'requerimientos_inmobiliarios.xlsx')
    
    print(f"Leyendo archivo: {ruta}")
    
    try:
        # Leer sin header para ver filas crudas
        df_raw = pd.read_excel(ruta, sheet_name=0, header=None)
        print(f"Dimensiones: {df_raw.shape}")
        print("\nPrimeras 5 filas crudas:")
        for i in range(min(5, len(df_raw))):
            print(f"Fila {i}: {list(df_raw.iloc[i].head(10).values)}")
        
        # Leer con header en fila 0 (asumiendo que la primera fila es encabezado)
        df = pd.read_excel(ruta, sheet_name=0, header=0)
        print(f"\nColumnas encontradas ({len(df.columns)}):")
        for i, col in enumerate(df.columns):
            print(f"  {i}: '{col}'")
        
        print("\nPrimeras 3 filas de datos:")
        for i in range(min(3, len(df))):
            print(f"\nFila {i}:")
            for col in df.columns[:10]:  # Mostrar primeras 10 columnas
                val = df.iloc[i][col]
                print(f"  {col}: {type(val).__name__} = {repr(val)}")
        
        # Verificar valores únicos en columnas clave
        print("\nValores únicos en algunas columnas:")
        for col in ['Fuente', 'Tipo Original', 'Condicion', 'Tipo Propiedad', 'Moneda']:
            if col in df.columns:
                print(f"{col}: {df[col].unique()[:10]}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()