#!/usr/bin/env python3
"""
Test directo de la base de datos Propifai
"""
import os
import sys
import django

# Configurar Django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

try:
    django.setup()
except Exception as e:
    print(f"Error configurando Django: {e}")
    sys.exit(1)

print("=== TEST DIRECTO BASE DE DATOS PROPIY ===")

# 1. Verificar conexión
try:
    from django.db import connections
    conn = connections['propifai']
    conn.ensure_connection()
    print("OK - Conexión a base de datos 'propifai' establecida")
except Exception as e:
    print(f"ERROR - No se puede conectar a BD 'propifai': {e}")
    import traceback
    traceback.print_exc()

# 2. Verificar modelo
try:
    from propifai.models import PropifaiProperty
    print("OK - Modelo PropifaiProperty importado")
    
    # 3. Contar propiedades
    count = PropifaiProperty.objects.count()
    print(f"OK - Total propiedades en tabla: {count}")
    
    # 4. Obtener algunas propiedades
    if count > 0:
        props = PropifaiProperty.objects.all()[:5]
        for i, prop in enumerate(props):
            print(f"  Propiedad {i+1}: ID={prop.id}, code={prop.code}, lat={prop.latitude}, lng={prop.longitude}")
    else:
        print("ADVERTENCIA - La tabla está vacía")
        
except Exception as e:
    print(f"ERROR - Problema con el modelo: {e}")
    import traceback
    traceback.print_exc()

# 5. Verificar routers
print("\n=== VERIFICACIÓN DE ROUTERS ===")
try:
    from webapp.routers import PropifaiRouter
    router = PropifaiRouter()
    
    # Verificar que el modelo use la BD correcta
    from propifai.models import PropifaiProperty
    db_for_read = router.db_for_read(PropifaiProperty)
    print(f"Router dice que PropifaiProperty usa BD: {db_for_read}")
    
except Exception as e:
    print(f"ERROR con routers: {e}")

print("\n=== TEST COMPLETADO ===")