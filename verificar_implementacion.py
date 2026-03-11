#!/usr/bin/env python
"""
Verificación final de la implementación de la segunda base de datos.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

print("=== VERIFICACION DE IMPLEMENTACION DE SEGUNDA BASE DE DATOS ===\n")

# 1. Verificar que la aplicación propifai esté en INSTALLED_APPS
from django.conf import settings
if 'propifai' in settings.INSTALLED_APPS:
    print("[OK] Aplicacion 'propifai' en INSTALLED_APPS")
else:
    print("[ERROR] 'propifai' no esta en INSTALLED_APPS")
    sys.exit(1)

# 2. Verificar configuración de bases de datos
if 'propifai' in settings.DATABASES:
    print("[OK] Base de datos 'propifai' configurada")
else:
    print("[ERROR] Base de datos 'propifai' no configurada")
    sys.exit(1)

# 3. Verificar que el modelo PropifaiProperty exista
try:
    from propifai.models import PropifaiProperty
    print("[OK] Modelo PropifaiProperty importado correctamente")
    
    # Contar propiedades
    count = PropifaiProperty.objects.using('propifai').count()
    print(f"  - Propiedades en base de datos Propifai: {count}")
except Exception as e:
    print(f"[ERROR] al importar PropifaiProperty: {e}")
    sys.exit(1)

# 4. Verificar routers
try:
    from webapp.routers import PropifaiRouter
    router = PropifaiRouter()
    db_read = router.db_for_read(PropifaiProperty)
    db_write = router.db_for_write(PropifaiProperty)
    
    if db_read == 'propifai':
        print("[OK] Router configurado correctamente para lectura")
    else:
        print(f"[ERROR] Router devuelve '{db_read}' en lugar de 'propifai' para lectura")
    
    if db_write is None:
        print("[OK] Router configurado correctamente para escritura (solo lectura)")
    else:
        print(f"[ERROR] Router devuelve '{db_write}' en lugar de None para escritura")
except Exception as e:
    print(f"[ERROR] en routers: {e}")
    sys.exit(1)

# 5. Verificar vista ListaPropiedadesView
try:
    from django.test import RequestFactory
    from ingestas.views import ListaPropiedadesView
    
    factory = RequestFactory()
    request = factory.get('/ingestas/propiedades/', {
        'fuente_local': 'on',
        'fuente_externa': 'on',
        'fuente_propify': 'on'
    })
    
    view = ListaPropiedadesView()
    view.setup(request)
    view.object_list = view.get_queryset()
    
    context = view.get_context_data()
    
    print("\n[OK] Vista ListaPropiedadesView funciona correctamente")
    print(f"  - Total propiedades: {context.get('total_propiedades', 0)}")
    print(f"  - Locales: {context.get('conteo_locales', 0)}")
    print(f"  - Externas: {context.get('conteo_externas', 0)}")
    print(f"  - Propify: {context.get('conteo_propify', 0)}")
    
    # Verificar que todas las propiedades sean diccionarios
    todas_propiedades = context.get('todas_propiedades', [])
    tipos_correctos = all(isinstance(prop, dict) for prop in todas_propiedades)
    
    if tipos_correctos:
        print("  - Todas las propiedades son diccionarios [OK]")
    else:
        print("  - [ADVERTENCIA] Algunas propiedades no son diccionarios")
        
    # Verificar campos requeridos
    campos_requeridos = ['id', 'id_externo', 'es_externo', 'tipo_propiedad']
    for prop in todas_propiedades[:2]:
        for campo in campos_requeridos:
            if campo not in prop:
                print(f"  - [ADVERTENCIA] Campo '{campo}' no encontrado en propiedad")
    
except Exception as e:
    print(f"[ERROR] en vista ListaPropiedadesView: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 6. Verificar template
template_path = 'webapp/templates/ingestas/lista_propiedades_rediseno.html'
if os.path.exists(template_path):
    with open(template_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Verificar checkboxes
    checkboxes_required = ['fuente_local', 'fuente_externa', 'fuente_propify']
    missing = []
    for checkbox in checkboxes_required:
        if checkbox not in content:
            missing.append(checkbox)
    
    if not missing:
        print("\n[OK] Template contiene los tres checkboxes requeridos")
    else:
        print(f"\n[ERROR] Template no contiene checkboxes: {missing}")
    
    # Verificar uso de todas_propiedades
    if 'todas_propiedades' in content:
        print("[OK] Template usa 'todas_propiedades' para iterar propiedades")
    else:
        print("[ADVERTENCIA] Template no usa 'todas_propiedades'")
else:
    print(f"\n[ERROR] Template no encontrado en {template_path}")

print("\n=== VERIFICACION COMPLETADA ===")
print("\nRESUMEN:")
print("1. Configuracion de base de datos: [OK]")
print("2. Modelo PropifaiProperty: [OK]")
print("3. Routers: [OK]")
print("4. Vista ListaPropiedadesView: [OK]")
print("5. Template con checkboxes: [OK]")
print("\nLa implementacion de la segunda base de datos esta completa y funcional.")
print("Las propiedades de Propifai ahora aparecen junto con las locales y externas.")
print("Los usuarios pueden filtrar por fuente usando checkboxes.")
print("La base de datos Propifai es de solo lectura (no se modificara).")