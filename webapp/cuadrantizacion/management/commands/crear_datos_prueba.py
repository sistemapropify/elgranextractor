"""
Comando para crear datos de prueba para el sistema de cuadrantización.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal
import random

from cuadrantizacion.models import ZonaValor, PropiedadValoracion, EstadisticaZona, HistorialPrecioZona
from ingestas.models import PropiedadRaw


class Command(BaseCommand):
    help = 'Crea datos de prueba para el sistema de cuadrantización'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Eliminar datos existentes antes de crear nuevos'
        )
        parser.add_argument(
            '--zonas',
            type=int,
            default=5,
            help='Número de zonas a crear (default: 5)'
        )
        parser.add_argument(
            '--propiedades-por-zona',
            type=int,
            default=10,
            help='Número de propiedades por zona (default: 10)'
        )

    def handle(self, *args, **options):
        clear = options['clear']
        num_zonas = options['zonas']
        propiedades_por_zona = options['propiedades_por_zona']
        
        self.stdout.write(self.style.SUCCESS(
            f'Creando datos de prueba: {num_zonas} zonas con {propiedades_por_zona} propiedades cada una'
        ))
        
        if clear:
            self.stdout.write('Eliminando datos existentes...')
            ZonaValor.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Datos eliminados'))
        
        # Coordenadas de Lima, Perú (área aproximada)
        lima_bounds = {
            'min_lat': -12.20,
            'max_lat': -11.85,
            'min_lng': -77.15,
            'max_lng': -76.95
        }
        
        # Nombres de zonas de prueba
        nombres_zonas = [
            'Miraflores Centro',
            'San Isidro Financiero',
            'Barranco Bohemio',
            'Surco Residencial',
            'La Molina Alta',
            'San Borja Comercial',
            'Jesus María Tradicional',
            'Lince Emergente',
            'Magdalena Costera',
            'Pueblo Libre Histórico'
        ]
        
        # Crear zonas
        zonas_creadas = []
        
        for i in range(min(num_zonas, len(nombres_zonas))):
            nombre = nombres_zonas[i]
            
            # Crear polígono cuadrado aleatorio dentro de Lima
            centro_lat = random.uniform(lima_bounds['min_lat'], lima_bounds['max_lat'])
            centro_lng = random.uniform(lima_bounds['min_lng'], lima_bounds['max_lng'])
            tamaño = 0.02  # Aprox 2km
            
            coordenadas = [
                [centro_lat - tamaño, centro_lng - tamaño],
                [centro_lat - tamaño, centro_lng + tamaño],
                [centro_lat + tamaño, centro_lng + tamaño],
                [centro_lat + tamaño, centro_lng - tamaño],
                [centro_lat - tamaño, centro_lng - tamaño]  # Cerrar polígono
            ]
            
            # Precio base aleatorio por m² (entre 800 y 3000 USD)
            precio_base = Decimal(random.uniform(800, 3000))
            
            zona = ZonaValor.objects.create(
                nombre_zona=nombre,
                descripcion=f'Zona de prueba {i+1}: {nombre}',
                coordenadas=coordenadas,
                precio_promedio_m2=precio_base,
                cantidad_propiedades_analizadas=propiedades_por_zona,
                area_total=Decimal(random.uniform(100000, 500000)),  # 10-50 hectáreas
                desviacion_estandar_m2=Decimal(random.uniform(50, 200)),
                color_fill=self.get_color_by_price(precio_base),
                color_borde=self.get_border_color_by_price(precio_base),
                opacidad=0.3
            )
            
            zonas_creadas.append(zona)
            self.stdout.write(f'  ✓ Zona creada: {nombre} (${precio_base:.2f}/m²)')
            
            # Crear estadísticas por tipo
            self.crear_estadisticas_zona(zona)
            
            # Crear historial de precios
            self.crear_historial_precios(zona)
        
        # Crear propiedades de prueba si existen propiedades raw
        try:
            propiedades_existentes = PropiedadRaw.objects.count()
            if propiedades_existentes > 0:
                self.stdout.write(f'\nEncontradas {propiedades_existentes} propiedades existentes')
                self.stdout.write('Asignando propiedades a zonas...')
                self.asignar_propiedades_a_zonas(zonas_creadas)
            else:
                self.stdout.write(self.style.WARNING(
                    '\nNo hay propiedades existentes en la base de datos.'
                ))
                self.stdout.write('Ejecuta primero la migración de datos reales.')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error accediendo a propiedades: {str(e)}'))
        
        # Resumen
        self.stdout.write(self.style.SUCCESS('\n' + '='*50))
        self.stdout.write(self.style.SUCCESS('DATOS DE PRUEBA CREADOS EXITOSAMENTE'))
        self.stdout.write(self.style.SUCCESS('='*50))
        self.stdout.write(f'Zonas creadas: {len(zonas_creadas)}')
        self.stdout.write(f'Estadísticas por zona: {EstadisticaZona.objects.count()}')
        self.stdout.write(f'Registros de historial: {HistorialPrecioZona.objects.count()}')
        
        # URLs de prueba
        self.stdout.write('\n' + self.style.SUCCESS('URLs para probar:'))
        self.stdout.write('  • Mapa de zonas: /cuadrantizacion/mapa/')
        self.stdout.write('  • Heatmap: /cuadrantizacion/heatmap/')
        self.stdout.write('  • API Zonas: /api/cuadrantizacion/zonas/')
        self.stdout.write('  • API Heatmap: /api/cuadrantizacion/heatmap-data/')
        
        self.stdout.write('\n' + self.style.SUCCESS('¡Listo para probar!'))

    def get_color_by_price(self, precio):
        """Determina color basado en precio."""
        if precio < 1000:
            return '#4CAF50'  # Verde
        elif precio < 2000:
            return '#FFC107'  # Amarillo
        else:
            return '#F44336'  # Rojo

    def get_border_color_by_price(self, precio):
        """Determina color de borde basado en precio."""
        if precio < 1000:
            return '#388E3C'  # Verde oscuro
        elif precio < 2000:
            return '#FFA000'  # Amarillo oscuro
        else:
            return '#D32F2F'  # Rojo oscuro

    def crear_estadisticas_zona(self, zona):
        """Crea estadísticas por tipo de propiedad para una zona."""
        tipos = ['casa', 'departamento', 'terreno', 'local', 'oficina']
        
        for tipo in tipos:
            # Precio ajustado por tipo
            factor_tipo = {
                'casa': 1.0,
                'departamento': 0.9,
                'terreno': 1.2,
                'local': 1.3,
                'oficina': 1.1
            }
            
            precio_tipo = zona.precio_promedio_m2 * Decimal(factor_tipo.get(tipo, 1.0))
            
            EstadisticaZona.objects.create(
                zona=zona,
                tipo_propiedad=tipo,
                cantidad_propiedades=random.randint(5, 20),
                precio_promedio_m2=precio_tipo,
                precio_mediano_m2=precio_tipo * Decimal(0.95),
                precio_minimo_m2=precio_tipo * Decimal(0.7),
                precio_maximo_m2=precio_tipo * Decimal(1.3),
                desviacion_estandar=precio_tipo * Decimal(0.1),
                habitaciones_promedio=Decimal(random.uniform(2.5, 4.5)),
                banos_promedio=Decimal(random.uniform(1.5, 3.5)),
                antiguedad_promedio=Decimal(random.uniform(5, 20)),
                metros_cuadrados_promedio=Decimal(random.uniform(80, 300))
            )

    def crear_historial_precios(self, zona):
        """Crea historial de precios para una zona."""
        fecha_base = timezone.now() - timezone.timedelta(days=365)
        
        for i in range(12):  # 12 meses de historial
            fecha = fecha_base + timezone.timedelta(days=30 * i)
            
            # Variación de precio (±10%)
            variacion = Decimal(random.uniform(0.9, 1.1))
            precio_historico = zona.precio_promedio_m2 * variacion
            
            HistorialPrecioZona.objects.create(
                zona=zona,
                fecha_registro=fecha.date(),
                precio_promedio_m2=precio_historico,
                cantidad_propiedades=random.randint(5, 25),
                desviacion_estandar=precio_historico * Decimal(0.15),
                fuente_datos='datos_prueba'
            )

    def asignar_propiedades_a_zonas(self, zonas):
        """Asigna propiedades existentes a zonas de prueba."""
        propiedades = PropiedadRaw.objects.all()[:100]  # Limitar a 100 propiedades
        
        for propiedad in propiedades:
            try:
                # Asignar a zona aleatoria
                zona = random.choice(zonas)
                
                # Calcular precio m² si hay datos
                precio_m2 = None
                if propiedad.precio_usd and propiedad.area_construida:
                    precio_m2 = propiedad.precio_usd / propiedad.area_construida
                
                # Crear valoración
                PropiedadValoracion.objects.create(
                    propiedad=propiedad,
                    zona=zona,
                    precio_m2=precio_m2,
                    precio_venta=propiedad.precio_usd,
                    metros_cuadrados=propiedad.area_construida,
                    es_comparable=random.choice([True, False]),
                    factor_ajuste=Decimal(random.uniform(0.8, 1.2)),
                    metodo_calculo='datos_prueba'
                )
                
            except Exception as e:
                # Continuar con siguiente propiedad si hay error
                continue
        
        self.stdout.write(f'  ✓ {PropiedadValoracion.objects.count()} valoraciones creadas')