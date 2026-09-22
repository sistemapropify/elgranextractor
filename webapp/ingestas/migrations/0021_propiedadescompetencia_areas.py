from django.db import migrations, models


class Migration(migrations.Migration):
    """Superficies por separado en la competencia: terreno y construcción (m²)."""

    dependencies = [
        ('ingestas', '0020_propiedadescompetencia_precision_ubicacion'),
    ]

    operations = [
        migrations.AddField(
            model_name='propiedadescompetencia',
            name='area_terreno',
            field=models.DecimalField(
                blank=True,
                db_column='area_terreno_m2',
                decimal_places=2,
                max_digits=10,
                null=True,
                verbose_name='Área de terreno (m²)',
            ),
        ),
        migrations.AddField(
            model_name='propiedadescompetencia',
            name='area_construida',
            field=models.DecimalField(
                blank=True,
                db_column='area_construida_m2',
                decimal_places=2,
                max_digits=10,
                null=True,
                verbose_name='Área construida (m²)',
            ),
        ),
    ]
