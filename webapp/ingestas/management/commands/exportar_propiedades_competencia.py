"""Exporta la tabla de propiedades scrapeadas (propiedades_competencia) a Excel.

Uso:
    python manage.py exportar_propiedades_competencia
    python manage.py exportar_propiedades_competencia --salida D:/reportes/propiedades.xlsx
    python manage.py exportar_propiedades_competencia --fuente properati --estado activa
    python manage.py exportar_propiedades_competencia --incluir-crudos

Es la misma exportación que ofrece el botón "Exportar Excel" del dashboard de
scraping, pero guardada como archivo en disco.
"""
import os
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from ingestas.scraping_export import construir_libro, filtrar_propiedades


class Command(BaseCommand):
    help = (
        'Exporta la tabla propiedades_competencia (propiedades scrapeadas de '
        'Remax, Adondevivir, Properati, Urbania y Facebook Marketplace) a Excel.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--salida', '-o', default='',
            help='Ruta del archivo .xlsx de salida (por defecto propiedades_competencia_<fecha>.xlsx)',
        )
        parser.add_argument('--fuente', default='', help='Filtrar por portal')
        parser.add_argument('--distrito', default='', help='Filtrar por distrito (coincidencia parcial)')
        parser.add_argument('--tipo', default='', help='Filtrar por tipo de inmueble')
        parser.add_argument('--estado', default='', help='Filtrar por estado de publicación')
        parser.add_argument('--limite', type=int, default=0, help='Máximo de filas a exportar (0 = todas)')
        parser.add_argument(
            '--incluir-crudos', action='store_true',
            help='Añade una hoja con el JSON crudo (datos_crudos) de cada propiedad',
        )

    def handle(self, *args, **options):
        limite = max(0, options['limite'] or 0)
        propiedades = filtrar_propiedades({
            'fuente': options['fuente'] or None,
            'distrito': options['distrito'] or None,
            'tipo': options['tipo'] or None,
            'estado': options['estado'] or None,
        })
        if limite:
            propiedades = propiedades[:limite]

        try:
            libro, total = construir_libro(
                propiedades, incluir_crudos=options['incluir_crudos'],
            )
        except ImportError as exc:
            raise CommandError(
                'openpyxl no está instalado. Ejecute: pip install openpyxl'
            ) from exc

        salida = options['salida'] or f'propiedades_competencia_{datetime.now():%Y%m%d_%H%M}.xlsx'
        ruta = os.path.abspath(salida)
        directorio = os.path.dirname(ruta)
        if directorio:
            os.makedirs(directorio, exist_ok=True)

        libro.save(ruta)
        self.stdout.write(self.style.SUCCESS(f'Exportadas {total} propiedades a {ruta}'))
