"""
Migración: Agregar campo texto_hash al modelo Requerimiento.

Hash SHA256 del texto normalizado para detección rápida de duplicados.
La columna ya existe en SQL Server como NOT NULL, se agrega con default=''
para compatibilidad.
"""

from django.db import migrations, models


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
                default='',
                verbose_name='Hash SHA256 del texto',
                help_text='Hash SHA256 del texto normalizado para detección rápida de duplicados',
                db_index=True,
            ),
        ),
    ]
