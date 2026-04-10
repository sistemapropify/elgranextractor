#!/usr/bin/env python
"""
Script para probar que la vista de eventos se puede importar sin errores.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

try:
    django.setup()
    print("OK: Django configurado correctamente")
    
    # Intentar importar la vista
    from eventos import views
    print("OK: Modulo eventos.views importado correctamente")
    
    # Verificar que las funciones existan
    if hasattr(views, 'dashboard_eventos'):
        print("OK: Funcion dashboard_eventos encontrada")
    else:
        print("ERROR: Funcion dashboard_eventos NO encontrada")
        
    if hasattr(views, 'detalle_evento'):
        print("OK: Funcion detalle_evento encontrada")
    else:
        print("ERROR: Funcion detalle_evento NO encontrada")
        
    if hasattr(views, 'api_eventos'):
        print("OK: Funcion api_eventos encontrada")
    else:
        print("ERROR: Funcion api_eventos NO encontrada")
    
    # Verificar importaciones
    from propifai.models import PropifaiProperty
    print("OK: Modelo PropifaiProperty importado correctamente")
    
    from eventos.models import Event, EventType
    print("OK: Modelos Event y EventType importados correctamente")
    
    print("\n=== Todas las importaciones funcionan correctamente ===")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)