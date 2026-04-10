#!/usr/bin/env python
import os
import sys
import django

# Configurar Django
sys.path.append('d:/proyectos/prometeo')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from webapp.propifai.models import PropifaiProperty

# Contar total de propiedades
total = PropifaiProperty.objects.count()
print(f'Total propiedades en DB: {total}')

# Contar propiedades que no son borradores
disponibles = PropifaiProperty.objects.filter(is_draft=False).count()
print(f'Propiedades disponibles (no borradores): {disponibles}')

# Contar borradores
borradores = PropifaiProperty.objects.filter(is_draft=True).count()
print(f'Borradores: {borradores}')

# Verificar algunos campos
print('\nPrimeras 5 propiedades:')
for p in PropifaiProperty.objects.all()[:5]:
    print(f'  {p.id}: {p.code} - draft={p.is_draft}, status={p.availability_status}')