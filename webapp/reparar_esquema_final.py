#!/usr/bin/env python
"""
SCRIPT FINAL PARA REPARAR ESQUEMA DE BASE DE DATOS
Este script realiza todas las acciones necesarias para corregir el error de columnas faltantes.
"""

import os
import sys
import django
import subprocess
from django.db import connection

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prometeo.settings')
django.setup()

def ejecutar_sql(query, params=None):
    """Ejecuta una consulta SQL y devuelve el resultado."""
    with connection.cursor() as cursor:
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        try:
            return cursor.fetchall()
        except:
            return None

def print_seccion(titulo):
    print(f"\n{'='*60}")
    print(f" {titulo}")
    print(f"{'='*60}")

def main():
    print_seccion("REPARACIÓN DE ESQUEMA - PROPIEDADRAW")
    
    # 1. Identificar tabla exacta
    print("\n1. IDENTIFICANDO TABLA...")
    tablas = ejecutar_sql("""
        SELECT TABLE_SCHEMA, TABLE_NAME
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_NAME LIKE '%propiedadraw%'
    """)
    
    if not tablas:
        print("ERROR: No se encontró ninguna tabla 'propiedadraw'.")
        return
    
    tabla_principal = None
    for schema, tabla in tablas:
        print(f"   - {schema}.{tabla}")
        if tabla.lower() == 'ingestas_propiedadraw':
            tabla_principal = f"{schema}.{tabla}"
    
    if not tabla_principal:
        tabla_principal = f"{tablas[0][0]}.{tablas[0][1]}"
    
    print(f"\n   Tabla seleccionada: {tabla_principal}")
    
    # 2. Verificar columnas existentes
    print_seccion("2. VERIFICANDO COLUMNAS")
    columnas = ejecutar_sql(f"""
        SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = '{tabla_principal.split('.')[1]}'
        ORDER BY ORDINAL_POSITION
    """)
    
    print(f"   Total columnas: {len(columnas) if columnas else 0}")
    columnas_set = set()
    if columnas:
        for col_name, data_type, nullable in columnas:
            columnas_set.add(col_name.lower())
            print(f"      {col_name} ({data_type}, nullable: {nullable})")
    
    # 3. Agregar columnas faltantes
    print_seccion("3. AGREGANDO COLUMNAS FALTANTES")
    columnas_faltantes = []
    
    if 'condicion' not in columnas_set:
        columnas_faltantes.append(('condicion', 'NVARCHAR(20) NULL', 'Condición (Venta/Alquiler)'))
    
    if 'propiedad_verificada' not in columnas_set:
        columnas_faltantes.append(('propiedad_verificada', 'BIT NULL', 'Propiedad Verificada'))
    
    if not columnas_faltantes:
        print("   ✓ Todas las columnas requeridas ya existen.")
    else:
        for col_name, tipo, desc in columnas_faltantes:
            print(f"   Agregando columna '{col_name}' ({desc})...")
            try:
                ejecutar_sql(f"ALTER TABLE {tabla_principal} ADD {col_name} {tipo}")
                print(f"   ✓ Columna '{col_name}' agregada exitosamente.")
            except Exception as e:
                print(f"   ✗ Error al agregar '{col_name}': {e}")
    
    # 4. Actualizar valores por defecto
    print_seccion("4. ACTUALIZANDO VALORES POR DEFECTO")
    try:
        # Actualizar condicion a 'no_especificado' donde sea NULL
        resultado = ejecutar_sql(f"""
            UPDATE {tabla_principal}
            SET condicion = 'no_especificado'
            WHERE condicion IS NULL
        """)
        if resultado is not None:
            print(f"   ✓ Valores de 'condicion' actualizados.")
    except Exception as e:
        print(f"   ✗ Error al actualizar 'condicion': {e}")
    
    try:
        # Actualizar propiedad_verificada a 0 donde sea NULL
        resultado = ejecutar_sql(f"""
            UPDATE {tabla_principal}
            SET propiedad_verificada = 0
            WHERE propiedad_verificada IS NULL
        """)
        if resultado is not None:
            print(f"   ✓ Valores de 'propiedad_verificada' actualizados.")
    except Exception as e:
        print(f"   ✗ Error al actualizar 'propiedad_verificada': {e}")
    
    # 5. Verificar migraciones de Django
    print_seccion("5. VERIFICANDO MIGRACIONES DE DJANGO")
    
    # Ejecutar showmigrations
    print("\n   Ejecutando 'python manage.py showmigrations ingestas'...")
    try:
        output = subprocess.check_output(
            ['python', 'manage.py', 'showmigrations', 'ingestas'],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stderr=subprocess.STDOUT,
            text=True
        )
        print("   Salida:")
        for line in output.split('\n'):
            print(f"      {line}")
    except subprocess.CalledProcessError as e:
        print(f"   Error al ejecutar showmigrations: {e.output}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # 6. Aplicar migraciones si es necesario
    print_seccion("6. APLICANDO MIGRACIONES")
    
    aplicar = input("\n   ¿Deseas aplicar las migraciones pendientes? (s/n): ").strip().lower()
    if aplicar == 's':
        try:
            print("   Ejecutando 'python manage.py migrate ingestas'...")
            output = subprocess.check_output(
                ['python', 'manage.py', 'migrate', 'ingestas'],
                cwd=os.path.dirname(os.path.abspath(__file__)),
                stderr=subprocess.STDOUT,
                text=True
            )
            print("   Salida:")
            for line in output.split('\n'):
                print(f"      {line}")
        except subprocess.CalledProcessError as e:
            print(f"   Error al aplicar migraciones: {e.output}")
        except Exception as e:
            print(f"   Error: {e}")
    else:
        print("   Saltando aplicación de migraciones.")
    
    # 7. Verificación final
    print_seccion("7. VERIFICACIÓN FINAL")
    
    # Contar registros
    try:
        resultado = ejecutar_sql(f"SELECT COUNT(*) FROM {tabla_principal}")
        if resultado:
            print(f"   Total registros en la tabla: {resultado[0][0]}")
    except Exception as e:
        print(f"   Error al contar registros: {e}")
    
    # Verificar columnas nuevamente
    columnas_final = ejecutar_sql(f"""
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = '{tabla_principal.split('.')[1]}'
    """)
    
    columnas_final_set = {col[0].lower() for col in columnas_final} if columnas_final else set()
    
    print("\n   Estado de columnas requeridas:")
    for col in ['condicion', 'propiedad_verificada']:
        if col in columnas_final_set:
            print(f"      ✓ '{col}' EXISTE")
        else:
            print(f"      ✗ '{col}' NO EXISTE")
    
    print_seccion("COMPLETADO")
    
    print("\nINSTRUCCIONES FINALES:")
    print("1. Reinicia el servidor Django con: python manage.py runserver")
    print("2. Accede a http://127.0.0.1:8000/admin/ingestas/propiedadraw/")
    print("3. Si el error persiste, contacta al administrador de la base de datos.")
    print("\nEste script ha intentado reparar el esquema. Si el problema continúa,")
    print("puede ser necesario revisar los permisos de la base de datos o")
    print("las migraciones de Django manualmente.")

if __name__ == '__main__':
    main()