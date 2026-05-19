# -*- coding: utf-8 -*-
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('requerimientos', '0011_quality_score_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='requerimiento',
            name='condicion',
            field=models.CharField(choices=[('compra', 'Compra'), ('alquiler', 'Alquiler'), ('anticresis', 'Anticresis'), ('ambos', 'Compra y Alquiler'), ('compartido', 'Compartido'), ('no_especificado', 'No Especificado')], max_length=50, verbose_name='Condición'),
        ),
    ]
