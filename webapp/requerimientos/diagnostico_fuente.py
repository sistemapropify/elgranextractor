import pandas as pd
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/..')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
import django
django.setup()

from requerimientos.models import FuenteChoices

path = 'data/requerimientos_completo.xlsx'
print("Leyendo archivo Excel...")
try:
    xl = pd.ExcelFile(path)
    print(f"Hojas: {xl.sheet_names}")
    # Usar la hoja 'Todos los Registros'
    hoja = 'Todos los Registros' if 'Todos los Registros' in xl.sheet_names else xl.sheet_names[0]
    df = xl.parse(hoja)
    print(f"Total filas: {len(df)}")
    print(f"Columnas: {list(df.columns)}")
    print("\n--- Análisis de columna 'Fuente' ---")
    if 'Fuente' in df.columns:
        print("Columna 'Fuente' encontrada.")
        print(f"Tipo de datos: {df['Fuente'].dtype}")
        print(f"Valores nulos: {df['Fuente'].isna().sum()}")
        print(f"Valores únicos (primeros 10): {df['Fuente'].unique()[:10]}")
        print("\nPrimeras 5 filas de 'Fuente':")
        for i, val in enumerate(df['Fuente'].head()):
            print(f"  Fila {i}: {repr(val)}")
        # Verificar si hay valores que no coincidan con FuenteChoices
        print("\nCoincidencia con FuenteChoices:")
        for val in df['Fuente'].dropna().unique()[:20]:
            if isinstance(val, str):
                val_strip = val.strip()
                # Buscar en choices
                found = any(choice.value == val_strip for choice in FuenteChoices)
                print(f"  '{val_strip}' -> {'OK' if found else 'NO COINCIDE'}")
    else:
        print("ERROR: No se encontró columna 'Fuente'.")
        print("Columnas disponibles:")
        for col in df.columns:
            print(f"  '{col}'")
    # Verificar mapeo
    print("\n--- Mapeo actual ---")
    mapeo = {
        'fuente': 'Fuente',
        'fecha': 'Fecha',
        'hora': 'Hora',
        'agente': 'Agente',
        'agente_telefono': 'Tel Agente',
        'tipo_original': 'Tipo Original',
        'condicion': 'Condicion',
        'tipo_propiedad': 'Tipo Propiedad',
        'distritos': 'Distritos',
        'requerimiento': 'Requerimiento',
        'presupuesto_monto': 'Presupuesto Monto',
        'presupuesto_moneda': 'Moneda',
        'presupuesto_forma_pago': 'Forma Pago',
        'habitaciones': 'Habitaciones',
        'banos': 'Banos',
        'cochera': 'Cochera',
        'ascensor': 'Ascensor',
        'amueblado': 'Amueblado',
        'area_m2': 'Area m2',
        'piso_preferencia': 'Piso Preferencia',
        'caracteristicas_extra': 'Caracteristicas Extra',
    }
    for campo, col_excel in mapeo.items():
        exists = col_excel in df.columns
        print(f"{campo} -> '{col_excel}' : {'EXISTE' if exists else 'FALTA'}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()