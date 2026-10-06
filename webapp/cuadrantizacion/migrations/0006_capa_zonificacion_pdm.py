"""
Registra la capa de Zonificación del PDM de Arequipa 2016-2025.

La georreferencia sale de la grilla UTM impresa en el propio plano
(WGS 1984 / UTM zona 19S, meridiano central -69, factor de escala 0.9996).
El encaje se validó contra el aeropuerto Rodríguez Ballón y la Plaza de
Armas: el error estimado es menor a 25 m en un área de 24 x 36 km.
"""

from django.db import migrations

NOMBRE = 'Zonificación PDM Arequipa 2016-2025'

ESQUINAS = {
    'tl': [-71.67365824, -16.24950631],
    'tr': [-71.44978567, -16.25221402],
    'br': [-71.45391668, -16.58168000],
    'bl': [-71.67816571, -16.57891436],
}

IMAGEN = 'cuadrantizacion/capas/zonificacion_pdm_2016_2025.png'


def crear_capa(apps, schema_editor):
    CapaRasterMapa = apps.get_model('cuadrantizacion', 'CapaRasterMapa')
    CapaRasterMapa.objects.get_or_create(
        nombre=NOMBRE,
        defaults={
            'descripcion': (
                'Plan de Desarrollo Metropolitano de Arequipa 2016-2025 — '
                'Zonificación. Georreferenciado (WGS84 / UTM 19S).'
            ),
            'imagen_url': IMAGEN,
            'esquinas': ESQUINAS,
            'opacidad': 0.65,
            'rotacion': 0.0,
            'escala': 1.0,
            'offset_x': 0.0,
            'offset_y': 0.0,
            'visible': True,
            'activo': True,
            'bloqueado': False,
            'orden': 0,
        },
    )


def eliminar_capa(apps, schema_editor):
    CapaRasterMapa = apps.get_model('cuadrantizacion', 'CapaRasterMapa')
    CapaRasterMapa.objects.filter(nombre=NOMBRE).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('cuadrantizacion', '0005_caparastermapa'),
    ]

    operations = [
        migrations.RunPython(crear_capa, eliminar_capa),
    ]
