#!/usr/bin/env python
"""
Script para probar la función calcular_matriz_agente_semana
"""
import os
import sys
import django

# Configurar Django
sys.path.append('d:/proyectos/prometeo/webapp')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from eventos.views import calcular_matriz_agente_semana
from eventos.models import Event
from datetime import date, timedelta

def test_matriz():
    print("=== Prueba de calcular_matriz_agente_semana ===")
    
    # Obtener eventos de los últimos 6 meses (para tener datos)
    fecha_limite = date.today() - timedelta(days=180)
    eventos_qs = Event.objects.filter(fecha_evento__gte=fecha_limite)
    
    if not eventos_qs.exists():
        print("No hay eventos recientes en la base de datos para probar.")
        # Intentar con cualquier evento
        eventos_qs = Event.objects.all()[:50]
        if not eventos_qs.exists():
            print("No hay eventos en la base de datos.")
            return
    
    print(f"Total de eventos para prueba: {eventos_qs.count()}")
    
    try:
        # Calcular matriz
        matriz = calcular_matriz_agente_semana(eventos_qs)
        
        # Mostrar resultados
        print(f"\nAgentes encontrados: {len(matriz['agentes'])}")
        for agente in matriz['agentes'][:5]:  # Mostrar primeros 5
            print(f"  - {agente['nombre_completo']} (ID: {agente['id']})")
        
        print(f"\nSemanas analizadas: {len(matriz['semanas_labels'])}")
        for i, (iso, label) in enumerate(zip(matriz['semanas_iso'], matriz['semanas_labels'])):
            print(f"  {i+1}. {iso} -> {label}")
        
        print(f"\nTipos de evento: {len(matriz['tipos_evento'])}")
        for tipo in matriz['tipos_evento'][:5]:
            print(f"  - {tipo['name']} (ID: {tipo['id']})")
        
        # Mostrar algunos datos de la matriz
        print("\nMuestra de datos de matriz:")
        agentes_con_datos = [a for a in matriz['agentes'] if a['id'] in matriz['matriz']]
        for agente in agentes_con_datos[:3]:
            agente_id = agente['id']
            semanas_data = matriz['matriz'][agente_id]
            for semana in list(semanas_data.keys())[:2]:
                tipos_data = semanas_data[semana]
                if tipos_data:
                    print(f"  Agente {agente['nombre_completo']}, Semana {semana}:")
                    for tipo_id, cantidad in list(tipos_data.items())[:3]:
                        print(f"    - Tipo {tipo_id}: {cantidad} eventos")
        
        print("\nTotales por semana:")
        for semana, total in list(matriz['totales_semana'].items())[:3]:
            print(f"  {semana}: {total} eventos")
        
        print("\n¡Prueba completada exitosamente!")
        return True
        
    except Exception as e:
        print(f"\nERROR durante la prueba: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_matriz()
    sys.exit(0 if success else 1)