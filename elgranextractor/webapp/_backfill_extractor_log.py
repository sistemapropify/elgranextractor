"""
Backfill: vincula Requerimientos existentes a sus ExtractorLog correspondientes.
"""
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, os.path.dirname(__file__))

import django
django.setup()

from django.db.models import Q
from whatsapp_extractor.models import ExtractorLog
from requerimientos.models import Requerimiento

# Log #6: 2346 mensajes válidos
log = ExtractorLog.objects.get(id=6)
print(f"Log #6: ejecutado en {log.ejecucion_fecha}, {log.mensajes_validos} válidos")

# Buscar requerimientos con fuente='WhatsApp Export' SIN extractor_log
# Ordenados por creado_en descendente, limitados a mensajes_validos
reqs = Requerimiento.objects.filter(
    fuente='WhatsApp Export',
    extractor_log__isnull=True,
    creado_en__gte=log.ejecucion_fecha,
).order_by('-creado_en')[:log.mensajes_validos]

print(f"Encontrados {reqs.count()} requerimientos para vincular")

# Vincularlos
actualizados = 0
for req in reqs:
    req.extractor_log = log
    req.save(update_fields=['extractor_log'])
    actualizados += 1

print(f"Vinculados {actualizados} requerimientos al Log #6")

# Verificar
count = Requerimiento.objects.filter(extractor_log=log).count()
print(f"Total requerimientos vinculados al Log #6: {count}")
print(f"Total requerimientos WhatsApp sin vincular: {Requerimiento.objects.filter(extractor_log__isnull=True, fuente='WhatsApp Export').count()}")
