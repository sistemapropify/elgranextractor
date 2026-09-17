from django.db import migrations


def migrar_condicion(apps, schema_editor):
    """
    Antes de eliminar tipo_original, deriva la condicion final usando ambos campos.

    - tipo_original BASURA / PROPIEDAD VENTA / PROPIEDAD ALQUILER -> basura
    - tipo_original ALQUILER -> alquiler
    - tipo_original COMPRA -> compra
    - resto: conservar condicion actual.
    Luego: ambos -> compra.
    """
    Requerimiento = apps.get_model('requerimientos', 'Requerimiento')

    for req in Requerimiento.objects.all().iterator():
        to = (req.tipo_original or '').upper()
        nuevo = None
        if 'BASURA' in to or 'PROPIEDAD VENTA' in to or 'PROPIEDAD ALQUILER' in to:
            nuevo = 'basura'
        elif 'ALQUILER' in to:
            nuevo = 'alquiler'
        elif 'COMPRA' in to:
            nuevo = 'compra'
        if nuevo:
            req.condicion = nuevo
            req.save(update_fields=['condicion'])

    Requerimiento.objects.filter(condicion='ambos').update(condicion='compra')


class Migration(migrations.Migration):

    dependencies = [
        ('requerimientos', '0014_texto_hash_unique_together'),
    ]

    operations = [
        migrations.RunPython(migrar_condicion, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='requerimiento',
            name='tipo_original',
        ),
    ]
