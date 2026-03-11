import os
import sys
import django

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from requerimientos.models import Requerimiento, FuenteChoices
from django.db.models import Count

def main():
    total = Requerimiento.objects.count()
    print(f"Total requerimientos: {total}")
    
    print("\nConteo por fuente:")
    for fuente, count in Requerimiento.objects.values('fuente').annotate(total=Count('id')).order_by('-total'):
        print(f"  {fuente}: {count}")
    
    # Verificar que todos los importados tengan fuente RED_INMOBILIARIA
    red_count = Requerimiento.objects.filter(fuente=FuenteChoices.RED_INMOBILIARIA).count()
    print(f"\nRequerimientos con fuente RED_INMOBILIARIA: {red_count}")
    
    # Si hay otros, podrían ser de importaciones anteriores (exito_inmobiliario)
    otros = total - red_count
    if otros > 0:
        print(f"Otros requerimientos (posiblemente de otras fuentes): {otros}")
        otras_fuentes = Requerimiento.objects.exclude(fuente=FuenteChoices.RED_INMOBILIARIA).values('fuente').annotate(c=Count('id'))
        for f in otras_fuentes:
            print(f"  Fuente {f['fuente']}: {f['c']}")

if __name__ == '__main__':
    main()