# -*- coding: utf-8 -*-
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('requerimientos', '0013_add_texto_hash'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='requerimiento',
            unique_together={('texto_hash', 'fecha', 'hora', 'fuente')},
        ),
    ]
