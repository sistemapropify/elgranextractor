"""
Comando para migrar propiedades existentes a valoraciones por m².
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from tqdm import tqdm

from cuadrantizacion.utils import calcular_valoracion_propiedad, migrar_propiedades_existentes
from ingestas.models import PropiedadRaw


class Command(BaseCommand):
    help = 'Migra propiedades existentes a valoraciones por m² y las asocia a zonas'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Tamaño del lote para procesamiento (default: 100)'
        )
        parser.add_argument(
            '--skip-zones',
            action='store_true',
            help='Saltar asignación de zonas (solo calcular precio m²)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forzar reprocesamiento de todas las propiedades'
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        skip_zones = options['skip_zones']
        force = options['force']
        
        self.stdout.write(self.style.SUCCESS(
            f'Iniciando migración de propiedades a valoraciones...'
        ))
        
        if skip_zones:
            self.stdout.write(self.style.WARNING('Saltando asignación de zonas'))
        
        # Obtener propiedades a procesar
        if force:
            propiedades = PropiedadRaw.objects.all()
            self.stdout.write(f'Forzando reprocesamiento de {propiedades.count()} propiedades')
        else:
            # Solo propiedades que no tienen valoraciones o necesitan actualización
            propiedades = PropiedadRaw.objects.all()
            self.stdout.write(f'Procesando {propiedades.count()} propiedades')
        
        # Estadísticas
        total = propiedades.count()
        procesadas = 0
        valoraciones_creadas = 0
        valoraciones_actualizadas = 0
        errores = 0
        
        # Procesar en lotes
        self.stdout.write(f'Procesando en lotes de {batch_size}...')
        
        with transaction.atomic():
            for i in tqdm(range(0, total, batch_size), desc="Procesando propiedades"):
                batch = propiedades[i:i + batch_size]
                
                for propiedad in batch:
                    try:
                        # Calcular valoración
                        valoracion = calcular_valoracion_propiedad(propiedad)
                        
                        if valoracion.pk:
                            valoraciones_actualizadas += 1
                        else:
                            valoraciones_creadas += 1
                        
                        procesadas += 1
                        
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(
                            f'Error procesando propiedad {propiedad.id}: {str(e)}'
                        ))
                        errores += 1
        
        # Resumen
        self.stdout.write(self.style.SUCCESS('\n' + '='*50))
        self.stdout.write(self.style.SUCCESS('RESUMEN DE MIGRACIÓN'))
        self.stdout.write(self.style.SUCCESS('='*50))
        self.stdout.write(f'Total propiedades: {total}')
        self.stdout.write(f'Procesadas: {procesadas}')
        self.stdout.write(f'Valoraciones creadas: {valoraciones_creadas}')
        self.stdout.write(f'Valoraciones actualizadas: {valoraciones_actualizadas}')
        self.stdout.write(f'Errores: {errores}')
        
        if errores > 0:
            self.stdout.write(self.style.WARNING(
                f'Se encontraron {errores} errores durante la migración'
            ))
        
        # Sugerir siguiente paso
        self.stdout.write('\n' + self.style.SUCCESS('Siguientes pasos recomendados:'))
        self.stdout.write('1. Crear zonas de valor en el mapa (/cuadrantizacion/mapa)')
        self.stdout.write('2. Calcular precios por zona: python manage.py calcular_precios_zonas')
        self.stdout.write('3. Generar estadísticas: python manage.py generar_estadisticas_zonas')