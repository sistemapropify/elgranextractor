"""
Registra la capa vectorial de zonificación del PDM.

Los polígonos se extrajeron del propio PDF (que los guarda como vectores, no
como imagen), se georreferenciaron desde la grilla UTM del plano y se
guardaron como GeoJSON. Con eso los límites entre zonas son líneas exactas a
cualquier nivel de zoom, y la clasificación de un marcador pasa a ser
geométrica: el punto cae dentro de un polígono o no.
"""

from django.db import migrations

NOMBRE = 'Zonificación PDM Arequipa 2016-2025'
GEOJSON = 'cuadrantizacion/capas/zonificacion_pdm_poligonos.geojson'


def crear_capa(apps, schema_editor):
    CapaVectorialMapa = apps.get_model('cuadrantizacion', 'CapaVectorialMapa')
    CapaVectorialMapa.objects.get_or_create(
        nombre=NOMBRE,
        defaults={
            'descripcion': (
                'Plan de Desarrollo Metropolitano de Arequipa 2016-2025 — '
                'Zonificación en polígonos georreferenciados (WGS84).'
            ),
            'geojson_url': GEOJSON,
            'opacidad': 0.65,
            'color_borde': '#000000',
            'grosor_borde': 0.4,
            'visible': True,
            'activo': True,
            'orden': 0,
        },
    )
    # La capa raster queda desactivada (no borrada): los polígonos la
    # reemplazan y así el mapa no dibuja las dos cosas a la vez. Se puede
    # reactivar desde el admin si hiciera falta volver a la imagen.
    CapaRasterMapa = apps.get_model('cuadrantizacion', 'CapaRasterMapa')
    CapaRasterMapa.objects.update(activo=False, visible=False)


def borrar_capa(apps, schema_editor):
    CapaVectorialMapa = apps.get_model('cuadrantizacion', 'CapaVectorialMapa')
    CapaVectorialMapa.objects.filter(nombre=NOMBRE).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('cuadrantizacion', '0010_capavectorialmapa'),
    ]

    operations = [
        migrations.RunPython(crear_capa, borrar_capa),
    ]
