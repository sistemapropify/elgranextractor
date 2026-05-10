# -*- coding: utf-8 -*-
"""
DEBUG: Buscar propiedad especifica LG835530090 - con schema correcto
"""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, '.')
django.setup()

from django.db import connection
from intelligence.models import IntelligenceCollection

import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print("=" * 80)
print("0. ANALIZANDO CONFIGURACION DE COLECCION RAG")
print("=" * 80)

collections = IntelligenceCollection.objects.filter(is_active=True)
for col in collections:
    print(f"\nColeccion: {col.name}")
    print(f"  Tabla origen (source_sql): {col.source_sql}")
    print(f"  Campos de embedding: {col.embedding_fields}")
    print(f"  Campos de display: {col.display_fields}")
    print(f"  Field definitions: {col.field_definitions}")
    print(f"  Documentos: {col.documents.count()}")

print("\n" + "=" * 80)
print("1. DESCUBRIENDO TABLAS DISPONIBLES")
print("=" * 80)

with connection.cursor() as cursor:
    cursor.execute("""
        SELECT TABLE_SCHEMA, TABLE_NAME 
        FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_TYPE = 'BASE TABLE'
        ORDER BY TABLE_SCHEMA, TABLE_NAME
    """)
    tables = cursor.fetchall()
    print(f"\nTablas disponibles ({len(tables)}):")
    for t in tables:
        print(f"  {t[0]}.{t[1]}")

print("\n" + "=" * 80)
print("2. BUSCANDO TABLAS RELACIONADAS CON PROPIEDADES")
print("=" * 80)

with connection.cursor() as cursor:
    cursor.execute("""
        SELECT TABLE_SCHEMA, TABLE_NAME 
        FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_TYPE = 'BASE TABLE'
          AND (TABLE_NAME LIKE '%prop%' OR TABLE_NAME LIKE '%inmueble%' OR TABLE_NAME LIKE '%property%')
        ORDER BY TABLE_SCHEMA, TABLE_NAME
    """)
    prop_tables = cursor.fetchall()
    print(f"\nTablas de propiedades ({len(prop_tables)}):")
    for t in prop_tables:
        print(f"  {t[0]}.{t[1]}")
        
        # Get columns for each property table
        cursor.execute("""
            SELECT COLUMN_NAME, DATA_TYPE
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
        """, [t[0], t[1]])
        cols = cursor.fetchall()
        print(f"    Columnas ({len(cols)}):")
        for c in cols:
            print(f"      - {c[0]} ({c[1]})")

print("\n" + "=" * 80)
print("3. DIAGNOSTICO COMPLETADO")
print("=" * 80)
