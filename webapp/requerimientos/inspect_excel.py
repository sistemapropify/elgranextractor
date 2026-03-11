import pandas as pd
import sys

path = 'data/requerimientos_completo.xlsx'
try:
    xl = pd.ExcelFile(path)
    print('Hojas disponibles:', xl.sheet_names)
    df = xl.parse(xl.sheet_names[0], nrows=10)
    print('Forma:', df.shape)
    print('Columnas:')
    for i, col in enumerate(df.columns):
        print(f'{i+1}. {col}')
    print('\nPrimeras filas:')
    print(df.head(3).to_string())
    print('\nTipos de datos:')
    print(df.dtypes)
except Exception as e:
    print('Error:', e)
    import traceback
    traceback.print_exc()