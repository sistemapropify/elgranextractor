#!/usr/bin/env python3
"""
Diagnóstico simple de la API del dashboard.
"""
import sys
import os
import django

# Configurar Django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

try:
    django.setup()
except Exception as e:
    print(f"Error configurando Django: {e}")
    sys.exit(1)

from django.test import RequestFactory
from requerimientos.views import ApiAnalisisTemporalView

# Crear una solicitud simulada
factory = RequestFactory()
request = factory.get('/requerimientos/api/analisis-temporal/', {'async': 'false'})

# Instanciar la vista
view = ApiAnalisisTemporalView()
view.request = request

try:
    response = view.get(request)
    print(f"Status: {response.status_code}")
    print(f"Content: {response.content.decode('utf-8')[:500]}")
except Exception as e:
    print(f"Error al ejecutar la vista: {e}")
    import traceback
    traceback.print_exc()