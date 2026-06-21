"""
Script para verificar el progreso del reprocesamiento.
"""
import os, sys, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from requerimientos.models import Requerimiento

total = Requerimiento.objects.filter(fuente__icontains='RED INMOBILIARIA').count()
print(f'Total requerimientos de RED INMOBILIARIA: {total}')
print()
print('--- Últimos 20 requerimientos creados ---')
ultimos = Requerimiento.objects.filter(fuente__icontains='RED INMOBILIARIA').order_by('-id')[:20]
for r in ultimos:
    agente = r.agente or '(vacio)'
    telefono = r.agente_telefono or '(vacio)'
    print(f'ID={r.id:>5} | agente={agente:30s} | tel={telefono:15s} | fecha={r.fecha}')
print()
print('--- Estadísticas de agente ---')
todos = Requerimiento.objects.filter(fuente__icontains='RED INMOBILIARIA')
con_nombre = 0
con_telefono_en_agente = 0
vacio = 0
for r in todos:
    if not r.agente:
        vacio += 1
    elif r.agente.startswith('+') or r.agente.replace(' ', '').isdigit():
        con_telefono_en_agente += 1
    else:
        con_nombre += 1
print(f'Con nombre real: {con_nombre}')
print(f'Con telefono en campo agente: {con_telefono_en_agente}')
print(f'Vacio: {vacio}')
