"""
Re-sincronizar colección propiedades_propify para que field_values
contengan los valores FK resueltos (nombres reales en lugar de IDs numéricos).
"""
import sys, os, django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
django.setup()

from intelligence.services.rag import RAGService

print("=== RE-SINCRONIZANDO COLECCIÓN propiedades_propify ===")
print("Esto actualizará field_values con nombres FK resueltos (district_name, currency_name, etc.)")
print()

success, message, stats = RAGService.sync_collection_dynamic(
    collection_name='propiedades_propify',
    force_full_sync=True,
    database_alias='propifai'
)

print(f"Resultado: {'✅ ÉXITO' if success else '❌ ERROR'}")
print(f"Mensaje: {message}")
print(f"Estadísticas: {stats}")
print()

if success:
    # Verificar que los field_values ahora tienen nombres resueltos
    from intelligence.models import IntelligenceDocument, IntelligenceCollection
    collection = IntelligenceCollection.objects.get(name='propiedades_propify')
    docs = IntelligenceDocument.objects.filter(collection=collection)[:3]
    
    print("=== VERIFICACIÓN: Primeros 3 documentos ===")
    for doc in docs:
        fv = doc.field_values or {}
        print(f"\nDocumento source_id={doc.source_id}:")
        for key in ['title', 'price', 'currency_name', 'district_name', 
                    'urbanization_name', 'operation_type_name', 'condition_name',
                    'property_type_name']:
            if key in fv:
                print(f"  {key}: {fv[key]}")
        # Mostrar si hay valores FK resueltos
        resolved_keys = [k for k in fv.keys() if k.endswith('_name')]
        if resolved_keys:
            print(f"  ✅ Campos FK resueltos encontrados: {resolved_keys}")
        else:
            print(f"  ❌ NO hay campos FK resueltos (terminados en _name)")
