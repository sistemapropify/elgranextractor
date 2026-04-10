#!/usr/bin/env python3
"""
Test que llama a la función real usada en la vista.
"""

import os
import sys
import django
import json

# Configurar Django
sys.path.append('webapp')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from eventos.models import Event
from eventos.views import calcular_evolucion_semanal_tipos_eventos

# Obtener todos los eventos (como hace la vista)
eventos = Event.objects.all()
print(f"Total eventos: {eventos.count()}")

# Llamar a la función
datos = calcular_evolucion_semanal_tipos_eventos(eventos, semanas=8)

print("\n=== DATOS GENERADOS POR LA FUNCIÓN ===")
print(f"Semanas: {len(datos['semanas'])}")
print(f"Tipos: {len(datos['tipos'])}")
print(f"Colores: {len(datos['colores'])}")

print("\nColores asignados:")
for tipo_id, color in datos['colores'].items():
    tipo_nombre = datos['tipos'].get(tipo_id, 'Desconocido')
    print(f"  {tipo_nombre} (ID {tipo_id}): {color}")

print("\nVerificando unicidad de colores:")
colores = list(datos['colores'].values())
colores_unicos = set(colores)
print(f"  Colores totales: {len(colores)}")
print(f"  Colores únicos: {len(colores_unicos)}")
if len(colores) != len(colores_unicos):
    print("  ¡ADVERTENCIA: Hay colores duplicados!")
    # Encontrar duplicados
    from collections import Counter
    conteo = Counter(colores)
    for color, count in conteo.items():
        if count > 1:
            print(f"    Color {color} aparece {count} veces")

# Verificar si coincide con lo que vimos en el HTML
print("\n=== COMPARACIÓN CON HTML ===")
html_colores = {
    '5': '#047D7D',  # Capacitacion
    '2': '#047D7D',  # Captación
    '3': '#047D7D',  # Cierre
    '6': '#51A7F0',  # Otro
    '4': '#047D7D',  # Tramite
    '1': '#047D7D',  # Visita
}

print("Colores en HTML (del output anterior):")
for tipo_id, color in html_colores.items():
    tipo_nombre = datos['tipos'].get(tipo_id, 'Desconocido')
    print(f"  {tipo_nombre} (ID {tipo_id}): {color}")

print("\n¿Coinciden?")
coinciden = True
for tipo_id in datos['colores']:
    color_funcion = datos['colores'][tipo_id]
    color_html = html_colores.get(tipo_id)
    if color_html and color_funcion != color_html:
        print(f"  NO: ID {tipo_id} - Función: {color_funcion}, HTML: {color_html}")
        coinciden = False

if coinciden:
    print("  Sí, todos los colores coinciden.")
else:
    print("  No, hay diferencias.")