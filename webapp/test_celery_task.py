#!/usr/bin/env python
"""
Script para probar la tarea Celery de análisis temporal.
"""
import os
import sys
import django
from datetime import datetime, timedelta

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from requerimientos.tasks import generar_analisis_temporal
from requerimientos.tasks import obtener_progreso_tarea

def test_celery_task():
    """Prueba la ejecución de la tarea Celery."""
    print("=== PRUEBA DE TAREA CELERY ===")
    
    # Configurar fechas (últimos 6 meses)
    fecha_fin = datetime.now()
    fecha_inicio = fecha_fin - timedelta(days=180)
    
    print(f"Fecha inicio: {fecha_inicio}")
    print(f"Fecha fin: {fecha_fin}")
    
    try:
        # Ejecutar tarea de forma síncrona (no async) para ver errores
        print("\nEjecutando tarea de forma síncrona...")
        result = generar_analisis_temporal.apply(args=[None, fecha_inicio, fecha_fin])
        
        print(f"Task ID: {result.id}")
        print(f"Estado: {result.state}")
        
        # Esperar y obtener resultado
        if result.ready():
            print("Tarea completada")
            if result.successful():
                data = result.get()
                print(f"Resultado exitoso. Datos recibidos: {len(data) if data else 0} elementos")
                if data and 'datos_mes' in data:
                    print(f"  - Meses procesados: {len(data['datos_mes'])}")
                if data and 'distritos_mes' in data:
                    print(f"  - Distritos procesados: {len(data['distritos_mes'])}")
            else:
                print(f"Tarea falló: {result.result}")
                print(f"Traceback: {result.traceback}")
        else:
            print("Tarea aún en progreso")
            
    except Exception as e:
        print(f"Error al ejecutar tarea: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n=== PRUEBA DE PROGRESO EN CACHE ===")
    try:
        # Crear una tarea real para probar progreso
        print("Creando tarea asíncrona...")
        async_task = generar_analisis_temporal.delay(None, fecha_inicio, fecha_fin)
        task_id = async_task.id
        print(f"Task ID creado: {task_id}")
        
        # Verificar progreso inmediatamente
        progress = obtener_progreso_tarea(task_id)
        print(f"Progreso inicial: {progress}")
        
    except Exception as e:
        print(f"Error en prueba de progreso: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_celery_task()