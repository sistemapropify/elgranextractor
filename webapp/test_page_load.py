#!/usr/bin/env python
import os
import sys
import django
import re
import json

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from propifai.views import property_visits_dashboard
from django.test import RequestFactory

print("=== TEST PAGE LOAD WITH JAVASCRIPT ===")

factory = RequestFactory()
request = factory.get('/propifai/dashboard/visitas/')

try:
    response = property_visits_dashboard(request)
    content = response.content.decode('utf-8')
    
    # Buscar console.log statements en el JavaScript
    console_logs = re.findall(r'console\.(log|error|warn)\(([^)]+)\)', content)
    
    print(f"Encontrados {len(console_logs)} console.log statements")
    
    # Extraer el JSON de propertiesData
    json_match = re.search(r'const propertiesData = (\[.*?\]);', content, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
        print(f"\nJSON encontrado, longitud: {len(json_str)} caracteres")
        
        try:
            parsed = json.loads(json_str)
            print(f"JSON parseado correctamente, {len(parsed)} propiedades")
            
            # Contar propiedades con eventos
            props_with_events = sum(1 for p in parsed if p.get('total_eventos', 0) > 0)
            print(f"Propiedades con eventos: {props_with_events}")
            
            # Mostrar algunas propiedades con eventos
            props_with_events_list = [p for p in parsed if p.get('total_eventos', 0) > 0]
            if props_with_events_list:
                print(f"\nPrimera propiedad con eventos:")
                print(json.dumps(props_with_events_list[0], indent=2, ensure_ascii=False)[:300])
            else:
                print("\nNo hay propiedades con eventos")
                
        except json.JSONDecodeError as e:
            print(f"✗ Error al parsear JSON: {e}")
            print(f"Contexto del error: {json_str[max(0, e.pos-100):e.pos+100]}")
    
    # Buscar el tbody de la tabla
    tbody_match = re.search(r'<tbody[^>]*id="properties-tbody"[^>]*>(.*?)</tbody>', content, re.DOTALL)
    if tbody_match:
        tbody_content = tbody_match.group(1)
        # Contar filas <tr> en el tbody
        tr_count = tbody_content.count('<tr')
        print(f"\nFilas <tr> en tbody: {tr_count}")
        
        if tr_count == 0:
            print("⚠️ El tbody está vacío - JavaScript no está renderizando filas")
        else:
            print(f"✓ Tabla tiene {tr_count} filas (incluyendo header)")
            
            # Contar filas de datos (excluyendo posible header)
            data_rows = re.findall(r'<tr[^>]*data-property-id[^>]*>', tbody_content)
            print(f"Filas con data-property-id: {len(data_rows)}")
    else:
        print("\n✗ No se encontró el tbody con id='properties-tbody'")
        
    # Verificar si hay elementos de filtro
    filter_elements = [
        ('filter-status', 'select'),
        ('filter-type', 'select'), 
        ('filter-district', 'select'),
        ('filter-agent', 'select'),
        ('properties-tbody', 'tbody'),
        ('kpi-total-props', 'span'),
        ('rendered-count', 'span')
    ]
    
    print("\n=== VERIFICACIÓN DE ELEMENTOS DOM ===")
    for elem_id, elem_type in filter_elements:
        pattern = f'<{elem_type}[^>]*id="{elem_id}"'
        if re.search(pattern, content, re.IGNORECASE):
            print(f"+ {elem_id} ({elem_type}) encontrado")
        else:
            print(f"- {elem_id} ({elem_type}) NO encontrado")
            
except Exception as e:
    print(f"\nError: {e}")
    import traceback
    traceback.print_exc()