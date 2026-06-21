from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Inmobiliaria',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(db_index=True, help_text='Nombre de la inmobiliaria', max_length=200, unique=True, verbose_name='Nombre')),
                ('direccion', models.TextField(blank=True, help_text='Dirección física de la inmobiliaria', verbose_name='Dirección')),
                ('latitud', models.FloatField(blank=True, help_text='Coordenada de latitud (-90 a 90)', null=True, verbose_name='Latitud')),
                ('longitud', models.FloatField(blank=True, help_text='Coordenada de longitud (-180 a 180)', null=True, verbose_name='Longitud')),
                ('creado_en', models.DateTimeField(auto_now_add=True, verbose_name='Creado en')),
                ('actualizado_en', models.DateTimeField(auto_now=True, verbose_name='Actualizado en')),
            ],
            options={
                'verbose_name': 'Inmobiliaria',
                'verbose_name_plural': 'Inmobiliarias',
                'db_table': 'agentes_inmobiliaria',
                'ordering': ['nombre'],
            },
        ),
        migrations.CreateModel(
            name='Agente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre_completo', models.CharField(db_index=True, help_text='Nombres y apellidos del agente', max_length=200, verbose_name='Nombre completo')),
                ('telefono', models.CharField(help_text='Número de contacto del agente', max_length=20, verbose_name='Teléfono')),
                ('tipo_agente', models.CharField(choices=[('INDEPENDIENTE', 'Independiente'), ('INMOBILIARIA', 'Inmobiliaria')], default='INDEPENDIENTE', help_text='Independiente o trabaja para una inmobiliaria', max_length=15, verbose_name='Tipo de agente')),
                ('creado_en', models.DateTimeField(auto_now_add=True, verbose_name='Creado en')),
                ('actualizado_en', models.DateTimeField(auto_now=True, verbose_name='Actualizado en')),
                ('inmobiliaria', models.ForeignKey(blank=True, help_text='Inmobiliaria a la que pertenece (solo si aplica)', null=True, on_delete=django.db.models.deletion.SET_NULL, to='agentes.inmobiliaria', verbose_name='Inmobiliaria')),
            ],
            options={
                'verbose_name': 'Agente',
                'verbose_name_plural': 'Agentes',
                'db_table': 'agentes_agente',
                'ordering': ['nombre_completo'],
            },
        ),
    ]
