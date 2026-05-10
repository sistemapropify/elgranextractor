import pandas as pd
from django.core.management.base import BaseCommand
from django.db import connections
from propifai.models import PropifaiProperty, PropertyType, PropertyStatus, User
from propifai.mapeo_ubicaciones import (
    obtener_nombre_departamento,
    obtener_nombre_provincia,
    obtener_nombre_distrito
)
from django.utils import timezone


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
        
        # Obtener tipos de propiedad y estados para referencia
        tipos_propiedad = {t.id: t.name for t in PropertyType.objects.all()}
        estados_propiedad = {s.id: s.name for s in PropertyStatus.objects.all()}
        
        # Preparar datos para el DataFrame
        data = []
        for prop in propiedades:
            # Obtener nombres completos de ubicación
            depto_nombre = obtener_nombre_departamento(prop.department)
            prov_nombre = obtener_nombre_provincia(prop.province)
            dist_nombre = obtener_nombre_distrito(prop.district)
            
            # Construir ubicación completa
            ubicacion_completa = f"{dist_nombre}, {prov_nombre}, {depto_nombre}"
            
            # Convertir fechas timezone-aware a naive
            created_at_naive = prop.created_at.replace(tzinfo=None) if prop.created_at else None
            updated_at_naive = prop.updated_at.replace(tzinfo=None) if prop.updated_at else None
            
            # Determinar tipo de propiedad basado en el modelo
            # El modelo PropifaiProperty no tiene un campo directo de tipo_propiedad,
            # pero podemos inferirlo de la lógica de negocio
            tipo_propiedad = "Propiedad"
            subtipo_propiedad = ""
            
            # Determinar condición (forma de pago)
            # Por defecto para propiedades propias de la inmobiliaria
            condicion = "venta"
            
            # Estado de disponibilidad
            estado_disponibilidad = prop.availability_status or ""
            
            # Datos de la propiedad
            row = {
                # === IDENTIFICACIÓN ===
                'ID': prop.id,
                'Código': prop.code,
                'Código Único': prop.codigo_unico_propiedad or '',
                'Título': prop.title or '',
                'Descripción': prop.description or '',
                
                # === TIPO DE PROPIEDAD ===
                'Tipo de Propiedad': tipo_propiedad,
                'Subtipo de Propiedad': subtipo_propiedad,
                
                # === PRECIO Y CONDICIÓN ===
                'Precio': prop.price or 0,
                'Moneda': 'PEN',  # Por defecto soles
                'Condición (Venta/Alquiler)': condicion,
                'Forma de Pago': condicion,  # Misma información
                'Mantenimiento': prop.maintenance_fee or 0,
                'Tiene Mantenimiento': 'Sí' if prop.has_maintenance else 'No',
                
                # === DIMENSIONES ===
                'Área Terreno (m²)': prop.land_area or 0,
                'Área Construida (m²)': prop.built_area or 0,
                'Frente (m)': prop.front_measure or 0,
                'Fondo (m)': prop.depth_measure or 0,
                
                # === ESPACIOS ===
                'Dormitorios': prop.bedrooms or 0,
                'Baños': prop.bathrooms or 0,
                'Medio Baño': prop.half_bathrooms or 0,
                'Cocheras': prop.garage_spaces or 0,
                'Pisos': prop.floors or 0,
                
                # === UBICACIÓN GEOGRÁFICA ===
                'Departamento ID': prop.department or '',
                'Departamento Nombre': depto_nombre,
                'Provincia ID': prop.province or '',
                'Provincia Nombre': prov_nombre,
                'Distrito ID': prop.district or '',
                'Distrito Nombre': dist_nombre,
                'Ubicación Completa': ubicacion_completa,
                'Dirección Real': prop.real_address or '',
                'Dirección Exacta': prop.exact_address or '',
                'Urbanización': prop.urbanization or '',
                'Coordenadas': prop.coordinates or '',
                'Latitud': prop.latitude,
                'Longitud': prop.longitude,
                
                # === CARACTERÍSTICAS ADICIONALES ===
                'Antigüedad (años)': prop.antiquity_years or 0,
                'Fecha Entrega': prop.delivery_date,
                'Proyecto': prop.project_name or '',
                'Ascensor': prop.ascensor or '',
                'Zonificación': prop.zoning or '',
                'Amenidades': prop.amenities or '',
                
                # === ESTADOS ===
                'Activa': 'Sí' if prop.is_active else 'No',
                'Listo para Venta': 'Sí' if prop.is_ready_for_sale else 'No',
                'Es Borrador': 'Sí' if prop.is_draft else 'No',
                'Es Proyecto': 'Sí' if prop.is_project else 'No',
                'Estado Disponibilidad': estado_disponibilidad,
                'Unidad Ubicación': prop.unit_location or '',
                
                # === FECHAS ===
                'Fecha Creación': created_at_naive,
                'Fecha Actualización': updated_at_naive,
                
                # === IMÁGENES ===
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
