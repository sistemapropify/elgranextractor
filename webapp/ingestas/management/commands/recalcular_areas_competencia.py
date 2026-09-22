"""Rellena área de terreno / área construida de las propiedades ya scrapeadas.

Los scrapers ahora guardan las dos superficies por separado, pero los registros
antiguos solo tienen ``area_m2`` y la superficie quedó dentro de la descripción
(«ÁREA DE TERRENO: 120 m2», «ÁREA CONSTRUIDA: 185 m2», «128 m2 totales»…).

Este comando relee esa descripción y **solo rellena los campos vacíos**: nunca
sobrescribe un dato que ya exista ni toca ``area_m2``.

Uso::

    python manage.py recalcular_areas_competencia --dry-run
    python manage.py recalcular_areas_competencia
    python manage.py recalcular_areas_competencia --fuente facebook_marketplace --limite 500
"""

from django.core.management.base import BaseCommand
from django.db.models import Q

from ingestas.models import PropiedadesCompetencia
from scrapi.areas import calcular_areas

TAMANO_LOTE = 500


class Command(BaseCommand):
    help = 'Rellena area_terreno/area_construida leyendo la descripcion de cada propiedad.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Solo informa cuántos registros se llenarían, sin guardar.')
        parser.add_argument('--fuente', default='',
                            help='Limita a un portal (remax, properati, urbania, facebook_marketplace…).')
        parser.add_argument('--limite', type=int, default=0,
                            help='Procesa como máximo N registros (0 = todos).')
        parser.add_argument('--lote', type=int, default=TAMANO_LOTE,
                            help=f'Tamaño de lote de escritura (por defecto {TAMANO_LOTE}).')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        limite = options['limite'] or 0
        lote = max(50, options['lote'])

        consulta = PropiedadesCompetencia.objects.filter(
            Q(area_terreno__isnull=True) | Q(area_construida__isnull=True)
        )
        if options['fuente']:
            consulta = consulta.filter(fuente=options['fuente'])

        pendientes = consulta.count()
        self.stdout.write(f'Registros con alguna superficie vacía: {pendientes}')

        revisados = 0
        con_terreno = 0
        con_construida = 0
        actualizados = 0
        # Paginación por ID (no se usa .iterator(): el cursor del servidor de SQL
        # Server no permite escribir en la misma sesión).
        ultimo_id = 0

        while True:
            lote_actual = list(
                consulta.filter(id__gt=ultimo_id).order_by('id')[:lote]
            )
            if not lote_actual:
                break
            ultimo_id = lote_actual[-1].id
            a_guardar = []
            for propiedad in lote_actual:
                revisados += 1
                # Los scrapers guardan la evidencia de la superficie en
                # ``datos_crudos`` (p. ej. ``Caracteristicas`` de Urbania o
                # ``Area Terreno``/``Area Construida`` de Remax), así que ese
                # respaldo se revisa además del título y la descripción.
                crudos = propiedad.datos_crudos if isinstance(propiedad.datos_crudos, dict) else {}
                datos = calcular_areas({
                    **crudos,
                    'Titulo': propiedad.titulo,
                    'Descripcion': propiedad.descripcion,
                })
                cambio = False
                if propiedad.area_terreno is None and datos['area_terreno']:
                    propiedad.area_terreno = datos['area_terreno']
                    con_terreno += 1
                    cambio = True
                if propiedad.area_construida is None and datos['area_construida']:
                    propiedad.area_construida = datos['area_construida']
                    con_construida += 1
                    cambio = True
                if cambio and not dry_run:
                    a_guardar.append(propiedad)
                if limite and revisados >= limite:
                    break
            if a_guardar:
                PropiedadesCompetencia.objects.bulk_update(
                    a_guardar, ['area_terreno', 'area_construida'],
                )
                actualizados += len(a_guardar)
            if limite and revisados >= limite:
                break

        self.stdout.write(f'Revisados: {revisados} · filas actualizadas: {actualizados}')
        self.stdout.write(self.style.SUCCESS(
            f'Con área de terreno: {con_terreno} · con área construida: {con_construida}'
        ))
        if dry_run:
            self.stdout.write(self.style.WARNING('dry-run: no se guardó ningún cambio.'))
