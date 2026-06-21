"""
Migración: Agregar campos urbanización y zona a Requerimiento

Cambios:
- Agregar campo urbanizacion (CharField, max_length=200, blank=True)
- Agregar campo zona (CharField, max_length=500, blank=True)
  para calles específicas, nombres de edificios, referencias separadas por coma
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('requerimientos', '0007_add_anticresis_choice'),
    ]

    operations = [
        migrations.AddField(
            model_name='requerimiento',
            name='urbanizacion',
            field=models.CharField(
                blank=True,
                max_length=200,
                verbose_name='Urbanización',
                help_text='Nombre de la urbanización o residencial',
            ),
        ),
        migrations.AddField(
            model_name='requerimiento',
            name='zona',
            field=models.CharField(
                blank=True,
                max_length=500,
                verbose_name='Zona / Calles / Edificio',
                help_text='Calles específicas, nombres de edificios o referencias, separados por coma',
            ),
        ),
    ]
