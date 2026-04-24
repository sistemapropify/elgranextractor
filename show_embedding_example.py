import os
import sys
import django

sys.path.insert(0, 'webapp')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from intelligence.models import IntelligenceCollection, IntelligenceDocument

print("=== EJEMPLO DE PROPIEDAD CON EMBEDDING ===")
print("\n1. Información de la colección 'propiedades_propify':")
c = IntelligenceCollection.objects.get(name='propiedades_propify')
print(f"   - Nombre: {c.name}")
print(f"   - Tabla origen: {c.table_name}")
print(f"   - Documentos: {c.documents.count()}")
print(f"   - Última sincronización: {c.last_sync_at}")

print("\n2. Documento específico (ID original: 101):")
try:
    doc = IntelligenceDocument.objects.get(collection=c, source_id='101')
    print(f"   - ID del documento: {doc.id}")
    print(f"   - ID original: {doc.source_id}")
    print(f"   - ¿Tiene embedding?: {'SÍ' if doc.embedding else 'NO'}")
    
    if doc.embedding:
        # Mostrar información sobre el embedding
        embedding_data = doc.embedding
        print(f"   - Tamaño del embedding: {len(embedding_data) if embedding_data else 0} bytes")
        print(f"   - Tipo de dato: {type(embedding_data)}")
        
        # Intentar interpretar como vector (384 dimensiones, float32)
        import struct
        try:
            # Asumiendo que es un array de floats de 32 bits
            num_floats = len(embedding_data) // 4
            print(f"   - Dimensiones estimadas: {num_floats} (esperado: 384)")
            
            # Mostrar primeros 5 valores
            if num_floats >= 5:
                floats = struct.unpack(f'{num_floats}f', embedding_data)
                print(f"   - Primeros 5 valores del vector: {floats[:5]}")
        except:
            print(f"   - No se pudo interpretar como vector de floats")
    
    print("\n3. Campos de la propiedad:")
    if doc.field_values:
        print(f"   - Título: {doc.field_values.get('title', 'N/A')}")
        print(f"   - Descripción: {doc.field_values.get('description', 'N/A')[:100]}...")
        print(f"   - Precio: {doc.field_values.get('price', 'N/A')}")
        print(f"   - Dirección: {doc.field_values.get('exact_address', 'N/A')}")
        print(f"   - Coordenadas: {doc.field_values.get('coordinates', 'N/A')}")
        print(f"   - Distrito: {doc.field_values.get('district', 'N/A')}")
    
    print("\n4. Contenido usado para embedding:")
    print(f"   {doc.content[:200]}...")
    
    print("\n5. Hash del contenido:")
    print(f"   {doc.content_hash}")
    
except IntelligenceDocument.DoesNotExist:
    print("   Documento con ID 101 no encontrado")
    # Mostrar otro documento
    doc = c.documents.first()
    if doc:
        print(f"\n   Mostrando primer documento disponible (ID: {doc.source_id}):")
        print(f"   - Título: {doc.field_values.get('title', 'N/A') if doc.field_values else 'N/A'}")
        print(f"   - ¿Tiene embedding?: {'SÍ' if doc.embedding else 'NO'}")

print("\n=== RESUMEN ===")
print("Los embeddings están almacenados en el campo 'embedding' de la tabla 'intelligence_documents'.")
print("Cada documento vectorizado tiene:")
print("1. Un ID único en la colección")
print("2. Los valores originales de los campos en 'field_values'")
print("3. El contenido concatenado para embedding en 'content'")
print("4. El vector embedding en binario en 'embedding'")
print("5. Un hash del contenido para detectar cambios")

print("\nPara verificar que el sistema RAG funciona, puedes:")
print("1. Ir a http://127.0.0.1:8000/api/v1/intelligence/chat-web/")
print("2. Usar el chat para preguntar sobre propiedades")
print("3. Verificar que el sistema encuentra propiedades relevantes")