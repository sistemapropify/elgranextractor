#!/usr/bin/env python
import os
import sys
import django
import json

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from propifai.views import property_visits_dashboard
from django.test import RequestFactory

print("=== DEBUG JSON OUTPUT ===")

factory = RequestFactory()
request = factory.get('/propifai/dashboard/visitas/')

try:
    response = property_visits_dashboard(request)
    print(f"Response status: {response.status_code}")
    print(f"Response type: {type(response)}")
    
    # Para HttpResponse, necesitamos acceder al contenido
    content = response.content.decode('utf-8')
    print(f"\nContenido HTML (primeros 500 caracteres):")
    print(content[:500])
    
    # Buscar el JSON en el contenido
    import re
    json_match = re.search(r'const propertiesData = (\[.*?\]);', content, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
        print(f"\nJSON encontrado en HTML (primeros 500 caracteres):")
        print(json_str[:500])
        
        # Intentar parsear
        try:
            parsed = json.loads(json_str)
            print(f"\nJSON válido")
            print(f"Número de propiedades: {len(parsed)}")
            if parsed:
                print(f"\nPrimera propiedad:")
                # Usar ensure_ascii=False pero codificar para la consola de Windows
                prop_json = json.dumps(parsed[0], indent=2, ensure_ascii=False)
                try:
                    print(prop_json[:200])
                except UnicodeEncodeError:
                    print(prop_json.encode('ascii', 'replace').decode('ascii')[:200])
        except json.JSONDecodeError as e:
            print(f"\nError al parsear JSON: {e}")
            print(f"Error en posición {e.pos}")
            print(f"Contexto del error: {json_str[max(0, e.pos-50):e.pos+50]}")
    else:
        print("\n✗ No se encontró 'const propertiesData =' en el HTML")
        # Buscar cualquier JSON
        json_match2 = re.search(r'propertiesData = (\[.*?\]);', content, re.DOTALL)
        if json_match2:
            print("Pero se encontró 'propertiesData =' sin 'const'")
            json_str = json_match2.group(1)
            print(f"JSON (primeros 200 chars): {json_str[:200]}")
        
except Exception as e:
    print(f"\nError al ejecutar la vista: {e}")
    import traceback
    traceback.print_exc()