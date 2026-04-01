#!/usr/bin/env python
"""
Script para probar si el admin de Django funciona después de agregar las columnas.
"""

import os
import sys
import django
from django.test import Client
from django.urls import reverse

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

def main():
    print("=== PRUEBA DEL ADMIN DE DJANGO ===\n")
    
    # Crear cliente de prueba
    client = Client()
    
    print("1. Probando acceso a la página de login del admin...")
    try:
        response = client.get('/admin/login/')
        if response.status_code == 200:
            print("  ✓ Página de login accesible")
        else:
            print(f"  ✗ Error: código {response.status_code}")
    except Exception as e:
        print(f"  ✗ Error al acceder al login: {e}")
    
    print("\n2. Probando acceso a la lista de PropiedadRaw (requiere autenticación)...")
    try:
        # Intentar acceder directamente (debería redirigir a login)
        response = client.get('/admin/ingestas/propiedadraw/')
        if response.status_code in [200, 302, 403]:
            print(f"  ✓ Página responde con código {response.status_code}")
            
            if response.status_code == 200:
                print("  ✓ ¡Admin funciona correctamente!")
                # Verificar si hay errores de columna en el contenido
                content = response.content.decode('utf-8', errors='ignore')
                if 'Invalid column name' in content or 'ProgrammingError' in content:
                    print("  ✗ ERROR: Todavía hay error de columna en la página")
                else:
                    print("  ✓ No se detectaron errores de columna")
            elif response.status_code == 302:
                print("  ✓ Redirección a login (normal para no autenticado)")
            elif response.status_code == 403:
                print("  ✓ Acceso denegado (normal para no autenticado)")
        else:
            print(f"  ✗ Código inesperado: {response.status_code}")
    except Exception as e:
        error_str = str(e)
        print(f"  ✗ Error al acceder a la página: {error_str}")
        
        # Verificar si es el error de columna
        if 'Invalid column name' in error_str or 'condicion' in error_str.lower() or 'propiedad_verificada' in error_str.lower():
            print("  ✗ ERROR: El problema de columnas persiste")
            print("  ✗ Las columnas 'condicion' y/o 'propiedad_verificada' aún no existen")
        else:
            print(f"  ✗ Otro error: {error_str}")
    
    print("\n3. Verificando columnas directamente en la base de datos...")
    from django.db import connection
    try:
        with connection.cursor() as cursor:
            # Buscar tabla
            cursor.execute("""
                SELECT TABLE_SCHEMA, TABLE_NAME
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_NAME LIKE '%propiedadraw%'
            """)
            tablas = cursor.fetchall()
            
            if tablas:
                for schema, tabla in tablas:
                    print(f"  Tabla: {schema}.{tabla}")
                    
                    for col in ['condicion', 'propiedad_verificada']:
                        cursor.execute("""
                            SELECT COUNT(*)
                            FROM INFORMATION_SCHEMA.COLUMNS
                            WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ? AND COLUMN_NAME = ?
                        """, [schema, tabla, col])
                        existe = cursor.fetchone()[0] > 0
                        
                        if existe:
                            print(f"    ✓ Columna '{col}' EXISTE")
                        else:
                            print(f"    ✗ Columna '{col}' NO EXISTE")
            else:
                print("  ✗ No se encontró la tabla propiedadraw")
    except Exception as e:
        print(f"  ✗ Error al verificar columnas: {e}")
    
    print("\n=== RECOMENDACIONES ===")
    print("1. Si las columnas existen pero el error persiste, reinicia el servidor Django.")
    print("2. Si las columnas no existen, ejecuta 'crear_migracion_faltante.py'.")
    print("3. Después de reiniciar, prueba acceder a: http://localhost:8000/admin/ingestas/propiedadraw/")

if __name__ == '__main__':
    main()