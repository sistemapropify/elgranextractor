from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('requerimientos', '0010_config_calidad'),
    ]

    operations = [
        migrations.AddField(
            model_name='requerimiento',
            name='quality_score',
            field=models.DecimalField(
                max_digits=5, decimal_places=1,
                null=True, blank=True,
                verbose_name='Score de calidad',
                help_text='Score total de calidad (0-100). Se recalcula automáticamente.',
            ),
        ),
        migrations.AddField(
            model_name='requerimiento',
            name='quality_nivel',
            field=models.CharField(
                max_length=20,
                null=True, blank=True,
                verbose_name='Nivel de calidad',
                help_text='Excelente/Bueno/Regular/Malo',
            ),
        ),
        migrations.AddField(
            model_name='requerimiento',
            name='quality_detalle',
            field=models.JSONField(
                null=True, blank=True,
                verbose_name='Detalle de calidad',
                help_text='Desglose de dimensiones: completitud, especificidad, presupuesto, antigüedad',
            ),
        ),
        migrations.AddField(
            model_name='requerimiento',
            name='quality_actualizado_en',
            field=models.DateTimeField(
                null=True, blank=True,
                verbose_name='Quality Score actualizado en',
            ),
        ),
    ]
