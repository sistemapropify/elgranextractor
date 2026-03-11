#!/usr/bin/env python
import os
import sys
import django

# Configurar Django
sys.path.append('webapp')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from django.test import Client
from propifai.models import PropifaiProperty

def test_vista_propify():
    print("=== Probando vista independiente de Propify ===")
    
    # Verificar que hay propiedades en la base de datos
    count = PropifaiProperty.objects.count()
    print(f"Propiedades en base de datos Propify: {count}")
    
    # Probar la vista con el cliente de prueba
    client = Client()
    
    # Probar la URL principal
    print("\n1. Probando URL: /propifai/propiedades/")
    response = client.get('/propifai/propiedades/')
    print(f"   Status: {response.status_code}")
    print(f"   Template usado: {response.templates[0].name if response.templates else 'N/A'}")
    
    if response.status_code == 200:
        # Verificar contenido
        content = response.content.decode('utf-8')
        
        # Buscar indicadores
        if 'Propiedades Propify' in content:
            print("   ✓ Título 'Propiedades Propify' encontrado")
        else:
            print("   ✗ Título 'Propiedades Propify' NO encontrado")
            
        if 'propify-badge' in content.lower() or 'PROPIFY' in content:
            print("   ✓ Elementos Propify encontrados")
        else:
            print("   ✗ Elementos Propify NO encontrados")
            
        # Contar tarjetas de propiedades
        card_count = content.count('property-card')
        print(f"   Tarjetas de propiedades encontradas: {card_count}")
        
        # Guardar muestra del HTML
        with open('test_propify_output.html', 'w', encoding='utf-8') as f:
            f.write(content[:5000])
        print("   Muestra de HTML guardada en test_propify_output.html")
    else:
        print(f"   ERROR: Status {response.status_code}")
        
    # Probar la vista simple
    print("\n2. Probando URL: /propifai/propiedades-simple/")
    response = client.get('/propifai/propiedades-simple/')
    print(f"   Status: {response.status_code}")
    
    if response.status_code == 200:
        content = response.content.decode('utf-8')
        if 'Propiedades Propify' in content:
            print("   ✓ Vista simple funciona")
        else:
            print("   ✗ Vista simple no muestra título esperado")
    
    print("\n=== Resumen ===")
    if count > 0:
        print(f"✓ Base de datos tiene {count} propiedades Propify")
    else:
        print("✗ Base de datos NO tiene propiedades Propify")
        
    print("\nURLs disponibles:")
    print("  - http://127.0.0.1:8000/propifai/propiedades/")
    print("  - http://127.0.0.1:8000/propifai/propiedades-simple/")

if __name__ == "__main__":
    test_vista_propify()