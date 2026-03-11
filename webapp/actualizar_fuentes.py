import os
import sys
import django
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from requerimientos.models import Requerimiento, FuenteChoices

def main():
    # Contar requerimientos con fuente inmobiliarias_unidas
    count_unidas = Requerimiento.objects.filter(fuente=FuenteChoices.UNIDAS).count()
    print(f"Requerimientos con fuente 'inmobiliarias_unidas': {count_unidas}")
    
    # Actualizar aquellos que tengan agente que contenga 'RED INMOBILIARIA' o similar
    # o que hayan sido creados recientemente (últimas 24 horas)
    from django.utils import timezone
    hace_24_horas = timezone.now() - timedelta(hours=24)
    
    recientes = Requerimiento.objects.filter(creado_en__gte=hace_24_horas, fuente=FuenteChoices.UNIDAS)
    print(f"Requerimientos recientes (24h) con fuente UNIDAS: {recientes.count()}")
    
    # Actualizar a RED_INMOBILIARIA
    actualizados = recientes.update(fuente=FuenteChoices.RED_INMOBILIARIA)
    print(f"Actualizados a RED_INMOBILIARIA: {actualizados}")
    
    # También actualizar aquellos cuyo agente contenga 'RED INMOBILIARIA' (por si acaso)
    from django.db.models import Q
    red_inmobiliaria_qs = Requerimiento.objects.filter(
        Q(agente__icontains='RED INMOBILIARIA') | 
        Q(agente__icontains='Red Inmobiliaria') |
        Q(fuente__icontains='red')
    ).exclude(fuente=FuenteChoices.RED_INMOBILIARIA)
    
    print(f"Requerimientos con texto 'RED INMOBILIARIA' en agente: {red_inmobiliaria_qs.count()}")
    extra_actualizados = red_inmobiliaria_qs.update(fuente=FuenteChoices.RED_INMOBILIARIA)
    print(f"Extra actualizados: {extra_actualizados}")
    
    # Verificar totales
    total_red = Requerimiento.objects.filter(fuente=FuenteChoices.RED_INMOBILIARIA).count()
    print(f"\nTotal requerimientos con fuente RED_INMOBILIARIA: {total_red}")
    
    # Mostrar algunas fuentes únicas
    fuentes = Requerimiento.objects.values_list('fuente', flat=True).distinct()
    print("Fuentes únicas ahora:", list(fuentes))

if __name__ == '__main__':
    main()