#!/usr/bin/env python
"""Verificar datos de fechas para el calendario."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
import django
django.setup()
from requerimientos.models import Requerimiento
from django.db.models import Count
from django.db.models.functions import ExtractYear, ExtractMonth

total = Requerimiento.objects.count()
con_fecha = Requerimiento.objects.filter(fecha__isnull=False).count()
sin_fecha = Requerimiento.objects.filter(fecha__isnull=True).count()
print(f"Total: {total}, Con fecha: {con_fecha}, Sin fecha: {sin_fecha}")

if con_fecha > 0:
    first = Requerimiento.objects.filter(fecha__isnull=False).earliest('fecha')
    last = Requerimiento.objects.filter(fecha__isnull=False).latest('fecha')
    print(f"Rango: {first.fecha} - {last.fecha}")

    meses = Requerimiento.objects.filter(fecha__isnull=False).annotate(
        anio=ExtractYear('fecha'), mes=ExtractMonth('fecha')
    ).values('anio', 'mes').annotate(total=Count('id')).order_by('-anio', '-mes')[:12]
    print("Últimos 12 meses:")
    for m in meses:
        print(f"  {m['anio']}-{m['mes']:02d}: {m['total']} requerimientos")

# Ver cuántos requerimientos tienen hora
con_hora = Requerimiento.objects.filter(hora__isnull=False).count()
print(f"Con hora: {con_hora}")
