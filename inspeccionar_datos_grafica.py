#!/usr/bin/env python3
"""
Script para inspeccionar los datos de la gráfica de evolución de tipos de eventos.
"""

import os
import sys
import json
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prometeo.settings')

try:
    django.setup()
except Exception as e:
    print(f"Error configurando Django: {e}")
    sys.exit(1)

from eventos.models import Event, EventType
from eventos.views import calcular_evolucion_semanal_tipos_eventos

def main():
    print("=== INSPECCIÓN DE DATOS DE GRÁFICA ===")
    
    # Obtener todos los eventos
    eventos_list = Event.objects.all().order_by('-fecha_evento', '-hora_inicio')
    total_eventos = eventos_list.count()
    print(f"Total de eventos en BD: {total_eventos}")
    
    # Calcular datos del gráfico
    print("\nCalculando datos del gráfico...")
    datos_grafico = calcular_evolucion_semanal_tipos_eventos(eventos_list)
    
    # Analizar estructura
    print(f"\nEstructura del gráfico:")
    print(f"- Número de semanas: {len(datos_grafico['semanas'])}")
    print(f"- Semanas: {datos_grafico['semanas']}")
    print(f"- Número de tipos de eventos: {len(datos_grafico['tipos'])}")
    print(f"- Tipos: {list(datos_grafico['tipos'].values())}")
    
    # Analizar valores del eje Y
    print(f"\nAnálisis de valores del eje Y (conteos por tipo):")
    max_valor = 0
    min_valor = float('inf')
    total_valores = 0
    suma_valores = 0
    
    for tipo_id, valores in datos_grafico['datos'].items():
        tipo_nombre = datos_grafico['tipos'][tipo_id]
        max_tipo = max(valores) if valores else 0
        min_tipo = min(valores) if valores else 0
        suma_tipo = sum(valores)
        promedio_tipo = suma_tipo / len(valores) if valores else 0
        
        print(f"\n  Tipo: {tipo_nombre} (ID: {tipo_id})")
        print(f"    Valores: {valores}")
        print(f"    Máximo: {max_tipo}, Mínimo: {min_tipo}, Promedio: {promedio_tipo:.1f}")
        
        max_valor = max(max_valor, max_tipo)
        min_valor = min(min_valor, min_tipo)
        suma_valores += suma_tipo
        total_valores += len(valores)
    
    print(f"\nResumen global:")
    print(f"  Valor máximo en todos los tipos: {max_valor}")
    print(f"  Valor mínimo en todos los tipos: {min_valor}")
    if total_valores > 0:
        print(f"  Promedio global: {suma_valores / total_valores:.1f}")
    
    # Verificar si hay valores extremos
    print(f"\nAnálisis de valores extremos:")
    if max_valor > 100:
        print(f"  ⚠️  VALOR EXTREMO DETECTADO: {max_valor} eventos en una semana")
        print(f"     Esto podría causar expansión del eje Y.")
    elif max_valor > 50:
        print(f"  ⚠️  Valor alto: {max_valor} eventos en una semana")
    else:
        print(f"  ✅ Valores normales: máximo {max_valor} eventos")
    
    # Mostrar JSON completo (resumido)
    print(f"\nJSON completo (resumido):")
    json_str = json.dumps(datos_grafico, indent=2, ensure_ascii=False)
    if len(json_str) > 2000:
        print(json_str[:2000] + "...")
    else:
        print(json_str)
    
    # Recomendaciones
    print(f"\n=== RECOMENDACIONES ===")
    if max_valor > 50:
        print(f"1. Configurar límite máximo del eje Y en Chart.js a {max_valor + 10}")
        print(f"2. Considerar usar escala logarítmica si los valores varían mucho")
    else:
        print(f"1. Los valores son normales, el problema puede ser de CSS/Canvas")
    
    print(f"2. Asegurar que el canvas tenga height fijo en píxeles")
    print(f"3. Verificar que el contenedor tenga overflow: hidden")
    
    return datos_grafico

if __name__ == '__main__':
    main()