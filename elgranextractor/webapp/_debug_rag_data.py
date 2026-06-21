"""
Debug: Revisar datos RAG y propiedades reales en BD
"""
import os, sys, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, os.path.dirname(__file__))
import django
django.setup()

from intelligence.models import IntelligenceCollection, IntelligenceDocument
from django.db import connections

print("=" * 70)
print("1. COLECCIONES RAG")
print("=" * 70)
for c in IntelligenceCollection.objects.all():
    docs_count = IntelligenceDocument.objects.filter(collection=c).count()
    print(f"\nColección: '{c.name}'")
    print(f"  Tabla: {c.table_name}")
    print(f"  Embedding fields: {c.embedding_fields}")
    print(f"  Display fields: {c.display_fields}")
    print(f"  Filter fields: {c.filter_fields}")
    print(f"  Activa: {c.is_active}")
    print(f"  Documentos: {docs_count}")
    print(f"  Field definitions keys: {list(c.field_definitions.keys())[:15] if isinstance(c.field_definitions, dict) else 'N/A'}")

print("\n" + "=" * 70)
print("2. DOCUMENTOS RAG - PRIMEROS 3")
print("=" * 70)
for doc in IntelligenceDocument.objects.all()[:3]:
    print(f"\nDocumento ID: {doc.id}")
    print(f"  Colección: {doc.collection.name}")
    print(f"  Source ID: {doc.source_id}")
    print(f"  Field values keys: {list(doc.field_values.keys())[:15] if isinstance(doc.field_values, dict) else 'N/A'}")
    print(f"  Content (primeros 300 chars): {doc.content[:300] if doc.content else 'VACIO'}")

print("\n" + "=" * 70)
print("3. DATOS EN BD PROPRIFY - PROPIEDADES EN CAYMA")
print("=" * 70)
try:
    conn = connections['propifai']
    with conn.cursor() as cursor:
        # Buscar tablas que podrian tener propiedades
        cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME")
        tables = [r[0] for r in cursor.fetchall()]
        print(f"Tablas disponibles en propifai: {tables[:20]}...")
        
        # Buscar propiedades en Cayma
        for table in tables:
            try:
                cursor.execute(f"SELECT TOP 3 COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='{table}'")
                cols = cursor.fetchall()
                col_names = [c[0] for c in cols]
                
                # Ver si tiene district, precio, moneda
                has_district = any('distrito' in c.lower() or 'district' in c.lower() or 'zona' in c.lower() or 'cayma' in c.lower() for c in col_names)
                has_price = any('precio' in c.lower() or 'price' in c.lower() or 'moneda' in c.lower() or 'currency' in c.lower() for c in col_names)
                
                if has_district or has_price:
                    print(f"\nTabla: {table}")
                    print(f"  Columnas: {col_names}")
                    
                    # Buscar registros con Cayma
                    district_cols = [c for c in col_names if 'distrito' in c.lower() or 'district' in c.lower() or 'zona' in c.lower()]
                    if district_cols:
                        for dc in district_cols:
                            try:
                                cursor.execute(f"SELECT COUNT(*) FROM [{table}] WHERE LOWER({dc}) LIKE '%cayma%'")
                                count = cursor.fetchone()[0]
                                if count > 0:
                                    print(f"  Registros con Cayma en '{dc}': {count}")
                                    # Mostrar algunos
                                    cursor.execute(f"SELECT TOP 3 * FROM [{table}] WHERE LOWER({dc}) LIKE '%cayma%'")
                                    rows = cursor.fetchall()
                                    for row in rows:
                                        print(f"    {dict(zip([c[0] for c in cursor.description], row))}")
                            except Exception as e:
                                print(f"  Error buscando Cayma en {dc}: {e}")
            except Exception as e:
                print(f"Error con tabla {table}: {e}")
except Exception as e:
    print(f"Error conectando a propifai: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("4. DATOS EN BD DEFAULT")
print("=" * 70)
try:
    conn = connections['default']
    with conn.cursor() as cursor:
        cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME")
        tables = [r[0] for r in cursor.fetchall()]
        print(f"Tablas disponibles en default: {tables[:20]}...")
        
        # Buscar tablas de propiedades
        for table in tables:
            if any(kw in table.lower() for kw in ['propiedad', 'property', 'inmueble']):
                cursor.execute(f"SELECT TOP 3 COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='{table}'")
                cols = [r[0] for r in cursor.fetchall()]
                print(f"\nTabla: {table}")
                print(f"  Columnas: {cols}")
                cursor.execute(f"SELECT TOP 2 * FROM [{table}]")
                rows = cursor.fetchall()
                for row in rows:
                    print(f"  {dict(zip(cols, row))}")
except Exception as e:
    print(f"Error: {e}")
