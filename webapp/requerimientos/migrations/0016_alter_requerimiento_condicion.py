from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Actualiza las choices de `condicion` en el estado de migraciones:
    se agrega 'basura' y se quita 'ambos'.
    (El cambio de choices no altera el esquema físico de la columna.)
    """

    dependencies = [
        ('requerimientos', '0015_remove_tipo_original'),
    ]

    operations = [
        migrations.AlterField(
            model_name='requerimiento',
            name='condicion',
            field=models.CharField(
                choices=[
                    ('compra', 'Compra'),
                    ('alquiler', 'Alquiler'),
                    ('anticresis', 'Anticresis'),
                    ('compartido', 'Compartido'),
                    ('basura', 'Basura / Irrelevante'),
                    ('no_especificado', 'No Especificado'),
                ],
                db_index=True,
                default='no_especificado',
                help_text='¿El cliente busca comprar o alquilar?',
                max_length=20,
                verbose_name='Condición',
            ),
        ),
    ]
