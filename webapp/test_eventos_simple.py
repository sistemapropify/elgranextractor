#!/usr/bin/env python
"""
Prueba simple de conexión a eventos.
"""
import os
import sys
import django

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from eventos.models import Event, EventType

print("=== Prueba de conexión a eventos ===")

try:
    count = Event.objects.using('propifai').count()
    print(f"OK - Eventos encontrados: {count}")
except Exception as e:
    print(f"ERROR - Error al contar eventos: {e}")
    import traceback
    traceback.print_exc()

print("=== Prueba completada ===")