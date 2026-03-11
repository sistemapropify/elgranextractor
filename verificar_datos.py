import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
import django
django.setup()

from requerimientos.models import Requerimiento
from propifai.models import PropifaiProperty

print("=== VERIFICACIÓN DE DATOS ===")

# Ver requerimiento 9605
req = Requerimiento.objects.get(id=9605)
print(f"Requerimiento 9605:")
print(f"  Presupuesto monto: {req.presupuesto_monto}")
print(f"  Presupuesto display: {req.presupuesto_display}")
print(f"  Tipo de dato: {type(req.presupuesto_monto)}")
print(f"  Distritos: {req.distritos}")

# Ver propiedades
print(f"\nPropiedades (primeras 3):")
props = PropifaiProperty.objects.all()[:3]
for p in props:
    print(f"  ID {p.id}: precio {p.price} (tipo: {type(p.price)})")

# Verificar si 'nan' está en distritos
print(f"\nRequerimientos con distrito 'nan': {Requerimiento.objects.filter(distritos='nan').count()}")
print(f"Requerimientos con distrito que contiene 'nan': {Requerimiento.objects.filter(distritos__contains='nan').count()}")

# Ver mapeo de distritos
print(f"\nMapeo de distritos ID 7:")
print(f"  ID 7 debería ser 'cerro colorado'")
prop_7 = PropifaiProperty.objects.filter(district='7').first()
if prop_7:
    print(f"  Propiedad con district='7': {prop_7.id}, código {prop_7.code}")