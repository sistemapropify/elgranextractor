import pandas as pd
import sys

path = 'data/requerimientos_completo.xlsx'
xl = pd.ExcelFile(path)
print('Hojas:', xl.sheet_names)
df = xl.parse('Todos los Registros', nrows=10)
print('Columnas:', list(df.columns))

# Mapeo igual que en admin.py
mapeo_columnas = {
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

def convertir_valor(campo, valor):
    if pd.isna(valor):
        return None
    if isinstance(valor, str):
        valor = valor.strip()
        if valor == '':
            return None
    if campo == 'es_urgente':
        if isinstance(valor, bool):
            return valor
        if isinstance(valor, (int, float)):
            return bool(valor)
        if isinstance(valor, str):
            lower = valor.lower()
            if lower in ('si', 'sí', 'true', 'verdadero', '1', 'yes'):
                return True
            elif lower in ('no', 'false', 'falso', '0'):
                return False
    if campo in ('habitaciones', 'banos', 'cochera', 'ascensor', 'piso_preferencia'):
        if valor is None:
            return None
        try:
            return int(float(valor))
        except:
            return None
    if campo == 'area_m2':
        if valor is None:
            return None
        try:
            return float(valor)
        except:
            return None
    if campo == 'presupuesto_monto':
        if valor is None:
            return None
        try:
            return float(valor)
        except:
            return None
    if campo == 'fecha' and isinstance(valor, pd.Timestamp):
        return valor.date()
    if campo == 'hora' and isinstance(valor, pd.Timestamp):
        return valor.time()
    return valor

for idx, row in df.iterrows():
    datos = {}
    for campo_modelo, col_excel in mapeo_columnas.items():
        if col_excel in df.columns:
            valor = row[col_excel]
            datos[campo_modelo] = convertir_valor(campo_modelo, valor)
        else:
            datos[campo_modelo] = None
    print(f'\n--- Fila {idx} ---')
    for k, v in datos.items():
        if v is not None:
            print(f'  {k}: {v} ({type(v).__name__})')

print('\nPrueba completada.')