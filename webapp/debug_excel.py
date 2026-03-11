import pandas as pd
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

df = pd.read_excel('requerimientos/data/requerimientos_completo.xlsx', sheet_name='Todos los Registros', header=1)
print("Columnas:", df.columns.tolist())
print("Número de columnas:", len(df.columns))
# Buscar columna que contenga 'Requerimiento'
for i, col in enumerate(df.columns):
    if isinstance(col, str) and 'Requerimiento' in col:
        print(f"Columna {i}: {col}")
        print("Primeros valores:")
        for j in range(min(5, len(df))):
            val = df.iloc[j, i]
            print(f"  Fila {j}: {repr(val)}")
        break
else:
    print("No se encontró columna 'Requerimiento'")
    # Imprimir todas las columnas
    for i, col in enumerate(df.columns):
        print(f"{i}: {repr(col)}")