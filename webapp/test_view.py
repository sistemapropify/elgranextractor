import sys
sys.path.insert(0, '.')
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
import django
django.setup()

from requerimientos.views import ListaRequerimientosView
print("Vista importada correctamente")
print("FuenteChoices importado:", hasattr(ListaRequerimientosView, 'get_context_data'))
# Crear una instancia de la vista
view = ListaRequerimientosView()
context = view.get_context_data()
print("Context keys:", context.keys())
print("Fuentes:", context['fuentes'])
print("Condiciones:", context['condiciones'])
print("Tipos propiedad:", context['tipos_propiedad'])