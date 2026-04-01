#!/usr/bin/env python
"""
Verificar qué datos se están enviando realmente en el HTML del dashboard
"""
import os
import sys
import django
from django.test import RequestFactory
from django.template import Template, Context

# Configurar Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from analisis_crm.views import dashboard

def verificar_contexto_vista():
    """Verificar el contexto que genera la vista"""
    print("=== VERIFICACIÓN DEL CONTEXTO DE LA VISTA ===")
    
    # Crear una request simulada
    factory = RequestFactory()
    request = factory.get('/analisis-crm/')
    
    # Llamar a la vista
    response = dashboard(request)
    
    # Obtener el contexto
    context = response.context_data
    
    print(f"Claves en el contexto: {list(context.keys())}")
    
    # Verificar datos específicos
    if 'days_of_month' in context:
        days = context['days_of_month']
        counts = context['counts_per_day']
        
        print(f"\nDatos en el contexto:")
        print(f"days_of_month (tipo: {type(days)}, longitud: {len(days)}):")
        for i, day in enumerate(days[:10]):  # Primeros 10
            print(f"  [{i}] {day}")
        
        print(f"\ncounts_per_day (tipo: {type(counts)}, longitud: {len(counts)}):")
        for i, count in enumerate(counts[:10]):  # Primeros 10
            print(f"  [{i}] {count}")
        
        # Buscar específicamente el 5 de marzo
        try:
            idx = days.index('05/03')
            print(f"\nÍndice de '05/03' en days_of_month: {idx}")
            print(f"Valor en counts_per_day[{idx}]: {counts[idx]}")
        except ValueError:
            print("ERROR: '05/03' no encontrado en days_of_month")
            print(f"Valores: {days}")
    
    # Verificar JSON
    if 'days_of_month_json' in context:
        days_json = context['days_of_month_json']
        counts_json = context['counts_per_day_json']
        
        print(f"\nJSON en el contexto:")
        print(f"days_of_month_json (primeros 100 chars): {days_json[:100]}...")
        print(f"counts_per_day_json (primeros 100 chars): {counts_json[:100]}...")
        
        # Parsear para verificar
        import json
        try:
            days_list = json.loads(days_json)
            counts_list = json.loads(counts_json)
            
            print(f"\nParseado del JSON:")
            print(f"days_list longitud: {len(days_list)}")
            print(f"counts_list longitud: {len(counts_list)}")
            
            # Buscar 5/3
            try:
                idx = days_list.index('05/03')
                print(f"Índice de '05/03' en JSON: {idx}")
                print(f"Valor en counts_list[{idx}]: {counts_list[idx]}")
            except ValueError:
                print("ERROR: '05/03' no encontrado en JSON days_list")
                
        except json.JSONDecodeError as e:
            print(f"ERROR parseando JSON: {e}")
    
    return context

def verificar_template_rendering():
    """Verificar cómo se renderiza el template"""
    print("\n=== VERIFICACIÓN DEL RENDERIZADO DEL TEMPLATE ===")
    
    # Obtener el contexto primero
    factory = RequestFactory()
    request = factory.get('/analisis-crm/')
    response = dashboard(request)
    context = response.context_data
    
    # Cargar el template
    from django.template.loader import get_template
    template = get_template('analisis_crm/dashboard.html')
    
    # Renderizar con el contexto
    html_content = template.render(context, request)
    
    # Buscar los elementos script con los datos
    import re
    
    # Buscar el script con id="days-data"
    days_pattern = r'<script id="days-data" type="application/json">(.*?)</script>'
    days_match = re.search(days_pattern, html_content, re.DOTALL)
    
    if days_match:
        days_json = days_match.group(1).strip()
        print(f"Encontrado script days-data:")
        print(f"Contenido (primeros 150 chars): {days_json[:150]}...")
        
        # Parsear
        import json
        try:
            days_list = json.loads(days_json)
            print(f"Parseado correctamente, longitud: {len(days_list)}")
            
            # Buscar 5/3
            try:
                idx = days_list.index('05/03')
                print(f"Índice de '05/03': {idx}")
            except ValueError:
                print("'05/03' no encontrado en days_list")
                print(f"Primeros valores: {days_list[:10]}")
                
        except json.JSONDecodeError as e:
            print(f"ERROR parseando days-data JSON: {e}")
            print(f"JSON crudo: {days_json}")
    else:
        print("ERROR: No se encontró el script days-data en el HTML")
    
    # Buscar el script con id="counts-data"
    counts_pattern = r'<script id="counts-data" type="application/json">(.*?)</script>'
    counts_match = re.search(counts_pattern, html_content, re.DOTALL)
    
    if counts_match:
        counts_json = counts_match.group(1).strip()
        print(f"\nEncontrado script counts-data:")
        print(f"Contenido (primeros 150 chars): {counts_json[:150]}...")
        
        # Parsear
        import json
        try:
            counts_list = json.loads(counts_json)
            print(f"Parseado correctamente, longitud: {len(counts_list)}")
            
            # Si encontramos days_list, buscar el valor correspondiente
            if 'days_list' in locals():
                try:
                    idx = days_list.index('05/03')
                    if idx < len(counts_list):
                        print(f"Valor para '05/03' (índice {idx}): {counts_list[idx]}")
                    else:
                        print(f"ERROR: Índice {idx} fuera de rango de counts_list (longitud: {len(counts_list)})")
                except ValueError:
                    pass
                    
        except json.JSONDecodeError as e:
            print(f"ERROR parseando counts-data JSON: {e}")
    else:
        print("ERROR: No se encontró el script counts-data en el HTML")
    
    # Buscar también datos hardcodeados de ejemplo (por si hay fallback)
    example_pattern = r"chartDays = \['01/03', '02/03', '03/03', '04/03', '05/03'\];"
    example_match = re.search(example_pattern, html_content)
    
    if example_match:
        print("\n¡ADVERTENCIA! Se encontraron datos de ejemplo hardcodeados en el JavaScript")
        print("Esto podría significar que el fallback se está ejecutando")
    
    return html_content

