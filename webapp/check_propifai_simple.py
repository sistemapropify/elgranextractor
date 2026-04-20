#!/usr/bin/env python
"""
Script simple para verificar la tabla de PropifaiProperty.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from propifai.models import PropifaiProperty
from intelligence.models import IntelligenceCollection

def main():
    print("=== Información de PropifaiProperty ===")
    
    # 1. Tabla del modelo
    print(f"1. Tabla del modelo: {PropifaiProperty._meta.db_table}")
    
    # 2. Campos del modelo
    print("\n2. Campos principales del modelo:")
    field_names = [f.name for f in PropifaiProperty._meta.fields]
    print(f"   {', '.join(field_names[:10])}...")
    
    # 3. Contar registros
    try:
        count = PropifaiProperty.objects.count()
        print(f"\n3. Total de propiedades: {count}")
        
        if count > 0:
            sample = PropifaiProperty.objects.first()
            print(f"   Ejemplo - ID: {sample.id}")
            print(f"   Título: {sample.titulo}")
            print(f"   Tipo: {sample.tipo_propiedad}")
            print(f"   Precio: {sample.precio}")
            print(f"   Distrito: {sample.distrito}")
    except Exception as e:
        print(f"\n3. Error al contar: {e}")
    
    # 4. Verificar colección "propiedades_propifai"
    print("\n=== Colección 'propiedades_propifai' ===")
    try:
        collection = IntelligenceCollection.objects.get(name='propiedades_propifai')
        print(f"ID: {collection.id}")
        print(f"SQL actual:")
        print(collection.source_sql[:200] + "..." if len(collection.source_sql) > 200 else collection.source_sql)
        
        # Verificar si el SQL hace referencia a tabla incorrecta
        if 'propifai_propiedad' in collection.source_sql:
            print("\n⚠️  PROBLEMA: SQL hace referencia a 'propifai_propiedad'")
            print(f"   Pero la tabla real es: {PropifaiProperty._meta.db_table}")
            
            # Proponer SQL corregido
            corrected_sql = collection.source_sql.replace('propifai_propiedad', PropifaiProperty._meta.db_table)
            print("\n   SQL corregido propuesto:")
            print(corrected_sql[:200] + "..." if len(corrected_sql) > 200 else corrected_sql)
            
            # También verificar campos
            print("\n   Campos en el SQL vs campos reales:")
            sql_fields = ['id', 'titulo', 'descripcion', 'direccion', 'distrito', 'tipo_propiedad', 
                         'precio', 'moneda', 'area_construida', 'area_total', 'habitaciones', 
                         'banos', 'estacionamientos', 'condicion', 'fecha_creacion', 'es_propify']
            
            for field in sql_fields:
                if hasattr(PropifaiProperty, field):
                    print(f"     ✓ {field} existe en el modelo")
                else:
                    print(f"     ✗ {field} NO existe en el modelo")
                    
    except IntelligenceCollection.DoesNotExist:
        print("Colección 'propiedades_propifai' no encontrada")
    except Exception as e:
        print(f"Error al obtener colección: {e}")

if __name__ == '__main__':
    main()