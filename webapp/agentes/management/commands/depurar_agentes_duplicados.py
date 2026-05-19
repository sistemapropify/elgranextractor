"""
Comando de management: depurar_agentes_duplicados

Detecta y elimina agentes duplicados en la tabla Agentes basándose en
los dígitos del teléfono (ignorando formato +51, espacios, guiones).

Uso:
    python manage.py depurar_agentes_duplicados          # Modo dry-run (solo muestra)
    python manage.py depurar_agentes_duplicados --delete  # Elimina duplicados
    python manage.py depurar_agentes_duplicados --delete --keep-first  # Elimina duplicados (conserva el primero)
    python manage.py depurar_agentes_duplicados --delete --keep-last   # Elimina duplicados (conserva el último)
"""
import re
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from agentes.models import Agente


def _extraer_digitos(valor):
    """Extrae solo dígitos de un string."""
    return re.sub(r'\D', '', valor)


class Command(BaseCommand):
    help = 'Detecta y elimina agentes duplicados por teléfono (ignorando formato)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete',
            action='store_true',
            help='Ejecuta la eliminación (sin este flag solo muestra los duplicados)',
        )
        parser.add_argument(
            '--keep-first',
            action='store_true',
            help='Conserva el registro más antiguo (por ID) al eliminar duplicados',
        )
        parser.add_argument(
            '--keep-last',
            action='store_true',
            help='Conserva el registro más reciente (por ID) al eliminar duplicados',
        )

    def handle(self, *args, **options):
        ejecutar = options['delete']
        keep_first = options['keep_first']
        keep_last = options['keep_last']

        if keep_first and keep_last:
            raise CommandError('Usa solo --keep-first o --keep-last, no ambos.')

        # Agrupar agentes por dígitos del teléfono
        grupos = {}  # {digitos: [lista_de_agentes]}
        for agente in Agente.objects.all().order_by('id'):
            digitos = _extraer_digitos(agente.telefono)
            if not digitos:
                continue
            if digitos not in grupos:
                grupos[digitos] = []
            grupos[digitos].append(agente)

        # Filtrar solo grupos con duplicados
        duplicados = {d: agents for d, agents in grupos.items() if len(agents) > 1}

        if not duplicados:
            self.stdout.write(self.style.SUCCESS('[OK] No se encontraron agentes duplicados.'))
            return

        total_duplicados = sum(len(agents) - 1 for agents in duplicados.values())
        total_grupos = len(duplicados)

        self.stdout.write(self.style.WARNING(f'[!] Se encontraron {total_duplicados} agente(s) duplicado(s) en {total_grupos} grupo(s):'))
        self.stdout.write('')

        for digitos, agents in sorted(duplicados.items()):
            self.stdout.write(f'  Teléfono (dígitos): {digitos}')
            for i, a in enumerate(agents):
                marca = ' [CONSERVAR]' if (keep_first and i == 0) or (keep_last and i == len(agents) - 1) else ''
                self.stdout.write(f'    [{a.id}] {a.nombre_completo} — tel: {a.telefono}{marca}')
            self.stdout.write('')

        if not ejecutar:
            self.stdout.write(
                self.style.WARNING(
                    'Modo dry-run: no se eliminó nada. '
                    'Ejecuta con --delete para eliminar los duplicados.'
                )
            )
            return

        # ── Ejecutar eliminación ──────────────────────────
        if not keep_first and not keep_last:
            keep_first = True  # Default: conservar el primero

        eliminados = 0
        with transaction.atomic():
            for digitos, agents in duplicados.items():
                if keep_first:
                    conservar = agents[0]  # El primero (menor ID)
                    a_eliminar = agents[1:]
                else:
                    conservar = agents[-1]  # El último (mayor ID)
                    a_eliminar = agents[:-1]

                for agente in a_eliminar:
                    self.stdout.write(f'  Eliminando [{agente.id}] {agente.nombre_completo} — {agente.telefono}')
                    agente.delete()
                    eliminados += 1

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'[OK] Eliminados {eliminados} agente(s) duplicado(s).'))
        self.stdout.write(self.style.SUCCESS(f'[OK] Se conservo 1 agente por grupo de telefono.'))
