#!/usr/bin/env python
"""
Ejecutar la vista dashboard directamente para ver qué está pasando.
"""
import os
import sys
import django
from django.test import RequestFactory

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from analisis_crm.views import dashboard

# Crear una request falsa
factory = RequestFactory()
request = factory.get('/analisis-crm/')

print("=== EJECUTANDO VISTA DASHBOARD DIRECTAMENTE ===")

# Ejecutar la vista
try:
    response = dashboard(request)
    print(f"Response status code: {response.status_code}")
    print(f"Response content type: {response['Content-Type']}")
    
    # Verificar el contexto
    if hasattr(response, 'context_data'):
        context = response.context_data
        print(f"\n=== CONTEXTO DE LA VISTA ===")
        for key, value in context.items():
            if key in ['days_of_month_json', 'counts_per_day_json']:
                print(f"{key}: '{value}' (tipo: {type(value)}, longitud: {len(value) if hasattr(value, '__len__') else 'N/A'})")
            elif key in ['days_of_month', 'counts_per_day']:
                print(f"{key}: {value} (tipo: {type(value)}, longitud: {len(value)})")
            else:
                print(f"{key}: {type(value)}")
    
    # También podemos renderizar el template para ver el HTML
    print("\n=== RENDERIZANDO TEMPLATE ===")
    from django.template.loader import render_to_string
    html = render_to_string('analisis_crm/dashboard.html', response.context_data)
    
    # Buscar los elementos script
    import re
    days_match = re.search(r'<script id="days-data".*?>(.*?)</script>', html, re.DOTALL)
    if days_match:
        print(f"days-data en HTML: '{days_match.group(1).strip()}'")
    
    counts_match = re.search(r'<script id="counts-data".*?>(.*?)</script>', html, re.DOTALL)
    if counts_match:
        print(f"counts-data en HTML: '{counts_match.group(1).strip()}'")
        
except Exception as e:
    print(f"Error ejecutando vista: {e}")
    import traceback
    traceback.print_exc()