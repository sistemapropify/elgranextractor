import pandas as pd
from django.core.management.base import BaseCommand
from django.db import connections
from propifai.models import PropifaiProperty
from propifai.mapeo_ubicaciones import (
    obtener_nombre_departamento,
    obtener_nombre_provincia,
    obtener_nombre_distrito
)


class Command(BaseCommand):
    help = 'Genera un archivo Excel con las propiedades de la tabla propifai y sus relaciones'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default='propiedades_propifai.xlsx',
            help='Nombre del archivo de salida Excel'
        )

    def handle(self, *args, **options):
        output_file = options['output']
        
        # Obtener todas las propiedades
        propiedades = PropifaiProperty.objects.all()
        
        # Preparar datos para el DataFrame
        data = []
        for prop in propiedades:
            # Obtener nombres completos de ubicación
            depto_nombre = obtener_nombre_departamento(prop.department)
            prov_nombre = obtener_nombre_provincia(prop.province)
            dist_nombre = obtener_nombre_distrito(prop.district)
            
            # Construir ubicación completa
            ubicacion_completa = f"{dist_nombre}, {prov_nombre}, {depto_nombre}"
            
            # Datos de la propiedad
            row = {
                'ID': prop.id,
                'Código': prop.code,
                'Título': prop.title or '',
                'Descripción': prop.description or '',
                'Precio': prop.price or 0,
                'Mantenimiento': prop.maintenance_fee or 0,
                'Área Terreno': prop.land_area or 0,
                'Área Construida': prop.built_area or 0,
                'Dormitorios': prop.bedrooms or 0,
                'Baños': prop.bathrooms or 0,
                'Cocheras': prop.garage_spaces or 0,
                'Pisos': prop.floors or 0,
                'Departamento ID': prop.department or '',
                'Departamento Nombre': depto_nombre,
                'Provincia ID': prop.province or '',
                'Provincia Nombre': prov_nombre,
                'Distrito ID': prop.district or '',
                'Distrito Nombre': dist_nombre,
                'Ubicación Completa': ubicacion_completa,
                'Dirección Real': prop.real_address or '',
                'Dirección Exacta': prop.exact_address or '',
                'Coordenadas': prop.coordinates or '',
                'Latitud': prop.latitude,
                'Longitud': prop.longitude,
                'Fecha Creación': prop.created_at,
                'Fecha Actualización': prop.updated_at,
                'Activa': prop.is_active,
                'Listo para Venta': prop.is_ready_for_sale,
                'Es Proyecto': prop.is_project,
                'Estado Disponibilidad': prop.availability_status or '',
                'Unidad Ubicación': prop.unit_location or '',
                'Ascensor': prop.ascensor or '',
                'Tipo de Propiedad': 'Propiedad',  # Este campo se obtendría de una relación real si existiera
                'Subtipo de Propiedad': '',  # No está en el modelo propifai, pero podemos agregarlo desde ingestas
                'Condición': 'Venta',  # Por defecto para propiedades propias
                'Antigüedad (años)': prop.antiquity_years or 0,
                'Fecha Entrega': prop.delivery_date,
                'Proyecto': prop.project_name or '',
                'Urbanización': prop.urbanization or '',
                'Zonificación': prop.zoning or '',
                'Amenidades': prop.amenities or '',
                'URL Imagen': prop.imagen_url or '',
            }
            data.append(row)
        
        # Crear DataFrame
        df = pd.DataFrame(data)
        
        # Guardar en Excel
        df.to_excel(output_file, index=False)
        
        self.stdout.write(
            self.style.SUCCESS(f'Archivo Excel generado exitosamente: {output_file}')
        )
        self.stdout.write(
            self.style.SUCCESS(f'Total de propiedades exportadas: {len(df)}')
        )
