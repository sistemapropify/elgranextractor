#!/usr/bin/env python3
"""
Prueba final del gráfico de evolución de eventos.
"""

import os
import sys
import django
import json

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

try:
    django.setup()
except Exception as e:
    print(f"Error configurando Django: {e}")
    sys.exit(1)

from eventos.views import calcular_evolucion_semanal_tipos_eventos
from eventos.models import Event

def test_colores_unicos():
    """Verificar que los colores sean únicos para cada tipo."""
    print("=== Prueba de colores únicos ===")
    
    eventos = Event.objects.all()
    datos = calcular_evolucion_semanal_tipos_eventos(eventos, semanas=4)
    
    if not datos or not datos['tipos']:
        print("No hay datos para probar.")
        return
    
    tipos = datos['tipos']
    colores = datos['colores']
    
    print(f"Tipos de eventos: {len(tipos)}")
    print(f"Colores asignados: {len(colores)}")
    
    # Verificar que cada tipo tenga un color
    for tipo_id, tipo_nombre in tipos.items():
        color = colores.get(tipo_id, 'No asignado')
        print(f"  - {tipo_nombre}: {color}")
    
    # Verificar unicidad
    colores_lista = list(colores.values())
    colores_unicos = set(colores_lista)
    
    print(f"\nColores únicos: {len(colores_unicos)} de {len(colores_lista)}")
    
    if len(colores_unicos) < len(colores_lista):
        print("ADVERTENCIA: Hay colores duplicados!")
        # Contar duplicados
        from collections import Counter
        conteo = Counter(colores_lista)
        for color, count in conteo.items():
            if count > 1:
                print(f"  - Color {color} aparece {count} veces")
    else:
        print("✓ Todos los colores son únicos.")
    
    # Verificar que los datos sean válidos para JSON
    try:
        json_str = json.dumps(datos)
        print(f"\n✓ Datos serializables a JSON: {len(json_str)} bytes")
    except Exception as e:
        print(f"\n✗ Error serializando a JSON: {e}")

def test_estructura_datos():
    """Verificar la estructura de datos para Chart.js."""
    print("\n=== Prueba de estructura de datos ===")
    
    eventos = Event.objects.all()
    datos = calcular_evolucion_semanal_tipos_eventos(eventos, semanas=4)
    
    if not datos:
        print("No se generaron datos.")
        return
    
    # Verificar estructura requerida
    required_keys = ['semanas', 'tipos', 'datos', 'colores']
    for key in required_keys:
        if key in datos:
            print(f"✓ Clave '{key}' presente")
        else:
            print(f"✗ Clave '{key}' faltante")
    
    # Verificar que los arrays tengan la misma longitud
    if 'semanas' in datos and 'tipos' in datos:
        semanas_len = len(datos['semanas'])
        print(f"\nSemanas: {semanas_len}")
        
        for tipo_id, valores in datos.get('datos', {}).items():
            if len(valores) != semanas_len:
                print(f"✗ Tipo {tipo_id}: {len(valores)} valores, esperados {semanas_len}")
            else:
                print(f"✓ Tipo {tipo_id}: {len(valores)} valores correctos")
    
    # Verificar que haya datos no cero
    datos_con_valores = False
    for tipo_id, valores in datos.get('datos', {}).items():
        if any(v > 0 for v in valores):
            datos_con_valores = True
            break
    
    if datos_con_valores:
        print("\n✓ Hay datos con valores mayores a cero")
    else:
        print("\n⚠ Todos los valores son cero (puede ser normal si no hay eventos recientes)")

def test_vista_web():
    """Simular una solicitud HTTP a la vista."""
    print("\n=== Prueba de vista web ===")
    
    from django.test import RequestFactory
    from eventos.views import dashboard_eventos
    
    factory = RequestFactory()
    request = factory.get('/eventos/')
    
    try:
        response = dashboard_eventos(request)
        
        if response.status_code == 200:
            print("✓ Vista responde con status 200")
            
            # Verificar que el contexto tenga los datos del gráfico
            if hasattr(response, 'context_data'):
                context = response.context_data
                if 'grafico_evolucion' in context:
                    grafico = context['grafico_evolucion']
                    print(f"✓ Gráfico en contexto: {len(grafico.get('semanas', []))} semanas, {len(grafico.get('tipos', {}))} tipos")
                    
                    # Verificar serialización
                    try:
                        import json
                        json.dumps(grafico)
                        print("✓ Datos del gráfico serializables")
                    except Exception as e:
                        print(f"✗ Error serializando datos del gráfico: {e}")
                else:
                    print("⚠ Gráfico no en contexto (puede ser normal si no hay datos)")
            else:
                print("⚠ No se pudo acceder al contexto")
        else:
            print(f"✗ Vista responde con status {response.status_code}")
            
    except Exception as e:
        print(f"✗ Error en la vista: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    print("Iniciando pruebas finales del gráfico de eventos...")
    test_colores_unicos()
    test_estructura_datos()
    test_vista_web()
    print("\n=== Pruebas completadas ===")