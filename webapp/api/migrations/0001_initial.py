# Generated manually for POI system

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='CategoriaPOI',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=100, unique=True, verbose_name='Nombre')),
                ('slug', models.SlugField(max_length=100, unique=True, verbose_name='Identificador', help_text='Identificador único para la API (ej: hospital, pharmacy)')),
                ('icono', models.CharField(blank=True, max_length=50, verbose_name='Icono (emoji)', help_text='Ej: 🏥, 💊, 🏪, 🏫')),
                ('color', models.CharField(default='#58a6ff', max_length=7, verbose_name='Color (hex)', help_text='Color para el marcador en el mapa, ej: #FF5733')),
                ('descripcion', models.TextField(blank=True, verbose_name='Descripción')),
                ('orden', models.PositiveIntegerField(default=0, verbose_name='Orden', help_text='Orden de aparición en listados (menor = primero)')),
                ('is_active', models.BooleanField(default=True, verbose_name='Activo')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Categoría / Capa',
                'verbose_name_plural': 'Categorías / Capas',
                'ordering': ['orden', 'nombre'],
            },
        ),
        migrations.CreateModel(
            name='PointOfInterest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=200, verbose_name='Nombre')),
                ('latitud', models.DecimalField(decimal_places=7, max_digits=10, verbose_name='Latitud')),
                ('longitud', models.DecimalField(decimal_places=7, max_digits=10, verbose_name='Longitud')),
                ('direccion', models.CharField(blank=True, max_length=300, verbose_name='Dirección')),
                ('descripcion', models.TextField(blank=True, verbose_name='Descripción')),
                ('telefono', models.CharField(blank=True, max_length=30, verbose_name='Teléfono')),
                ('sitio_web', models.URLField(blank=True, max_length=500, verbose_name='Sitio web')),
                ('is_active', models.BooleanField(default=True, verbose_name='Activo')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('categoria', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='puntos', to='api.categoriapoi', verbose_name='Categoría / Capa')),
            ],
            options={
                'verbose_name': 'Punto de Interés',
                'verbose_name_plural': 'Puntos de Interés',
            },
        ),
        migrations.AddIndex(
            model_name='pointofinterest',
            index=models.Index(fields=['categoria'], name='api_poi_categoria_idx'),
        ),
        migrations.AddIndex(
            model_name='pointofinterest',
            index=models.Index(fields=['is_active'], name='api_poi_active_idx'),
        ),
    ]
