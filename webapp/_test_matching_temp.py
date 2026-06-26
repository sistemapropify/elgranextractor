# -*- coding: utf-8 -*-
"""Temporary script to test matching v3.0 - safe to delete after execution"""
import os
os.environ['DJANGO_LOG_LEVEL'] = 'CRITICAL'
os.environ['DJANGO_LOG_HANDLERS'] = '[]'

import django
from django.conf import settings

# Override logging config before Django fully boots
import logging
logging.disable(logging.CRITICAL)

# Now setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
import django
django.setup()

# Disable all loggers explicitly
for name in logging.root.manager.loggerDict:
    logger = logging.getLogger(name)
    logger.disabled = True
    logger.setLevel(logging.CRITICAL)
    logger.handlers = []
logging.getLogger().handlers = []

from matching.engine import ejecutar_matching_masivo
from matching.models import MatchResult
from django.db.models import Count, Avg, Max, Min

# 1. Ejecutar matching masivo
print('=== EJECUTANDO MATCHING MASIVO ===')
stats = ejecutar_matching_masivo()
print(stats)

# 2. Verificar resultados
print()
print('=== RESULTADOS ===')
total = MatchResult.objects.count()
print(f'Total MatchResult: {total}')

# 3. Verificar matches por propiedad
print()
print('Matches por propiedad (top 10):')
for r in MatchResult.objects.values('propiedad_id').annotate(total=Count('id')).order_by('-total')[:10]:
    print(f'  Prop {r["propiedad_id"]}: {r["total"]} matches')

# 4. Verificar scores promedio
print()
aggs = MatchResult.objects.aggregate(
    avg_score=Avg('score_total'),
    max_score=Max('score_total'),
    min_score=Min('score_total')
)
print(f'Score promedio: {aggs["avg_score"]:.2f}')
print(f'Score maximo:   {aggs["max_score"]:.2f}')
print(f'Score minimo:   {aggs["min_score"]:.2f}')
