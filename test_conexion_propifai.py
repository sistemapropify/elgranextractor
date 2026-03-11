#!/usr/bin/env python
"""
Test mínimo de conexión a Propifai.
"""
import os
import sys
import django

sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

print("=== TEST DE CONEXIÓN A PROPIFFY ===\n")

try:
    from propifai.models import PropifaiProperty
    
    print("1. Probando conexión directa con using('propifai'):")
    try:
        count = PropifaiProperty.objects.using('propifai').count()
        print(f"   ✓ Count usando using('propifai'): {count}")
    except Exception as e:
        print(f"   ✗ Error con using('propifai'): {e}")
    
    print("\n2. Probando conexión sin using (depende del router):")
    try:
        count2 = PropifaiProperty.objects.count()
        print(f"   ✓ Count sin using: {count2}")
    except Exception as e:
        print(f"   ✗ Error sin using: {e}")
        
    print("\n3. Probando router:")
    from webapp.routers import PropifaiRouter
    router = PropifaiRouter()
    db_read = router.db_for_read(PropifaiProperty)
    db_write = router.db_for_write(PropifaiProperty)
    print(f"   Router db_for_read: {db_read}")
    print(f"   Router db_for_write: {db_write}")
    
    print("\n4. Probando obtener algunas propiedades:")
    try:
        props = PropifaiProperty.objects.using('propifai').all()[:3]
        for i, prop in enumerate(props):
            print(f"   Propiedad {i+1}: ID={prop.id}, Code={prop.code}, Dept={prop.department}")
    except Exception as e:
        print(f"   ✗ Error al obtener propiedades: {e}")
        
except Exception as e:
    print(f"ERROR general: {e}")
    import traceback
    traceback.print_exc()

print("\n=== FIN DEL TEST ===")