import pandas as pd
import numpy as np
import os

# Cargar el archivo Excel - ruta correcta (desde el directorio webapp)
excel_path = 'requerimientos/data/propiedadesraw_para_azure.xlsx'
print(f"Intentando cargar archivo desde: {os.path.abspath(excel_path)}")
print(f"¿Existe el archivo? {os.path.exists(excel_path)}")

if os.path.exists(excel_path):
    df = pd.read_excel(excel_path)
else:
    # Intentar ruta alternativa
    excel_path_alt = 'webapp/requerimientos/data/propiedadesraw_para_azure.xlsx'
    print(f"Intentando ruta alternativa: {os.path.abspath(excel_path_alt)}")
    print(f"¿Existe el archivo? {os.path.exists(excel_path_alt)}")
    df = pd.read_excel(excel_path_alt)

print("=== INSPECCIÓN DEL ARCHIVO EXCEL ===")
print(f"Total de filas: {len(df)}")
print(f"Total de columnas: {len(df.columns)}")
print("\nColumnas disponibles:")
for i, col in enumerate(df.columns):
    print(f"  {i+1}. {col}")

print("\n=== MUESTRA DE DATOS ===")
print(df.head(10))

print("\n=== TIPOS DE DATOS ===")
print(df.dtypes)

print("\n=== VALORES NULOS POR COLUMNA ===")
for col in df.columns:
    null_count = df[col].isnull().sum()
    total = len(df)
    print(f"{col}: {null_count} nulos ({null_count/total*100:.1f}%)")

print("\n=== VALORES ÚNICOS EN COLUMNAS CLAVE ===")
columnas_clave = ['tipo_propiedad', 'subtipo_propiedad', 'operacion', 'portal', 'estado_propiedad']
for col in columnas_clave:
    if col in df.columns:
        valores = df[col].dropna().unique()
        print(f"\n{col} ({len(valores)} valores únicos):")
        print(f"  {valores[:20]}")  # Mostrar primeros 20 valores

print("\n=== ESTADÍSTICAS NUMÉRICAS ===")
columnas_numericas = ['precio_usd', 'area_terreno', 'area_construida', 'numero_pisos', 
                      'numero_habitaciones', 'numero_banos', 'numero_cocheras']
for col in columnas_numericas:
    if col in df.columns:
        print(f"\n{col}:")
        print(f"  Min: {df[col].min()}")
        print(f"  Max: {df[col].max()}")
        print(f"  Media: {df[col].mean()}")
        print(f"  No nulos: {df[col].count()}")

print("\n=== MAPEO CON MODELO PropiedadRaw ===")
# Mapeo de columnas Excel a campos del modelo
mapeo = {
    'fuente_excel': 'fuente_excel',
    'fecha_ingesta': 'fecha_ingesta',  # Se usará auto_now_add
    'tipo_propiedad': 'tipo_propiedad',
    'subtipo_propiedad': 'subtipo_propiedad',
    'operacion': None,  # No hay campo directo en el modelo
    'precio_usd': 'precio_usd',
    'descripcion': 'descripcion',
    'portal': 'portal',
    'url_propiedad': 'url_propiedad',
    'coordenadas': 'coordenadas',
    'departamento': 'departamento',
    'provincia': 'provincia',
    'distrito': 'distrito',
    'area_terreno': 'area_terreno',
    'area_construida': 'area_construida',
    'numero_pisos': 'numero_pisos',
    'numero_habitaciones': 'numero_habitaciones',
    'numero_banos': 'numero_banos',
    'numero_cocheras': 'numero_cocheras',
    'agente_inmobiliario': 'agente_inmobiliario',
    'imagenes_propiedad': 'imagenes_propiedad',
    'identificador_externo': 'identificador_externo',
    'fecha_publicacion': 'fecha_publicacion',
    'antiguedad': 'antiguedad',
    'servicio_agua': 'servicio_agua',
    'energia_electrica': 'energia_electrica',
    'servicio_drenaje': 'servicio_drenaje',
    'servicio_gas': 'servicio_gas',
    'telefono_agente': 'telefono_agente',
    'estado_propiedad': 'estado_propiedad'
}

print("Columnas que se mapearán directamente:")
for excel_col, model_field in mapeo.items():
    if model_field:
        print(f"  {excel_col} -> {model_field}")

print("\nColumnas sin mapeo directo (se almacenarán en atributos_extras):")
for excel_col, model_field in mapeo.items():
    if not model_field:
        print(f"  {excel_col}")