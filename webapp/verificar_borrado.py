#!/usr/bin/env python
"""
Script para verificar que propiedadraw está vacía
"""
import os
import sys
import django
from django.db import connection

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

print("=== VERIFICACION DE BORRADO DE PROPIEDADRAW ===")
print("")

try:
    with connection.cursor() as cursor:
        # Contar registros
        cursor.execute("SELECT COUNT(*) FROM ingestas_propiedadraw")
        count = cursor.fetchone()[0]
        
        print(f"Registros en la tabla 'ingestas_propiedadraw': {count}")
        print("")
        
        if count == 0:
            print("ESTADO: TABLA VACIA - BORRADO EXITOSO")
            print("")
            print("Todos los registros de propiedadraw han sido eliminados.")
        else:
            print(f"ESTADO: TABLA NO VACIA - QUEDAN {count} REGISTROS")
            print("")
            print("El borrado no fue completo.")
            
        # Mostrar algunos registros si hay
        if count > 0 and count <= 10:
            cursor.execute("SELECT TOP 5 id, titulo FROM ingestas_propiedadraw")
            rows = cursor.fetchall()
            print("Primeros registros encontrados:")
            for row in rows:
                print(f"  ID: {row[0]}, Titulo: {row[1]}")
        
except Exception as e:
    print(f"Error: {e}")

print("")
print("Verificacion completada.")