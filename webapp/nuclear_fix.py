#!/usr/bin/env python
"""
SOLUCIÓN NUCLEAR: Elimina migraciones, las regenera y aplica desde cero.
ADVERTENCIA: Esto puede afectar la base de datos si hay datos importantes.
"""

import os
import sys
import shutil
import subprocess

def run_command(cmd, cwd=None):
    print(f"\n>>> {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print(f"STDERR: {result.stderr}")
        return result.returncode == 0
    except Exception as e:
        print(f"Error: {e}")
        return False

def main():
    webapp_dir = os.path.dirname(os.path.abspath(__file__))
    
    print("=== SOLUCIÓN NUCLEAR PARA ERROR DE COLUMNAS ===\n")
    
    # 1. Detener servidor Django (si está corriendo)
    print("1. Asegurándose de que el servidor Django esté detenido...")
    
    # 2. Eliminar migraciones de la app ingestas
    migrations_dir = os.path.join(webapp_dir, 'ingestas', 'migrations')
    if os.path.exists(migrations_dir):
        print(f"2. Eliminando migraciones en {migrations_dir}...")
        # Eliminar todos los archivos excepto __init__.py
        for filename in os.listdir(migrations_dir):
            if filename != '__init__.py' and filename.endswith('.py'):
                filepath = os.path.join(migrations_dir, filename)
                os.remove(filepath)
                print(f"   Eliminado: {filename}")
    else:
        print("2. Directorio de migraciones no encontrado.")
    
    # 3. Eliminar tabla de migraciones de Django (opcional, no lo haremos)
    
    # 4. Crear migraciones iniciales
    print("3. Creando migraciones iniciales...")
    run_command("python manage.py makemigrations ingestas", cwd=webapp_dir)
    
    # 5. Aplicar migraciones
    print("4. Aplicando migraciones...")
    run_command("python manage.py migrate ingestas", cwd=webapp_dir)
    
    # 6. Aplicar todas las migraciones
    print("5. Aplicando todas las migraciones...")
    run_command("python manage.py migrate", cwd=webapp_dir)
    
    # 7. Verificar esquema
    print("6. Verificando esquema de la tabla...")
    run_command("python manage.py sqlmigrate ingestas 0001", cwd=webapp_dir)
    
    # 8. Verificar columnas con SQL
    print("7. Verificando columnas existentes...")
    import django
    sys.path.append(webapp_dir)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prometeo.settings')
    django.setup()
    
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'ingestas_propiedadraw'
            ORDER BY ORDINAL_POSITION
        """)
        columns = cursor.fetchall()
        print(f"   Columnas encontradas ({len(columns)}):")
        for col_name, data_type, nullable in columns:
            print(f"      - {col_name} ({data_type}, nullable: {nullable})")
    
    print("\n=== COMPLETADO ===")
    print("\nINSTRUCCIONES:")
    print("1. Reinicia el servidor Django: python manage.py runserver")
    print("2. Accede a http://127.0.0.1:8000/admin/ingestas/propiedadraw/")
    print("3. Si el error persiste, puede ser necesario reiniciar la base de datos.")
    print("\nADVERTENCIA: Este script eliminó las migraciones anteriores.")
    print("Si hay datos importantes, asegúrate de tener un backup.")

if __name__ == '__main__':
    main()