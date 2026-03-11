import os
import sys
import django

# Añadir el directorio actual al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

try:
    django.setup()
    print("Django configurado correctamente")
except Exception as e:
    print(f"Error configurando Django: {e}")
    sys.exit(1)

from requerimientos.tasks import generar_analisis_temporal
from datetime import datetime, timedelta

print("=== PRUEBA SIMPLE DE CELERY ===")

fecha_fin = datetime.now()
fecha_inicio = fecha_fin - timedelta(days=180)
print(f"Fecha inicio: {fecha_inicio}")
print(f"Fecha fin: {fecha_fin}")

try:
    print("\nIntentando ejecutar tarea...")
    # Usar apply() para ejecución síncrona y ver errores
    result = generar_analisis_temporal.apply(args=[None, fecha_inicio, fecha_fin])
    print(f"Task ID: {result.id}")
    print(f"Estado: {result.state}")
    
    if result.ready():
        print("Tarea lista")
        if result.successful():
            data = result.get()
            print(f"Éxito! Datos: {len(data) if data else 0} elementos")
        else:
            print(f"Fallo: {result.result}")
            if hasattr(result, 'traceback'):
                print(f"Traceback: {result.traceback}")
    else:
        print("Tarea aún en progreso")
        
except Exception as e:
    print(f"Error general: {e}")
    import traceback
    traceback.print_exc()