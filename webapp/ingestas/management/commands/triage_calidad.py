"""Triaje con IA de las alertas de calidad.

Recorre las propiedades marcadas con alertas y deja el veredicto del agente en
``RevisionIAAlerta``. Es **incremental**: al re-ejecutarse salta las que ya tienen
veredicto, asi que despues de la primera corrida solo procesa lo nuevo.
"""
from __future__ import annotations

import time

from django.core.management.base import BaseCommand

from ingestas.calidad_ia import analizar, propiedades_con_alertas
from ingestas.models import RevisionIAAlerta


class Command(BaseCommand):
    help = 'Clasifica con IA las alertas de calidad (real / ruido / dudoso)'

    def add_arguments(self, parser):
        parser.add_argument('--limite', type=int, default=0,
                            help='Procesar a lo sumo N propiedades (0 = todas)')
        parser.add_argument('--repetir', action='store_true',
                            help='Reanalizar tambien las que ya tienen veredicto')
        parser.add_argument('--lote', type=int, default=25,
                            help='Guardar cada N propiedades (para poder cortar sin perder)')

    def handle(self, *args, **opciones):
        limite = opciones['limite']
        pendientes = propiedades_con_alertas(sin_veredicto=not opciones['repetir'])
        if limite:
            pendientes = pendientes[:limite]

        total = len(pendientes)
        if not total:
            self.stdout.write(self.style.SUCCESS('No hay propiedades pendientes de triaje.'))
            return

        self.stdout.write('Triaje de %d propiedades (lote de %d)...' % (total, opciones['lote']))
        conteo, t0 = {}, time.time()

        for n, propiedad in enumerate(pendientes, 1):
            resultado = analizar(dict(propiedad))
            conteo[resultado['veredicto']] = conteo.get(resultado['veredicto'], 0) + 1

            RevisionIAAlerta.objects.update_or_create(
                propiedad_id=propiedad['id'],
                defaults={
                    'veredicto': resultado['veredicto'],
                    'motivo': resultado['motivo'],
                    'correccion': resultado['correccion'],
                    'alertas_revisadas': list(propiedad.get('alertas') or []),
                    'confianza': resultado['confianza'],
                    'modelo': resultado.get('modelo', '') or 'deepseek',
                    'respuesta_cruda': {'texto': resultado.get('respuesta_cruda', ''),
                                        'intentos': resultado.get('intentos')},
                },
            )

            if n % opciones['lote'] == 0 or n == total:
                transcurrido = time.time() - t0
                self.stdout.write('  %d/%d  %s  (%.1f s/propiedad)' % (
                    n, total, conteo, transcurrido / n))

        self.stdout.write(self.style.SUCCESS(
            'Listo: %d procesadas en %.0f s. %s' % (total, time.time() - t0, conteo)))
