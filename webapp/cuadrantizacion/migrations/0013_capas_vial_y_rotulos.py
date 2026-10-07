"""
Registra la estructura vial y los rótulos de códigos como capas aparte.

La red vial son las líneas negras del plano, cada una con el grosor de su
nivel (Interregionales, 2.º a 5.º nivel y ferrocarril). Los rótulos son los
códigos de zona impresos dentro de los polígonos (RDM-2, CE, ZRE-CH, ...).
Ambas capas quedan con su propio control de transparencia y visibilidad.
"""

from django.db import migrations

CAPAS = [
    {
        'nombre': 'Estructura vial PDM 2016-2025',
        'tipo': 'lineas',
        'geojson_url': 'cuadrantizacion/capas/estructura_vial_pdm.geojson',
        'descripcion': (
            'Avenidas y calles del plano según su nivel (Interregionales, '
            '2.º a 5.º nivel) y ferrocarril.'
        ),
        'opacidad': 0.85,
        'color_borde': '#000000',
        'grosor_borde': 1.0,
        'escala_ancho': 0.8,
        'zoom_minimo': 0,
        'orden': 10,
    },
    {
        'nombre': 'Códigos de zona',
        'tipo': 'etiquetas',
        'geojson_url': 'cuadrantizacion/capas/zonificacion_pdm_codigos.geojson',
        'descripcion': 'Códigos de zonificación impresos en el plano (RDM-2, CE, ZRE-CH, ...).',
        'opacidad': 1.0,
        'color_borde': '#111111',
        'grosor_borde': 1.0,
        'tamano_rotulo': 10.0,
        'zoom_minimo': 14,
        'orden': 20,
    },
]


def crear_capas(apps, schema_editor):
    CapaVectorialMapa = apps.get_model('cuadrantizacion', 'CapaVectorialMapa')
    for capa in CAPAS:
        datos = dict(capa)
        nombre = datos.pop('nombre')
        CapaVectorialMapa.objects.update_or_create(
            nombre=nombre,
            defaults={**datos, 'visible': True, 'activo': True},
        )


def borrar_capas(apps, schema_editor):
    CapaVectorialMapa = apps.get_model('cuadrantizacion', 'CapaVectorialMapa')
    CapaVectorialMapa.objects.filter(
        nombre__in=[capa['nombre'] for capa in CAPAS]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('cuadrantizacion', '0012_capavectorialmapa_escala_ancho_and_more'),
    ]

    operations = [
        migrations.RunPython(crear_capas, borrar_capas),
    ]
