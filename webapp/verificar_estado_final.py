#!/usr/bin/env python
"""
Script final para verificar el estado de las columnas y recomendar pasos.
"""

import os
import sys
import django
from django.db import connection

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

def main():
    print("=== VERIFICACIÓN FINAL DEL ESTADO ===\n")
    
    # 1. Verificar columnas
    print("1. Verificando columnas en la base de datos...")
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT TABLE_SCHEMA, TABLE_NAME
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME LIKE '%propiedadraw%'
        """)
        tablas = cursor.fetchall()
        
        if not tablas:
            print("  ✗ ERROR: No se encontró ninguna tabla 'propiedadraw'.")
            return
        
        todas_las_columnas_existen = True
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
                    todas_las_columnas_existen = False
    
    # 2. Verificar migraciones
    print("\n2. Verificando migraciones aplicadas...")
    try:
        from django.db.migrations.recorder import MigrationRecorder
        recorder = MigrationRecorder(connection)
        migraciones = recorder.applied_migrations()
        
        migraciones_ingestas = [m for m in migraciones if m[0] == 'ingestas']
        print(f"  Migraciones aplicadas para 'ingestas': {len(migraciones_ingestas)}")
        
        # Buscar migración reciente
        migraciones_recientes = sorted(migraciones_ingestas, key=lambda x: x[1])[-5:]
        for app, nombre in migraciones_recientes:
            print(f"    - {nombre}")
    except Exception as e:
        print(f"  ✗ Error al verificar migraciones: {e}")
    
    # 3. Recomendaciones
    print("\n=== RECOMENDACIONES FINALES ===")
    
    if todas_las_columnas_existen:
        print("✓ TODAS LAS COLUMNAS EXISTEN")
        print("\nPASOS A SEGUIR:")
        print("1. REINICIA el servidor Django (si está corriendo, detenlo y vuelve a iniciarlo)")
        print("2. Después de reiniciar, prueba acceder a:")
        print("   - http://localhost:8000/admin/ingestas/propiedadraw/")
        print("   - http://localhost:8000/ingestas/propiedades/ (templates)")
        print("\n3. Si aún hay errores, ejecuta: python manage.py migrate ingestas --fake")
    else:
        print("✗ FALTAN COLUMNAS")
        print("\nPASOS A SEGUIR:")
        print("1. Ejecuta el script de creación de migración:")
        print("   python webapp/crear_migracion_faltante.py")
        print("\n2. Si falla, agrega las columnas manualmente con SQL:")
        print("   ALTER TABLE [schema].[tabla] ADD condicion NVARCHAR(20) NULL")
        print("   ALTER TABLE [schema].[tabla] ADD propiedad_verificada BIT NULL")
        print("\n3. Después de agregar columnas, reinicia el servidor Django")
    
    print("\n=== COMANDOS PARA REINICIAR SERVIDOR ===")
    print("Si el servidor está corriendo en otra terminal:")
    print("1. Presiona Ctrl+C en la terminal del servidor")
    print("2. Ejecuta: cd webapp && python manage.py runserver")
    print("\nO si usas un proceso en segundo plano:")
    print("1. Encuentra el proceso: netstat -ano | findstr :8000")
    print("2. Termínalo: taskkill /PID [PID] /F")
    print("3. Reinicia: cd webapp && python manage.py runserver")

if __name__ == '__main__':
    main()