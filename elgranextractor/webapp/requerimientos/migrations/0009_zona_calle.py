from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('requerimientos', '0008_urbanizacion_zona'),
    ]

    operations = [
        migrations.CreateModel(
            name='ZonaCalle',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(db_index=True, help_text='Nombre de la zona, calle, edificio o referencia', max_length=200, unique=True, verbose_name='Nombre de zona/calle')),
                ('veces_usado', models.PositiveIntegerField(default=1, verbose_name='Veces usado')),
                ('creado_en', models.DateTimeField(auto_now_add=True, verbose_name='Creado en')),
                ('actualizado_en', models.DateTimeField(auto_now=True, verbose_name='Actualizado en')),
            ],
            options={
                'verbose_name': 'Zona / Calle',
                'verbose_name_plural': 'Zonas y Calles',
                'db_table': 'zona_calle',
                'ordering': ['-veces_usado', 'nombre'],
            },
        ),
    ]
