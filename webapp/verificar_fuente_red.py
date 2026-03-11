import os
import sys
import django

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from requerimientos.models import Requerimiento, FuenteChoices
from django.db.models import Count

def main():
    total_red = Requerimiento.objects.filter(fuente=FuenteChoices.RED_INMOBILIARIA).count()
    print(f"Total requerimientos con fuente RED_INMOBILIARIA: {total_red}")
    
    if total_red > 0:
        print("\nPrimeros 5 requerimientos con fuente RED_INMOBILIARIA:")
        for r in Requerimiento.objects.filter(fuente=FuenteChoices.RED_INMOBILIARIA).order_by('-id')[:5]:
            print(f"  ID: {r.id}, Agente: {r.agente[:30]}, Fecha: {r.fecha}, Distritos: {r.distritos[:30]}")
    
    print("\nConteo por fuente:")
    for fuente, count in Requerimiento.objects.values('fuente').annotate(total=Count('id')).order_by('-total'):
        print(f"  {fuente}: {count}")
    
    # Verificar que haya exactamente 552 (los que importamos)
    if total_red == 552:
        print("\n✅ Todos los requerimientos importados tienen la fuente correcta.")
    else:
        print(f"\n⚠️  Advertencia: se esperaban 552, pero hay {total_red}.")

if __name__ == '__main__':
    main()