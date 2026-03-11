#!/usr/bin/env python
"""Script para probar la tarea completa de análisis temporal."""

import os
import sys
import django
from datetime import datetime, timedelta

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

django.setup()

from requerimientos.tasks import generar_analisis_temporal

print("=== Probando tarea generar_analisis_temporal ===")

# Configurar fechas de prueba (últimos 30 días)
fecha_fin = datetime.now().date()
fecha_inicio = fecha_fin - timedelta(days=30)

print(f"Fechas: {fecha_inicio} a {fecha_fin}")

try:
    # Ejecutar tarea directamente (no como Celery)
    print("1. Ejecutando tarea...")
    resultado = generar_analisis_temporal(
        filtros={},
        fecha_inicio=fecha_inicio.isoformat(),
        fecha_fin=fecha_fin.isoformat()
    )
    
    print(f"   Éxito! Resultado obtenido.")
    print(f"   - Datos por mes: {len(resultado['datos_mes'])} meses")
    print(f"   - Distritos: {len(resultado['distritos_mes']['distritos'])}")
    print(f"   - Tipos propiedad: {len(resultado['tipos_mes']['tipos'])}")
    print(f"   - Presupuesto: {len(resultado['presupuesto_mes']['promedio'])} meses")
    
except Exception as e:
    print(f"   ERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    
    # Probar cada función por separado
    print("\n2. Probando funciones individualmente...")
    from requerimientos.analytics import (
        obtener_requerimientos_por_mes,
        obtener_distritos_por_mes,
        obtener_tipos_propiedad_por_mes,
        obtener_presupuesto_por_mes,
        obtener_caracteristicas_demandadas
    )
    
    try:
        print("   a. obtener_requerimientos_por_mes...")
        datos = list(obtener_requerimientos_por_mes(fecha_inicio, fecha_fin, {}))
        print(f"      OK: {len(datos)} meses")
    except Exception as e2:
        print(f"      ERROR: {e2}")
    
    try:
        print("   b. obtener_distritos_por_mes...")
        distritos = obtener_distritos_por_mes(fecha_inicio, fecha_fin)
        print(f"      OK: {len(distritos['distritos'])} distritos")
    except Exception as e2:
        print(f"      ERROR: {e2}")
    
    try:
        print("   c. obtener_tipos_propiedad_por_mes...")
        tipos = obtener_tipos_propiedad_por_mes(fecha_inicio, fecha_fin)
        print(f"      OK: {len(tipos['tipos'])} tipos")
    except Exception as e2:
        print(f"      ERROR: {e2}")
    
    try:
        print("   d. obtener_presupuesto_por_mes...")
        presupuesto = obtener_presupuesto_por_mes(fecha_inicio, fecha_fin)
        print(f"      OK: {len(presupuesto['promedio'])} meses")
    except Exception as e2:
        print(f"      ERROR: {e2}")
    
    try:
        print("   e. obtener_caracteristicas_demandadas...")
        caracteristicas = obtener_caracteristicas_demandadas(fecha_inicio, fecha_fin)
        print(f"      OK: {len(caracteristicas['caracteristicas'])} características")
    except Exception as e2:
        print(f"      ERROR: {e2}")

print("\n=== Prueba completada ===")