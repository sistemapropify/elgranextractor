import os
import sys
import django
from datetime import timedelta

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from requerimientos.models import Requerimiento, FuenteChoices
from django.utils import timezone

def main():
    # Contar requerimientos con fuente inmobiliarias_unidas
    count_unidas = Requerimiento.objects.filter(fuente=FuenteChoices.UNIDAS).count()
    print(f"Requerimientos con fuente 'inmobiliarias_unidas': {count_unidas}")
    
    # Actualizar aquellos creados recientemente (últimas 24 horas)
    hace_24_horas = timezone.now() - timedelta(hours=24)
    recientes = Requerimiento.objects.filter(creado_en__gte=hace_24_horas, fuente=FuenteChoices.UNIDAS)
    print(f"Requerimientos recientes (24h) con fuente UNIDAS: {recientes.count()}")
    
    # Actualizar a RED_INMOBILIARIA
    actualizados = recientes.update(fuente=FuenteChoices.RED_INMOBILIARIA)
    print(f"Actualizados a RED_INMOBILIARIA: {actualizados}")
    
    # Verificar totales
    total_red = Requerimiento.objects.filter(fuente=FuenteChoices.RED_INMOBILIARIA).count()
    print(f"Total requerimientos con fuente RED_INMOBILIARIA: {total_red}")
    
    # Mostrar conteo por fuente
    from django.db.models import Count
    print("\nConteo por fuente:")
    for fuente, count in Requerimiento.objects.values('fuente').annotate(total=Count('id')).order_by('-total'):
        print(f"  {fuente}: {count}")

if __name__ == '__main__':
    main()