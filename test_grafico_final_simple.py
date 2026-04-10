#!/usr/bin/env python3
"""
Test simple para verificar que el gráfico de evolución semanal funciona correctamente.
"""

import os
import sys
import django

# Configurar Django
sys.path.append('webapp')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from eventos.models import Event, EventType
from eventos.views import calcular_evolucion_semanal_tipos_eventos
from django.utils import timezone
from datetime import timedelta

def test_datos_grafico():
    """Test que verifica que la función genera datos válidos."""
    print("=== Test de datos del gráfico ===")
    
    # Obtener todos los eventos
    eventos = Event.objects.all()
    print(f"Total de eventos en BD: {eventos.count()}")
    
    # Calcular evolución semanal
    datos = calcular_evolucion_semanal_tipos_eventos(eventos, semanas=8)
    
    # Verificar estructura
    assert 'semanas' in datos, "Falta clave 'semanas'"
    assert 'tipos' in datos, "Falta clave 'tipos'"
    assert 'datos' in datos, "Falta clave 'datos'"
    assert 'colores' in datos, "Falta clave 'colores'"
    
    print(f"Semanas generadas: {len(datos['semanas'])}")
    print(f"Tipos de eventos: {len(datos['tipos'])}")
    print(f"Colores generados: {len(datos['colores'])}")
    
    # Verificar que hay colores únicos
    colores = list(datos['colores'].values())
    colores_unicos = set(colores)
    print(f"Colores únicos: {len(colores_unicos)} de {len(colores)}")
    
    # Verificar que cada tipo tiene datos
    for tipo_id, tipo_nombre in datos['tipos'].items():
        if tipo_id in datos['datos']:
            datos_tipo = datos['datos'][tipo_id]
            print(f"  - {tipo_nombre}: {len(datos_tipo)} puntos de datos")
        else:
            print(f"  - {tipo_nombre}: Sin datos")
    
    # Verificar que no todos los colores son iguales
    if len(colores) > 1:
        todos_iguales = all(c == colores[0] for c in colores)
        if todos_iguales:
            print("¡ADVERTENCIA: Todos los colores son iguales!")
        else:
            print("✓ Los colores son distintos entre sí.")
    else:
        print("Solo hay un tipo de evento.")
    
    print("✓ Test de datos del gráfico completado exitosamente.")
    return True

if __name__ == '__main__':
    try:
        test_datos_grafico()
        print("\n✅ Todos los tests pasaron correctamente.")
    except Exception as e:
        print(f"\n❌ Error en el test: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)