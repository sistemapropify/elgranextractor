#!/usr/bin/env python
"""
ÚLTIMO INTENTO: Script que fuerza la creación de columnas y reinicia el servidor.
"""

import os
import sys
import django
import time
import subprocess
from django.db import connection

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prometeo.settings')
django.setup()

def ejecutar_sql(query, params=None):
    with connection.cursor() as cursor:
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        try:
            return cursor.fetchall()
        except:
            return None

def main():
    print("=== ÚLTIMO INTENTO DE REPARACIÓN ===")
    
    # 1. Encontrar tabla
    tablas = ejecutar_sql("""
        SELECT TABLE_SCHEMA, TABLE_NAME
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_NAME LIKE '%propiedadraw%'
    """)
    
    if not tablas:
        print("ERROR: No se encontró la tabla.")
        return
    
    tabla = f"{tablas[0][0]}.{tablas[0][1]}"
    print(f"Tabla: {tabla}")
    
    # 2. Agregar columnas sin verificar (usando TRY-CATCH en SQL)
    sql_commands = [
        f"""
        BEGIN TRY
            ALTER TABLE {tabla} ADD condicion NVARCHAR(20) NULL
            PRINT 'Columna condicion agregada'
        END TRY
        BEGIN CATCH
            PRINT 'Columna condicion ya existe o error: ' + ERROR_MESSAGE()
        END CATCH
        """,
        f"""
        BEGIN TRY
            ALTER TABLE {tabla} ADD propiedad_verificada BIT NULL
            PRINT 'Columna propiedad_verificada agregada'
        END TRY
        BEGIN CATCH
            PRINT 'Columna propiedad_verificada ya existe o error: ' + ERROR_MESSAGE()
        END CATCH
        """,
        f"""
        UPDATE {tabla} SET condicion = 'no_especificado' WHERE condicion IS NULL
        """,
        f"""
        UPDATE {tabla} SET propiedad_verificada = 0 WHERE propiedad_verificada IS NULL
        """
    ]
    
    for sql in sql_commands:
        try:
            ejecutar_sql(sql)
            print(f"Ejecutado: {sql[:50]}...")
        except Exception as e:
            print(f"Error: {e}")
    
    # 3. Verificar columnas
    columnas = ejecutar_sql(f"""
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = '{tabla.split('.')[1]}'
    """)
    
    if columnas:
        columnas_set = {col[0].lower() for col in columnas}
        print("\nColumnas existentes:")
        for col in sorted(columnas_set):
            print(f"  - {col}")
        
        if 'condicion' in columnas_set and 'propiedad_verificada' in columnas_set:
            print("\n¡ÉXITO! Ambas columnas existen.")
        else:
            print("\nADVERTENCIA: Algunas columnas aún faltan.")
    
    # 4. Aplicar migraciones de Django
    print("\nAplicando migraciones de Django...")
    try:
        output = subprocess.check_output(
            ['python', 'manage.py', 'migrate', 'ingestas', '--fake'],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stderr=subprocess.STDOUT,
            text=True
        )
        print(output)
    except subprocess.CalledProcessError as e:
        print(f"Error fake migrate: {e.output}")
    
    # 5. Reiniciar servidor (sugerencia)
    print("\n=== INSTRUCCIONES FINALES ===")
    print("1. Detén el servidor Django (Ctrl+C)")
    print("2. Ejecuta: python manage.py runserver")
    print("3. Accede a http://127.0.0.1:8000/admin/ingestas/propiedadraw/")
    print("\nSi el error persiste, el problema puede ser de caché de Django.")
    print("Intenta ejecutar: python manage.py shell -c \"from django.db import connection; connection.close()\"")
    print("Luego reinicia el servidor.")

if __name__ == '__main__':
    main()