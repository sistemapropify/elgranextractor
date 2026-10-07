"""
Agranda los rótulos de códigos y los deja por encima de los rellenos.

Con el tamaño anterior (10 px) los códigos se leían mal sobre los colores de
las zonas. Ahora arrancan en 13 px y crecen con el zoom.
"""

from django.db import migrations


def agrandar(apps, schema_editor):
    CapaVectorialMapa = apps.get_model('cuadrantizacion', 'CapaVectorialMapa')
    CapaVectorialMapa.objects.filter(tipo='etiquetas').update(
        tamano_rotulo=13.0,
        color_borde='#000000',
        activo=True,
        visible=True,
    )


def revertir(apps, schema_editor):
    CapaVectorialMapa = apps.get_model('cuadrantizacion', 'CapaVectorialMapa')
    CapaVectorialMapa.objects.filter(tipo='etiquetas').update(tamano_rotulo=10.0)


class Migration(migrations.Migration):

    dependencies = [
        ('cuadrantizacion', '0013_capas_vial_y_rotulos'),
    ]

    operations = [
        migrations.RunPython(agrandar, revertir),
    ]
