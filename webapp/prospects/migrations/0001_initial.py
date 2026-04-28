# Generated manually for PropertyProspect model
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PropertyProspect',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('photo', models.ImageField(blank=True, null=True, upload_to='prospects/photos/%Y/%m/', verbose_name='Foto')),
                ('latitude', models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True, verbose_name='Latitud')),
                ('longitude', models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True, verbose_name='Longitud')),
                ('address', models.CharField(blank=True, max_length=300, verbose_name='Dirección')),
                ('district', models.CharField(blank=True, max_length=100, verbose_name='Distrito')),
                ('owner_name', models.CharField(blank=True, max_length=200, verbose_name='Nombre del propietario')),
                ('phone', models.CharField(blank=True, max_length=30, verbose_name='Teléfono')),
                ('operation_type', models.CharField(blank=True, choices=[('alquiler', 'Alquiler'), ('venta', 'Venta')], max_length=20, verbose_name='Tipo de operación')),
                ('property_type', models.CharField(blank=True, choices=[('departamento', 'Departamento'), ('casa', 'Casa'), ('terreno', 'Terreno'), ('local', 'Local Comercial'), ('oficina', 'Oficina'), ('otro', 'Otro')], max_length=20, verbose_name='Tipo de propiedad')),
                ('price', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='Precio')),
                ('currency', models.CharField(blank=True, choices=[('USD', 'USD'), ('PEN', 'PEN')], max_length=3, verbose_name='Moneda')),
                ('bedrooms', models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Dormitorios')),
                ('area_m2', models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True, verbose_name='Área (m²)')),
                ('ocr_raw_text', models.TextField(blank=True, verbose_name='Texto OCR / IA')),
                ('ocr_processed_at', models.DateTimeField(blank=True, null=True, verbose_name='Procesado con IA el')),
                ('status', models.CharField(choices=[('borrador', 'Borrador'), ('pendiente', 'Pendiente'), ('contactado', 'Contactado'), ('negociando', 'Negociando'), ('captado', 'Captado'), ('perdido', 'Perdido')], default='borrador', max_length=20, verbose_name='Estado')),
                ('notes', models.TextField(blank=True, verbose_name='Notas')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Creado el')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Actualizado el')),
                ('agent', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='prospects', to=settings.AUTH_USER_MODEL, verbose_name='Agente')),
            ],
            options={
                'verbose_name': 'Prospecto',
                'verbose_name_plural': 'Prospectos',
                'db_table': 'prospects_propertyprospect',
                'ordering': ['-created_at'],
            },
        ),
    ]
