# -*- coding: utf-8 -*-
from django.db import migrations, models
import hashlib


def calcular_texto_hash(apps, schema_editor):
    """Calcula texto_hash para todos los Requerimiento existentes."""
    Requerimiento = apps.get_model('requerimientos', 'Requerimiento')
    db_alias = schema_editor.connection.alias
    for req in Requerimiento.objects.using(db_alias).all():
        texto = req.requerimiento or ''
        req.texto_hash = hashlib.sha256(texto.encode('utf-8')).hexdigest()
        req.save(update_fields=['texto_hash'])


class Migration(migrations.Migration):

    dependencies = [
        ('requerimientos', '0012_compartido_condicion'),
    ]

    operations = [
        migrations.AddField(
            model_name='requerimiento',
            name='texto_hash',
            field=models.CharField(
                max_length=64,
                blank=True,
                editable=False,
                verbose_name='Hash SHA256 del texto',
                help_text='Hash del campo requerimiento para unique constraint (SQL Server no permite índices en TEXT/NVARCHAR(MAX))',
            ),
        ),
        migrations.RunPython(calcular_texto_hash, reverse_code=migrations.RunPython.noop),
    ]
