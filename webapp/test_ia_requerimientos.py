import sys
import os
sys.path.insert(0, '.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
import django
django.setup()

from requerimientos.services import ExtractorInteligenteRequerimientos

texto = 'Requerimiento de casa de 2 habitaciones 1 baño en distrito de Cayma y Yanahuara.'
print('Texto:', texto)
try:
    resultado = ExtractorInteligenteRequerimientos.extraer_datos_requerimiento(texto)
    print('Resultado:', resultado)
except Exception as e:
    print('Error:', e)
    import traceback
    traceback.print_exc()