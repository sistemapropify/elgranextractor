import pandas as pd

path = 'data/requerimientos_completo.xlsx'
hoja = 'Todos los Registros'
# Leer sin header para ver filas crudas
df_raw = pd.read_excel(path, sheet_name=hoja, header=None)
print("Primeras 10 filas crudas (columnas 0-5):")
for i in range(10):
    print(f"Fila {i}: {list(df_raw.iloc[i, :5])}")

# Leer con header en fila 1 (suponiendo que los encabezados están en fila 1)
df = pd.read_excel(path, sheet_name=hoja, header=1)
print("\n--- Con header en fila 1 ---")
print(f"Columnas: {list(df.columns)}")
print(f"Total filas: {len(df)}")
print("Primeras 5 filas de 'Fuente':")
for i in range(5):
    val = df.iloc[i]['Fuente'] if 'Fuente' in df.columns else 'NO COL'
    print(f"  Fila {i}: {repr(val)}")
    # Verificar si es NaN
    if pd.isna(val):
        print("    -> ES NaN")

# Verificar si hay filas donde 'Fuente' es NaN
if 'Fuente' in df.columns:
    nulos = df['Fuente'].isna().sum()
    print(f"\nTotal valores NaN en 'Fuente': {nulos}")
    if nulos > 0:
        print("Filas con NaN:")
        for idx, row in df[df['Fuente'].isna()].head().iterrows():
            print(f"  Fila {idx}: {row.tolist()[:3]}")