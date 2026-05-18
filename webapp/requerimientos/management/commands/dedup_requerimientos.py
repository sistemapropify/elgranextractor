import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from requerimientos.models import Requerimiento

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Elimina registros duplicados de Requerimiento manteniendo el más reciente'

    def handle(self, *args, **options):
        # Definir los campos que identifican un registro único
        unique_fields = [
            'fuente',
            'fecha',
            'hora',
            'agente',
            'requerimiento',
        ]
        # Construir diccionario para agrupar
        from django.db.models import Count, Max
        duplicates = (
            Requerimiento.objects.values(*unique_fields)
            .annotate(cnt=Count('id'), max_id=Max('id'))
            .filter(cnt__gt=1)
        )
        total_deleted = 0
        with transaction.atomic():
            for dup in duplicates:
                # Obtener todos los IDs excepto el más reciente (max_id)
                ids_to_delete = (
                    Requerimiento.objects.filter(
                        fuente=dup['fuente'],
                        fecha=dup['fecha'],
                        hora=dup['hora'],
                        agente=dup['agente'],
                        requerimiento=dup['requerimiento']
                    )
                    .exclude(id=dup['max_id'])
                    .values_list('id', flat=True)
                )
                deleted, _ = Requerimiento.objects.filter(id__in=list(ids_to_delete)).delete()
                total_deleted += deleted
        self.stdout.write(self.style.SUCCESS(f'Duplicados eliminados: {total_deleted}'))
