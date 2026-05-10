"""
DEBUG: Buscar propiedad específica LG835530090 y analizar campos de publicidad
"""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, '.')
django.setup()

from django.db import connection

print("=" * 80)
print("1. BUSCANDO PROPIEDAD CON CÓDIGO LG835530090")
print("=" * 80)

with connection.cursor() as cursor:
    # Buscar en properties
    cursor.execute("""
        SELECT p.id, p.titulo, p.descripcion, p.precio, p.moneda, 
               p.direccion, p.codigo_unico_propiedad, p.area_construida, 
               p.area_total, p.num_banios, p.num_dorm, 
               p.estado_conservacion, p.antiguedad, p.piso, p.total_pisos,
               p.latitud, p.longitud, p.condicion, p.tipo_propiedad,
               p.operacion, p.estado, p.moneda_precio, p.precio_dolares,
               p.precio_soles, p.area_terreno
        FROM properties p 
        WHERE p.codigo_unico_propiedad = 'LG835530090'
    """)
    columns = [desc[0] for desc in cursor.description]
    row = cursor.fetchone()
    if row:
        print("\n✅ Propiedad encontrada en tabla 'properties':")
        for i, col in enumerate(columns):
            print(f"  {col}: {row[i]}")
    else:
        print("\n❌ NO se encontró en 'properties'")
        
        # Buscar con LIKE
        cursor.execute("""
            SELECT p.id, p.titulo, p.codigo_unico_propiedad, p.direccion 
            FROM properties p 
            WHERE p.codigo_unico_propiedad LIKE '%LG8355%'
        """)
        rows = cursor.fetchall()
        if rows:
            print(f"\n✅ Encontrado con LIKE: {rows}")
        else:
            # Buscar por dirección
            cursor.execute("""
                SELECT p.id, p.titulo, p.codigo_unico_propiedad, p.direccion 
                FROM properties p 
                WHERE p.direccion LIKE '%Emperatriz%'
            """)
            rows = cursor.fetchall()
            if rows:
                print(f"\n✅ Encontrado por dirección: {rows}")
            else:
                print("\n❌ No se encontró ninguna propiedad con esos criterios")

print("\n" + "=" * 80)
print("2. ANALIZANDO CAMPOS DE PUBLICIDAD EN TABLA 'properties'")
print("=" * 80)

# Obtener todas las columnas de properties
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, CHARACTER_MAXIMUM_LENGTH
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = 'properties'
        ORDER BY ORDINAL_POSITION
    """)
    all_columns = cursor.fetchall()
    
    print(f"\nTodas las columnas de 'properties' ({len(all_columns)} total):")
    advertising_keywords = ['publicidad', 'advertising', 'anuncio', 'descripcion', 'caracteristica', 
                           'feature', 'amenitie', 'comodidad', 'servicio', 'detalle', 'observacion',
                           'nota', 'comentario', 'info_adicional', 'informacion_adicional',
                           'coworking', 'terraza', 'alcabala', 'beneficio', 'incluye']
    
    for col in all_columns:
        col_name = col[0].lower()
        is_advertising = any(kw in col_name for kw in advertising_keywords)
        marker = " 📢 PUBLICIDAD" if is_advertising else ""
        print(f"  - {col[0]:40s} ({col[1]:15s}){marker}")

print("\n" + "=" * 80)
print("3. BUSCANDO EN OTRAS TABLAS POSIBLES CAMPOS DE PUBLICIDAD")
print("=" * 80)

# Buscar tablas relacionadas con propiedades que tengan campos de publicidad
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT TABLE_NAME 
        FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_TYPE = 'BASE TABLE'
          AND TABLE_NAME LIKE '%prop%'
        ORDER BY TABLE_NAME
    """)
    prop_tables = cursor.fetchall()
    
    for tbl in prop_tables:
        tbl_name = tbl[0]
        cursor.execute("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = %s
              AND (LOWER(COLUMN_NAME) LIKE '%publicidad%'
                OR LOWER(COLUMN_NAME) LIKE '%anuncio%'
                OR LOWER(COLUMN_NAME) LIKE '%descripcion%'
                OR LOWER(COLUMN_NAME) LIKE '%caracteristica%'
                OR LOWER(COLUMN_NAME) LIKE '%amenitie%'
                OR LOWER(COLUMN_NAME) LIKE '%comodidad%'
                OR LOWER(COLUMN_NAME) LIKE '%servicio%'
                OR LOWER(COLUMN_NAME) LIKE '%detalle%'
                OR LOWER(COLUMN_NAME) LIKE '%observacion%'
                OR LOWER(COLUMN_NAME) LIKE '%nota%'
                OR LOWER(COLUMN_NAME) LIKE '%incluye%'
                OR LOWER(COLUMN_NAME) LIKE '%beneficio%'
                OR LOWER(COLUMN_NAME) LIKE '%coworking%'
                OR LOWER(COLUMN_NAME) LIKE '%terraza%'
                OR LOWER(COLUMN_NAME) LIKE '%alcabala%')
        """, [tbl_name])
        adv_cols = cursor.fetchall()
        if adv_cols:
            print(f"\n📢 Tabla '{tbl_name}' tiene campos de publicidad:")
            for ac in adv_cols:
                print(f"  - {ac[0]}")

print("\n" + "=" * 80)
print("4. VERIFICANDO QUÉ CAMPOS USA LA COLECCIÓN RAG")
print("=" * 80)

from intelligence.models import IntelligenceCollection

collections = IntelligenceCollection.objects.filter(is_active=True)
for col in collections:
    print(f"\n📚 Colección: {col.name}")
    print(f"  Tabla origen: {col.source_sql}")
    print(f"  Campos de embedding: {col.embedding_fields}")
    print(f"  Campos de display: {col.display_fields}")
    print(f"  Field definitions: {col.field_definitions}")
    print(f"  Documentos: {col.documents.count()}")

print("\n" + "=" * 80)
print("5. VERIFICANDO CONTENIDO DE DOCUMENTOS RAG PARA PROPIEDADES")
print("=" * 80)

from intelligence.models import IntelligenceDocument

# Buscar documentos que contengan información de la propiedad
docs = IntelligenceDocument.objects.filter(
    collection__name='propiedades_propify'
)[:5]

for doc in docs:
    print(f"\nDocumento ID: {doc.id}")
    print(f"  Source ID: {doc.source_id}")
    print(f"  Field values: {doc.field_values}")
    print(f"  Content (primeros 500 chars): {doc.content[:500] if doc.content else 'VACÍO'}")
    print(f"  Content hash: {doc.content_hash}")

print("\n" + "=" * 80)
print("6. VERIFICANDO SI HAY CAMPOS 'publicidad' EN LA BD")
print("=" * 80)

with connection.cursor() as cursor:
    cursor.execute("""
        SELECT TABLE_NAME, COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE LOWER(COLUMN_NAME) LIKE '%publicidad%'
           OR LOWER(COLUMN_NAME) LIKE '%anuncio%'
           OR LOWER(COLUMN_NAME) LIKE '%advertising%'
        ORDER BY TABLE_NAME, COLUMN_NAME
    """)
    rows = cursor.fetchall()
    if rows:
        print("\nCampos de publicidad encontrados:")
        for r in rows:
            print(f"  {r[0]}.{r[1]}")
    else:
        print("\nNo hay campos con nombre 'publicidad' en ninguna tabla")

print("\n✅ Diagnóstico completado")
