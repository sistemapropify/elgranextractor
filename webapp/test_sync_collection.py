#!/usr/bin/env python
"""
Script para probar la sincronización de la colección 'propiedades_propifai'.
"""
import os
import sys
import django
import requests
from django.test import Client

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from intelligence.models import IntelligenceCollection, IntelligenceDocument

def test_sync_via_api():
    """Probar sincronización mediante API (POST a la vista)."""
    print("=== Probando sincronización de colección ===")
    
    # Obtener la colección
    collection_id = 'b899d903-5a14-4b23-b567-6bf15aa5f5b9'
    try:
        collection = IntelligenceCollection.objects.get(id=collection_id)
        print(f"Colección: {collection.name}")
        print(f"ID: {collection.id}")
        print(f"SQL: {collection.source_sql[:100]}...")
        
        # Contar documentos actuales
        current_count = IntelligenceDocument.objects.filter(collection=collection).count()
        print(f"Documentos actuales en colección: {current_count}")
        
        # Usar Django test client para simular la solicitud
        client = Client()
        
        # Primero necesitamos iniciar sesión (simular usuario admin)
        from django.contrib.auth.models import User
        user = User.objects.filter(is_superuser=True).first()
        if not user:
            print("No hay usuario superuser, creando uno temporal...")
            user = User.objects.create_superuser('testadmin', 'test@example.com', 'testpass123')
        
        client.force_login(user)
        
        # URL de sincronización
        sync_url = f'/api/v1/intelligence/collections/{collection_id}/sync/'
        print(f"URL de sincronización: {sync_url}")
        
        # Hacer POST a la vista de sincronización
        print("Enviando solicitud POST para sincronizar...")
        response = client.post(sync_url, {'confirm': 'true'})
        
        print(f"Status code: {response.status_code}")
        print(f"Response: {response}")
        
        if response.status_code == 302:  # Redirect
            print(f"Redirect a: {response.url}")
            # Seguir el redirect
            redirect_response = client.get(response.url)
            print(f"Redirect status: {redirect_response.status_code}")
            
        # Contar documentos después de la sincronización
        new_count = IntelligenceDocument.objects.filter(collection=collection).count()
        print(f"Documentos después de sincronización: {new_count}")
        
        if new_count > current_count:
            print(f"✅ Sincronización exitosa: {new_count - current_count} nuevos documentos")
        else:
            print(f"⚠️  No se agregaron nuevos documentos")
            
        # Mostrar algunos documentos si existen
        if new_count > 0:
            sample_docs = IntelligenceDocument.objects.filter(collection=collection)[:3]
            for i, doc in enumerate(sample_docs):
                print(f"  Documento {i+1}: {doc.title[:50]}...")
                
    except IntelligenceCollection.DoesNotExist:
        print(f"Colección con ID {collection_id} no encontrada")
    except Exception as e:
        print(f"Error durante la prueba: {e}")
        import traceback
        traceback.print_exc()

def test_sql_direct():
    """Probar el SQL directamente en la base de datos."""
    print("\n=== Probando SQL directamente ===")
    
    from django.db import connection
    from propifai.models import PropifaiProperty
    
    # Contar propiedades activas
    active_count = PropifaiProperty.objects.filter(is_active=1).count()
    print(f"Propiedades activas en tabla 'properties': {active_count}")
    
    # Ejecutar el SQL de la colección
    collection = IntelligenceCollection.objects.get(id='b899d903-5a14-4b23-b567-6bf15aa5f5b9')
    sql = collection.source_sql.strip()
    
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql)
            rows = cursor.fetchall()
            print(f"SQL retorna {len(rows)} filas")
            
            if rows:
                print("Primera fila de ejemplo:")
                columns = [col[0] for col in cursor.description]
                print(f"  Columnas: {columns}")
                print(f"  Valores: {rows[0]}")
                
    except Exception as e:
        print(f"Error ejecutando SQL: {e}")

if __name__ == '__main__':
    test_sql_direct()
    print("\n" + "="*50 + "\n")
    test_sync_via_api()