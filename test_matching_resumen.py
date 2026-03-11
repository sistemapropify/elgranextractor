import os
import sys
import django
import time

# Configurar Django
sys.path.append('d:/proyectos/prometeo/webapp')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from matching.engine import obtener_resumen_matching_masivo

print("Ejecutando obtener_resumen_matching_masivo()...")
start = time.time()
try:
    resumen = obtener_resumen_matching_masivo()
    elapsed = time.time() - start
    print(f"Función completada en {elapsed:.2f} segundos")
    print(f"Total de items en resumen: {len(resumen)}")
    if resumen:
        print(f"Primer item: {resumen[0]}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()