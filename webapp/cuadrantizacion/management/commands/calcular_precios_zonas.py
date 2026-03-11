"""
Comando para calcular precios por m² de todas las zonas.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from cuadrantizacion.models import ZonaValor, HistorialPrecioZona
from cuadrantizacion.services import actualizar_estadisticas_zona
from ingestas.models import PropiedadRaw


class Command(BaseCommand):
    help = 'Calcula precios por m² para todas las zonas activas'

    def add_arguments(self, parser):
        parser.add_argument(
            '--zona-id',
            type=int,
            help='ID de zona específica a calcular (opcional)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forzar recálculo incluso si ya tiene datos recientes'
        )
        parser.add_argument(
            '--dias-ultima-actualizacion',
            type=int,
            default=7,
            help='Número de días para considerar datos obsoletos (default: 7)'
        )

    def handle(self, *args, **options):
        zona_id = options['zona_id']
        force = options['force']
        dias_obsoletos = options['dias_ultima_actualizacion']
        
        self.stdout.write(self.style.SUCCESS(
            f'Iniciando cálculo de precios por m² para zonas...'
        ))
        
        # Determinar qué zonas procesar
        if zona_id:
            zonas = ZonaValor.objects.filter(id=zona_id, activo=True)
            if not zonas.exists():
                self.stdout.write(self.style.ERROR(f'Zona {zona_id} no encontrada o inactiva'))
                return
        else:
            zonas = ZonaValor.objects.filter(activo=True)
        
        self.stdout.write(f'Procesando {zonas.count()} zona(s)')
        
        # Fecha límite para considerar datos obsoletos
        fecha_limite = timezone.now() - timezone.timedelta(days=dias_obsoletos)
        
        total_zonas = zonas.count()
        zonas_procesadas = 0
        zonas_actualizadas = 0
        zonas_omitidas = 0
        errores = 0
        
        for zona in zonas:
            try:
                # Verificar si necesita actualización
                necesita_actualizacion = force
                
                if not necesita_actualizacion:
                    if not zona.fecha_actualizacion:
                        necesita_actualizacion = True
                    elif zona.fecha_actualizacion < fecha_limite:
                        necesita_actualizacion = True
                    elif zona.cantidad_propiedades_analizadas == 0:
                        necesita_actualizacion = True
                
                if not necesita_actualizacion:
                    self.stdout.write(
                        f'  Zona "{zona.nombre_zona}" ya actualizada recientemente, omitiendo...'
                    )
                    zonas_omitidas += 1
                    continue
                
                self.stdout.write(f'  Calculando zona: {zona.nombre_zona}...')
                
                # Actualizar estadísticas
                actualizar_estadisticas_zona(zona)
                
                zonas_actualizadas += 1
                self.stdout.write(self.style.SUCCESS(
                    f'    ✓ Actualizada: ${zona.precio_promedio_m2 or 0:.2f}/m² '
                    f'({zona.cantidad_propiedades_analizadas} propiedades)'
                ))
                
                zonas_procesadas += 1
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f'  ✗ Error en zona {zona.nombre_zona}: {str(e)}'
                ))
                errores += 1
        
        # Resumen
        self.stdout.write(self.style.SUCCESS('\n' + '='*50))
        self.stdout.write(self.style.SUCCESS('RESUMEN DE CÁLCULO'))
        self.stdout.write(self.style.SUCCESS('='*50))
        self.stdout.write(f'Zonas totales: {total_zonas}')
        self.stdout.write(f'Zonas procesadas: {zonas_procesadas}')
        self.stdout.write(f'Zonas actualizadas: {zonas_actualizadas}')
        self.stdout.write(f'Zonas omitidas: {zonas_omitidas}')
        self.stdout.write(f'Errores: {errores}')
        
        if zonas_actualizadas > 0:
            # Estadísticas generales
            zonas_con_precio = ZonaValor.objects.filter(
                activo=True, 
                precio_promedio_m2__isnull=False
            )
            
            if zonas_con_precio.exists():
                precio_promedio = zonas_con_precio.aggregate(
                    avg=models.Avg('precio_promedio_m2')
                )['avg']
                
                zona_mas_cara = zonas_con_precio.order_by('-precio_promedio_m2').first()
                zona_mas_barata = zonas_con_precio.order_by('precio_promedio_m2').first()
                
                self.stdout.write('\n' + self.style.SUCCESS('ESTADÍSTICAS GLOBALES:'))
                self.stdout.write(f'  Precio promedio global: ${precio_promedio:.2f}/m²')
                self.stdout.write(f'  Zona más cara: {zona_mas_cara.nombre_zona} (${zona_mas_cara.precio_promedio_m2:.2f}/m²)')
                self.stdout.write(f'  Zona más barata: {zona_mas_barata.nombre_zona} (${zona_mas_barata.precio_promedio_m2:.2f}/m²)')
        
        self.stdout.write('\n' + self.style.SUCCESS('¡Cálculo completado!'))


# Import para funciones de agregación
from django.db import models