def verificar_consola_javascript():
    """Simular lo que vería la consola JavaScript"""
    print("\n=== SIMULACIÓN DE CONSOLA JAVASCRIPT ===")
    
    # Obtener el contexto
    factory = RequestFactory()
    request = factory.get('/analisis-crm/')
    response = dashboard(request)
    context = response.context_data
    
    # Simular el código JavaScript del template
    print("Código JavaScript que se ejecutaría:")
    print("--------------------------------------")
    
    if 'days_of_month_json' in context and 'counts_per_day_json' in context:
        days_json = context['days_of_month_json']
        counts_json = context['counts_per_day_json']
        
        print(f"1. Elementos script generados:")
        print(f'   <script id="days-data" type="application/json">{days_json[:50]}...</script>')
        print(f'   <script id="counts-data" type="application/json">{counts_json[:50]}...</script>')
        
        print(f"\n2. JavaScript ejecutándose:")
        print(f"   const daysElement = document.getElementById('days-data');")
        print(f"   const countsElement = document.getElementById('counts-data');")
        
        # Simular parseo
        import json
        try:
            days_list = json.loads(days_json)
            counts_list = json.loads(counts_json)
            
            print(f"\n3. Parseo exitoso:")
            print(f"   chartDays = {days_list[:5]}... (total: {len(days_list)} días)")
            print(f"   chartCounts = {counts_list[:5]}... (total: {len(counts_list)} valores)")
            
            # Buscar 5/3
            try:
                idx = days_list.index('05/03')
                print(f"\n4. Para el 5/3 (índice {idx}):")
                print(f"   Día: {days_list[idx]}")
                print(f"   Conteo: {counts_list[idx]}")
                
                if counts_list[idx] != 12:
                    print(f"   ¡PROBLEMA! El gráfico mostraría {counts_list[idx]} en lugar de 12")
                else:
                    print(f"   ✓ Correcto, el gráfico mostraría 12")
                    
            except ValueError:
                print(f"\n4. ERROR: '05/03' no encontrado en days_list")
                
        except json.JSONDecodeError as e:
            print(f"\n3. ERROR parseando JSON: {e}")
            print(f"   Se ejecutaría el fallback a datos de ejemplo")
            print(f"   chartDays = ['01/03', '02/03', '03/03', '04/03', '05/03']")
            print(f"   chartCounts = [12, 8, 15, 20, 10]")
            print(f"   ¡El gráfico mostraría 10 para el 5/3 en lugar de 12!")
    
    print("\n--------------------------------------")

def main():
    print("VERIFICACIÓN DE DATOS EN HTML/JavaScript")
    print("=" * 70)
    
    # Verificar contexto
    context = verificar_contexto_vista()
    
    # Verificar template
    html_content = verificar_template_rendering()
    
    # Verificar consola JavaScript
    verificar_consola_javascript()
    
    print("\n" + "=" * 70)
    print("RESUMEN:")
    
    # Verificar conclusión
    if 'days_of_month_json' in context:
        import json
        try:
            days_json = context['days_of_month_json']
            counts_json = context['counts_per_day_json']
            
            days_list = json.loads(days_json)
            counts_list = json.loads(counts_json)
            
            try:
                idx = days_list.index('05/03')
                valor = counts_list[idx]
                
                if valor == 12:
                    print("✓ Los datos son correctos en el contexto (12 para 5/3)")
                    print("  El problema debe estar en:")
                    print("  1. Cache del navegador")
                    print("  2. JavaScript no ejecutándose correctamente")
                    print("  3. Error en Chart.js")
                    print("\nSolución: Recargar la página con Ctrl+F5 para limpiar cache")
                else:
                    print(f"¡PROBLEMA! El valor para 5/3 es {valor} en lugar de 12")
                    print("  Esto indica un error en la vista o en los datos")
                    
            except ValueError:
                print("ERROR: '05/03' no encontrado en los datos")
                
        except json.JSONDecodeError:
            print("ERROR: JSON inválido en el contexto")
    else:
        print("ERROR: No hay datos JSON en el contexto")

if __name__ == '__main__':
    main()