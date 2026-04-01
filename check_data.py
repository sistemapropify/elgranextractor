#!/usr/bin/env python
"""
Script para verificar datos en las bases de datos.
"""
import os
import sys
import django

# Configurar Django
sys.path.insert(0, 'webapp')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from ingestas.models import PropiedadRaw
from propifai.models import PropifaiProperty

print("=== Verificación de datos en bases de datos ===")

# Verificar PropiedadRaw (base local)
try:
    local_count = PropiedadRaw.objects.using('default').count()
    print(f"PropiedadRaw (default): {local_count} registros")
    
    # Verificar algunos campos
    if local_count > 0:
        sample = PropiedadRaw.objects.using('default').first()
        print(f"  Muestra: ID={sample.id}, precio_usd={sample.precio_usd}, coordenadas={sample.coordenadas}")
except Exception as e:
    print(f"Error en PropiedadRaw: {e}")

# Verificar PropifaiProperty
try:
    propifai_count = PropifaiProperty.objects.using('propifai').count()
    print(f"PropifaiProperty (propifai): {propifai_count} registros")
    
    if propifai_count > 0:
        sample = PropifaiProperty.objects.using('propifai').first()
        print(f"  Muestra: ID={sample.id}, price={sample.price}, coordinates={sample.coordinates}")
except Exception as e:
    print(f"Error en PropifaiProperty: {e}")

# Verificar métricas de calidad
print("\n=== Probando cálculo de métricas ===")
try:
    from market_analysis.charts import calculate_data_quality_metrics, create_data_quality_summary
    
    metrics = calculate_data_quality_metrics()
    print(f"Métricas calculadas: {metrics.keys()}")
    
    if 'local' in metrics:
        local = metrics['local']
        print(f"  Local: total_records={local.get('total_records')}, avg_completeness={local.get('avg_completeness')}")
    
    if 'propifai' in metrics:
        propifai = metrics['propifai']
        print(f"  Propifai: total_records={propifai.get('total_records')}, avg_completeness={propifai.get('avg_completeness')}")
    
    if 'overall' in metrics:
        overall = metrics['overall']
        print(f"  Overall: data_quality_score={overall.get('data_quality_score')}")
    
    # Verificar gráficos
    charts = create_data_quality_summary()
    print(f"\nGráficos generados: {len(charts)}")
    for key, value in charts.items():
        if value:
            print(f"  {key}: {'data:image' in str(value[:50])}")
        else:
            print(f"  {key}: VACÍO")
            
except Exception as e:
    print(f"Error en métricas: {e}")
    import traceback
    traceback.print_exc()