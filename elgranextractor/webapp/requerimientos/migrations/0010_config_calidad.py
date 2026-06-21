from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('requerimientos', '0009_zona_calle'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConfiguracionCalidad',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('activo', models.BooleanField(default=True, verbose_name='Configuración activa')),
                ('config', models.JSONField(default=dict, verbose_name='Configuración JSON')),
                ('nombre', models.CharField(blank=True, default='Default', max_length=100, verbose_name='Nombre de configuración')),
                ('creado_en', models.DateTimeField(auto_now_add=True, verbose_name='Creado en')),
                ('actualizado_en', models.DateTimeField(auto_now=True, verbose_name='Actualizado en')),
            ],
            options={
                'verbose_name': 'Configuración de Calidad',
                'verbose_name_plural': 'Configuraciones de Calidad',
                'db_table': 'config_calidad',
            },
        ),
    ]
