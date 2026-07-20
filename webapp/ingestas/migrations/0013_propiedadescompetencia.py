"""
Generated migration for PropiedadesCompetencia model.

Crea la tabla propiedades_competencia en la base de datos default (Azure SQL).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ingestas', '0012_alter_propiedadraw_condicion'),
    ]

    operations = [
        migrations.CreateModel(
            name='PropiedadesCompetencia',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fuente', models.CharField(help_text='remax, adondevivir, properati, urbania', max_length=50, verbose_name='Portal de origen')),
                ('id_origen', models.CharField(help_text='ID único de la propiedad en el portal de origen', max_length=100, verbose_name='ID en el portal')),
                ('fecha_extraccion', models.DateTimeField(blank=True, null=True, verbose_name='Fecha de extracción')),
                ('titulo', models.CharField(blank=True, max_length=255, null=True, verbose_name='Título')),
                ('tipo_inmueble', models.CharField(blank=True, choices=[('Casa', 'Casa'), ('Departamento', 'Departamento'), ('Terreno', 'Terreno'), ('Oficina', 'Oficina'), ('Local', 'Local'), ('Hotel', 'Hotel'), ('Otro', 'Otro')], max_length=50, null=True, verbose_name='Tipo de inmueble')),
                ('tipo_operacion', models.CharField(blank=True, choices=[('Venta', 'Venta'), ('Alquiler', 'Alquiler'), ('Ambos', 'Compra y Alquiler'), ('No especificado', 'No especificado')], max_length=20, null=True, verbose_name='Tipo de operación')),
                ('precio_soles', models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True, verbose_name='Precio en Soles')),
                ('precio_usd', models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True, verbose_name='Precio en USD')),
                ('area_m2', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Área (m²)')),
                ('dormitorios', models.IntegerField(blank=True, null=True, verbose_name='Dormitorios')),
                ('banos', models.IntegerField(blank=True, null=True, verbose_name='Baños')),
                ('estacionamientos', models.IntegerField(blank=True, null=True, verbose_name='Estacionamientos')),
                ('distrito', models.CharField(blank=True, max_length=100, null=True)),
                ('provincia', models.CharField(blank=True, max_length=100, null=True)),
                ('departamento', models.CharField(blank=True, max_length=100, null=True)),
                ('direccion_texto', models.TextField(blank=True, null=True, verbose_name='Dirección')),
                ('latitud', models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
                ('longitud', models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
                ('descripcion', models.TextField(blank=True, null=True)),
                ('amenities', models.TextField(blank=True, null=True, verbose_name='Servicios / Amenities')),
                ('url', models.URLField(blank=True, max_length=500, null=True, verbose_name='URL de la propiedad')),
                ('imagen_url', models.URLField(blank=True, max_length=500, null=True, verbose_name='URL de imagen')),
                ('antiguedad_anios', models.IntegerField(blank=True, null=True, verbose_name='Antigüedad (años)')),
                ('agencia_agente', models.CharField(blank=True, max_length=200, null=True, verbose_name='Agencia / Agente')),
                ('datos_crudos', models.JSONField(blank=True, help_text='Respaldo del diccionario raw para depuración', null=True, verbose_name='Datos originales del scraper')),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Propiedad de Competencia',
                'verbose_name_plural': 'Propiedades de Competencia',
                'db_table': 'propiedades_competencia',
                'ordering': ['-fecha_extraccion'],
                'indexes': [
                    models.Index(fields=['fuente'], name='prop_comp_fuente_idx'),
                    models.Index(fields=['fuente', 'fecha_extraccion'], name='prop_comp_fuente_fecha_idx'),
                    models.Index(fields=['tipo_inmueble'], name='prop_comp_tipo_idx'),
                    models.Index(fields=['distrito'], name='prop_comp_distrito_idx'),
                ],
                'unique_together': {('fuente', 'id_origen')},
            },
        ),
    ]
