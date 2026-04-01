#!/usr/bin/env python
"""
Script ULTIMO para borrar propiedadraw - SIN COMPLICACIONES
"""
import os
import sys
import subprocess

print("=== BORRADO ULTIMO DE PROPIEDADRAW ===")
print("")

# Opción 1: Usar sqlcmd si está disponible
print("Intentando con sqlcmd...")
try:
    # Comando para truncar la tabla
    cmd = 'sqlcmd -S localhost -d prometeo -Q "TRUNCATE TABLE ingestas_propiedadraw"'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        print("✓ Tabla truncada con sqlcmd")
        print("Salida:", result.stdout)
    else:
        print("✗ Error con sqlcmd:", result.stderr)
        print("Intentando método alternativo...")
except Exception as e:
    print("Error:", e)

# Opción 2: Usar el script original de Python
print("\nIntentando con Python Django...")
try:
    # Configurar entorno Django mínimo
    import django
    from django.db import connection
    
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
    django.setup()
    
    with connection.cursor() as cursor:
        # Contar primero
        cursor.execute("SELECT COUNT(*) FROM ingestas_propiedadraw")
        count = cursor.fetchone()[0]
        print(f"Registros encontrados: {count}")
        
        if count > 0:
            # Borrar
            cursor.execute("TRUNCATE TABLE ingestas_propiedadraw")
            print("✓ Tabla truncada con Django")
            
            # Verificar
            cursor.execute("SELECT COUNT(*) FROM ingestas_propiedadraw")
            new_count = cursor.fetchone()[0]
            print(f"Registros después del borrado: {new_count}")
        else:
            print("La tabla ya está vacía")
            
except Exception as e:
    print("Error con Django:", e)

# Opción 3: Mensaje final
print("\n" + "="*50)
print("SI NADA FUNCIONA, EJECUTA MANUALMENTE:")
print("1. Abre SQL Server Management Studio")
print("2. Conéctate a la base de datos")
print("3. Ejecuta: TRUNCATE TABLE ingestas_propiedadraw")
print("="*50)

input("\nPresiona Enter para salir...")