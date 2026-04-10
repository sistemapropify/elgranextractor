#!/usr/bin/env python
"""
Prueba de conexión a la base de datos propifai para eventos.
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
    # Intentar contar eventos usando el router
    count = Event.objects.using('propifai').count()
    print(f"✓ Eventos encontrados: {count}")
except Exception as e:
    print(f"✗ Error al contar eventos: {e}")
    print("Detalle:", str(e))

try:
    # Intentar contar tipos de eventos
    type_count = EventType.objects.using('propifai').count()
    print(f"✓ Tipos de eventos encontrados: {type_count}")
except Exception as e:
    print(f"✗ Error al contar tipos: {e}")

# Probar una consulta simple
try:
    eventos = Event.objects.using('propifai').all()[:5]
    print(f"✓ Primeros {len(eventos)} eventos:")
    for e in eventos:
        print(f"  - {e.id}: {e.titulo} ({e.fecha_evento})")
except Exception as e:
    print(f"✗ Error en consulta: {e}")

print("\n=== Prueba completada ===")