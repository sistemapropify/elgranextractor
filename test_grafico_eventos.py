#!/usr/bin/env python3
"""
Script para probar la implementación del gráfico de evolución semanal de eventos.
"""

import os
import sys
import django

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
from datetime import date, timedelta

def test_calculo_grafico():
    """Prueba la función de cálculo del gráfico."""
    print("=== Prueba de cálculo de gráfico de evolución semanal ===")
    
    # Obtener algunos eventos de prueba
    eventos = Event.objects.all()
    print(f"Total de eventos en la base de datos: {eventos.count()}")
    
    if eventos.count() == 0:
        print("No hay eventos en la base de datos. Usando datos de prueba...")
        # En un caso real, aquí crearíamos datos de prueba
        print("La función debería manejar el caso sin datos.")
        return
    
    # Probar la función
    try:
        datos_grafico = calcular_evolucion_semanal_tipos_eventos(eventos, semanas=4)
        
        print(f"\nDatos del gráfico calculados exitosamente:")
        print(f"- Número de semanas: {len(datos_grafico['semanas'])}")
        print(f"- Etiquetas de semanas: {datos_grafico['semanas']}")
        print(f"- Número de tipos de eventos: {len(datos_grafico['tipos'])}")
        
        if datos_grafico['tipos']:
            print("\nTipos de eventos encontrados:")
            for tipo_id, tipo_nombre in datos_grafico['tipos'].items():
                color = datos_grafico['colores'].get(tipo_id, '#000000')
                datos_tipo = datos_grafico['datos'].get(tipo_id, [])
                print(f"  - {tipo_nombre} (ID: {tipo_id}): {len(datos_tipo)} valores, color: {color}")
        
        # Verificar estructura de datos
        print("\nVerificación de estructura:")
        print(f"  - 'semanas' en datos: {'semanas' in datos_grafico}")
        print(f"  - 'tipos' en datos: {'tipos' in datos_grafico}")
        print(f"  - 'datos' en datos: {'datos' in datos_grafico}")
        print(f"  - 'colores' en datos: {'colores' in datos_grafico}")
        
        # Verificar que los datos sean serializables (para JSON)
        import json
        try:
            json_str = json.dumps(datos_grafico)
            print(f"  - Datos serializables a JSON: Sí ({len(json_str)} bytes)")
        except Exception as e:
            print(f"  - Error serializando a JSON: {e}")
            
    except Exception as e:
        print(f"\nError al calcular el gráfico: {e}")
        import traceback
        traceback.print_exc()

def test_vista_eventos():
    """Prueba que la vista de eventos funcione correctamente."""
    print("\n=== Prueba de vista de eventos ===")
    
    from django.test import RequestFactory
    from eventos.views import dashboard_eventos
    
    # Crear una solicitud de prueba
    factory = RequestFactory()
    request = factory.get('/eventos/')
    
    try:
        # Simular la vista
        response = dashboard_eventos(request)
        
        print(f"Vista ejecutada exitosamente:")
        print(f"  - Status code: {response.status_code}")
        print(f"  - Template usado: {response.template_name}")
        
        # Verificar que el contexto tenga los datos del gráfico
        if hasattr(response, 'context_data'):
            context = response.context_data
            if 'grafico_evolucion' in context:
                print(f"  - Gráfico en contexto: Sí")
                grafico = context['grafico_evolucion']
                print(f"    * Semanas: {len(grafico.get('semanas', []))}")
                print(f"    * Tipos: {len(grafico.get('tipos', {}))}")
            else:
                print(f"  - Gráfico en contexto: No")
        else:
            print(f"  - No se pudo acceder al contexto")
            
    except Exception as e:
        print(f"Error en la vista: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    print("Iniciando pruebas de implementación del gráfico de eventos...")
    test_calculo_grafico()
    test_vista_eventos()
    print("\n=== Pruebas completadas ===")