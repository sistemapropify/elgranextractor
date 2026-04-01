import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from propifai.models import PropifaiProperty

# Simular la vista sin filtros
propiedades = PropifaiProperty.objects.all().order_by('-created_at')
print(f"Total propiedades: {propiedades.count()}")
print("Primeras 10 propiedades en el QuerySet ordenado:")
for i, prop in enumerate(propiedades[:10]):
    print(f"{i}: {prop.code} - {prop.created_at}")

# Verificar el orden en la lista propiedades_con_score (simulando el loop)
propiedades_con_score = []
for i, prop in enumerate(propiedades):
    # Simular cálculo de score
    propiedades_con_score.append(prop)
    if i < 5:
        print(f"Procesada propiedad {i}: {prop.code}")
        
print("\nCódigos en propiedades_con_score (primeras 10):")
for p in propiedades_con_score[:10]:
    print(p.code)