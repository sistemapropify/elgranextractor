import os
import sys
import django
import json

# Configurar Django
sys.path.append('webapp')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from django.test import RequestFactory
from acm.views import buscar_comparables

rf = RequestFactory()
data = {'lat': -16.4090, 'lng': -71.5375, 'radio': 5000, 'tipo_propiedad': ''}
request = rf.post('/acm/buscar-comparables/', data=json.dumps(data), content_type='application/json')
response = buscar_comparables(request)
print('Status:', response.status_code)
print('Content:', response.content.decode())