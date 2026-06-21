"""
Migración: Agregar opción Anticresis a CondicionChoices

Cambios:
- Agregar 'anticresis' como opción válida en el campo condicion
  del modelo Requerimiento (solo afecta la validación a nivel Django,
  la BD ya acepta cualquier string)
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('requerimientos', '0006_requerimiento_verificado_alter_requerimiento_fuente'),
    ]

    operations = [
        migrations.AlterField(
            model_name='requerimiento',
            name='condicion',
            field=models.CharField(
                blank=True,
                choices=[
                    ('compra', 'Compra'),
                    ('alquiler', 'Alquiler'),
                    ('anticresis', 'Anticresis'),
                    ('ambos', 'Compra y Alquiler'),
                    ('no_especificado', 'No Especificado'),
                ],
                db_index=True,
                max_length=50,
                verbose_name='Condición',
            ),
        ),
    ]
