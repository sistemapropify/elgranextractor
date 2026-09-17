from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('prospects', '0010_propertyprospect_tomada_en_captado'),
    ]

    operations = [
        migrations.AlterField(
            model_name='propertyprospect',
            name='status',
            field=models.CharField(
                choices=[
                    ('borrador', 'Borrador'),
                    ('pendiente', 'Pendiente'),
                    ('contactado', 'Contactado'),
                    ('negociando', 'Negociando'),
                    ('captado', 'Captado'),
                    ('descartado', 'Descartado'),
                    ('caducado', 'Caducó'),
                ],
                default='borrador',
                max_length=20,
                verbose_name='Estado',
            ),
        ),
    ]
