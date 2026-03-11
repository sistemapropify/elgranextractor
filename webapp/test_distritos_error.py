#!/usr/bin/env python
"""Script para probar la función obtener_distritos_por_mes y detectar errores."""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

django.setup()

from requerimientos.analytics import obtener_distritos_por_mes
from django.db import connection

print("=== Probando función obtener_distritos_por_mes ===")

try:
    # Probar con parámetros simples
    print("1. Probando sin parámetros...")
    resultado = obtener_distritos_por_mes()
    print(f"   Éxito! Distritos encontrados: {len(resultado['distritos'])}")
    print(f"   Meses: {len(resultado['meses'])}")
    
except Exception as e:
    print(f"   ERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

print("\n2. Probando conexión a base de datos...")
try:
    with connection.cursor() as cursor:
        cursor.execute("SELECT TOP 1 id FROM requerimiento")
        row = cursor.fetchone()
        print(f"   Conexión OK. Primer requerimiento ID: {row[0] if row else 'Ninguno'}")
except Exception as e:
    print(f"   ERROR en conexión: {e}")

print("\n3. Probando consulta STRING_SPLIT...")
try:
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT DISTINCT TRIM(value) as distrito
            FROM requerimiento
            CROSS APPLY STRING_SPLIT(distritos, ',')
            WHERE TRIM(value) != ''
            ORDER BY distrito
        """)
        distritos = [row[0] for row in cursor.fetchall()]
        print(f"   Consulta OK. Distritos encontrados: {len(distritos)}")
        if distritos:
            print(f"   Primeros 5: {distritos[:5]}")
except Exception as e:
    print(f"   ERROR en STRING_SPLIT: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

print("\n=== Prueba completada ===")