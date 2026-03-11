import pandas as pd
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

df = pd.read_excel('requerimientos/data/requerimientos_completo.xlsx', sheet_name='Todos los Registros', header=1)
print("Shape:", df.shape)
print("Columna 21 (índice 21) primera fila:", repr(df.iloc[0, 21]) if len(df.columns) > 21 else "no existe")
print("Tipo:", type(df.iloc[0, 21]))

# Simular la función convertir_valor
def convertir_valor(campo, valor):
    if pd.isna(valor):
        return None
    if isinstance(valor, str):
        valor = valor.strip()
        if valor == '':
            return None
    # Truncar si es string
    if isinstance(valor, str):
        max_lengths = {'requerimiento': 500}
        if campo in max_lengths:
            max_len = max_lengths[campo]
            if len(valor) > max_len:
                valor = valor[:max_len]
    return valor

valor = df.iloc[0, 21]
result = convertir_valor('requerimiento', valor)
print("Resultado después de convertir_valor:", repr(result))
print("Longitud:", len(result) if result else 0)