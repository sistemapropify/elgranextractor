import pandas as pd
import sys

try:
    df = pd.read_excel('requerimientos/data/requerimientos_completo.xlsx', sheet_name='Todos los Registros', header=1)
    print('Número de columnas:', len(df.columns))
    print('Nombres de columnas:')
    for i, col in enumerate(df.columns):
        print(f'{i+1}. {repr(col)}')
    
    print('\nPrimera fila de datos:')
    for i, col in enumerate(df.columns):
        val = df.iloc[0][col]
        print(f'{i+1}. {col}: {repr(val)} (tipo: {type(val).__name__})')
    
    print('\nMapeo sugerido:')
    # Basado en lo que veo
    sugerencias = {
        0: 'id_excel',
        1: 'fuente',
        2: 'fecha',
        3: 'hora',
        4: 'agente',
        5: 'tipo_original',
        6: 'condicion',
        7: 'tipo_propiedad',
        8: 'distritos',
        9: 'presupuesto_monto',
        10: 'presupuesto_moneda',
        11: 'presupuesto_forma_pago',
        12: 'habitaciones',
        13: 'banos',
        14: 'cochera',
        15: 'ascensor',
        16: 'amueblado',
        17: 'area_m2',
    }
    
    for idx, campo in sugerencias.items():
        if idx < len(df.columns):
            col_name = df.columns[idx]
            print(f'{campo}: {repr(col_name)}')
            
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()