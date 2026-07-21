"""Test api_lead_matrix directly"""
import django, os, json, sys
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
django.setup()

from django.test import RequestFactory
from canvas.views import api_lead_matrix

rf = RequestFactory()
req = rf.get('/canvas/api/lead-matrix/')

class MockUser:
    is_authenticated = True

req.current_user = MockUser()

resp = api_lead_matrix(req)
data = json.loads(resp.content)

with open('d:\\test_output.txt', 'w') as f:
    f.write(f"Total properties: {len(data.get('properties',[]))}\n")
    f.write(f"Total leads: {data.get('total_leads',0)}\n\n")
    for p in data.get('properties', [])[:5]:
        f.write(f"  property_id={p['property_id']} title={repr(p.get('title',''))[:80]}\n")

print("DONE - check d:\\test_output.txt")
