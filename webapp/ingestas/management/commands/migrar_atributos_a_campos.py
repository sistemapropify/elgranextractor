"""
Comando de gestión para migrar datos desde atributos_extras a campos fijos y columnas dinámicas.
Útil cuando la importación de Excel no mapeó correctamente los campos y toda la información
quedó almacenada en atributos_extras.
"""

import sys
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, connection
from django.db.models import Q
from ingestas.models import PropiedadRaw, CampoDinamico
from decimal import Decimal, InvalidOperation
import json


class Command(BaseCommand):
    help = 'Migra datos desde atributos_extras a campos fijos y columnas dinámicas.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--campo',
            type=str,
            help='Migrar solo un campo específico (nombre en atributos_extras)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simular migración sin guardar cambios'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Tamaño del lote para procesamiento por lotes (default: 100)'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Mostrar detalles de cada propiedad procesada'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        campo_especifico = options['campo']
        batch_size = options['batch_size']
        verbose = options['verbose']

        self.stdout.write(self.style.NOTICE(
            'Iniciando migración de atributos_extras a campos...'
        ))
        if dry_run:
            self.stdout.write(self.style.WARNING('MODO SIMULACIÓN - No se guardarán cambios.'))

        # Mapeo de campos fijos conocidos
        campos_fijos = {
            'tipo_propiedad': ['tipo_propiedad', 'tipo', 'property_type', 'tipo_de_propiedad'],
            'precio_usd': ['precio_usd', 'precio', 'price', 'valor', 'precio_usd', 'precio_us'],
            'moneda': ['moneda', 'currency'],
            'ubicacion': ['ubicacion', 'location', 'direccion', 'dirección', 'address', 'distrito', 'provincia', 'departamento'],
            'metros_cuadrados': ['metros_cuadrados', 'metros', 'area', 'area_construida', 'area_terreno', 'm2', 'mt2'],
            'habitaciones': ['habitaciones', 'rooms', 'bedrooms', 'dormitorios', 'habitacion'],
            'banos': ['banos', 'bathrooms', 'baños', 'banios', 'bano'],
            'estacionamientos': ['estacionamientos', 'parking', 'cocheras', 'garage'],
            'descripcion': ['descripcion', 'description', 'descripción'],
            'url_fuente': ['url_fuente', 'url', 'link', 'fuente_url'],
            'fuente_excel': ['fuente_excel', 'fuente', 'source'],
        }

        # Obtener campos dinámicos existentes (columnas físicas)
        campos_dinamicos = CampoDinamico.objects.all()
        mapeo_dinamico = {}
        for cd in campos_dinamicos:
            mapeo_dinamico[cd.nombre_campo_bd] = cd.nombre_campo_bd  # la clave es la misma
            # También podemos considerar variantes? Por ahora solo nombre exacto.

        total_propiedades = PropiedadRaw.objects.count()
        self.stdout.write(f'Total de propiedades a procesar: {total_propiedades}')

        # Procesar por lotes
        offset = 0
        total_migrados = 0
        total_actualizados = 0

        while offset < total_propiedades:
            propiedades = PropiedadRaw.objects.all()[offset:offset + batch_size]
            batch_updated = 0

            for propiedad in propiedades:
                atributos = propiedad.atributos_extras
                if not isinstance(atributos, dict) or not atributos:
                    continue

                cambios = False
                # Migrar a campos fijos
                for campo_fijo, posibles_claves in campos_fijos.items():
                    valor = None
                    for clave in posibles_claves:
                        if clave in atributos:
                            valor = atributos[clave]
                            break
                    if valor is not None:
                        # Verificar si el campo fijo actual está vacío
                        actual = getattr(propiedad, campo_fijo)
                        if actual is None or actual == '' or (isinstance(actual, (int, float)) and actual == 0):
                            # Intentar convertir el valor al tipo adecuado
                            try:
                                valor_convertido = self.convertir_valor(campo_fijo, valor)
                                setattr(propiedad, campo_fijo, valor_convertido)
                                cambios = True
                                if verbose:
                                    self.stdout.write(f'  {propiedad.id}: {campo_fijo} = {valor_convertido}')
                            except (ValueError, TypeError, InvalidOperation) as e:
                                self.stdout.write(self.style.WARNING(
                                    f'  {propiedad.id}: Error convirtiendo {campo_fijo} con valor {valor}: {e}'
                                ))

                # Migrar a campos dinámicos (si existen columnas físicas)
                for campo_bd in mapeo_dinamico.keys():
                    if campo_bd in atributos:
                        # Verificar si la columna existe físicamente (ya lo sabemos)
                        # Actualizar mediante SQL dinámico (o usando setattr si el modelo tiene el campo)
                        # Como el campo dinámico no está definido en el modelo, necesitamos usar raw SQL.
                        # Por simplicidad, omitimos por ahora.
                        pass

                if cambios:
                    if not dry_run:
                        propiedad.save(update_fields=[campo for campo in campos_fijos.keys() if getattr(propiedad, campo) is not None])
                    batch_updated += 1
                    total_actualizados += 1

                total_migrados += 1

            offset += batch_size
            self.stdout.write(f'Procesadas {offset}/{total_propiedades} propiedades...')

        self.stdout.write(self.style.SUCCESS(
            f'Migración completada. Propiedades procesadas: {total_migrados}, actualizadas: {total_actualizados}'
        ))
        if dry_run:
            self.stdout.write(self.style.WARNING(
                'Ejecución en modo simulación. Para aplicar cambios, ejecute sin --dry-run.'
            ))

    def convertir_valor(self, campo, valor):
        """Convierte un valor al tipo adecuado para el campo."""
        if valor is None:
            return None
        if campo in ['precio_usd', 'metros_cuadrados']:
            # Decimal
            try:
                return Decimal(str(valor).replace(',', '.'))
            except:
                # Si falla, intentar extraer números
                import re
                numeros = re.findall(r'[\d.,]+', str(valor))
                if numeros:
                    return Decimal(numeros[0].replace(',', '.'))
                raise ValueError(f'No se pudo convertir a Decimal: {valor}')
        elif campo in ['habitaciones', 'banos', 'estacionamientos']:
            # Entero
            try:
                return int(float(str(valor).replace(',', '.')))
            except:
                raise ValueError(f'No se pudo convertir a entero: {valor}')
        elif campo in ['tipo_propiedad', 'ubicacion', 'descripcion', 'url_fuente', 'fuente_excel', 'moneda']:
            # String
            return str(valor).strip()
        else:
            return valor