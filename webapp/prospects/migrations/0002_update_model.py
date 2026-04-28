# Generated manually to sync model with database
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('prospects', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='propertyprospect',
            name='currency',
            field=models.CharField(blank=True, choices=[('USD', 'USD'), ('PEN', 'PEN (Soles)')], default='USD', max_length=5, verbose_name='Moneda'),
        ),
        migrations.AlterField(
            model_name='propertyprospect',
            name='notes',
            field=models.TextField(blank=True, verbose_name='Notas del agente'),
        ),
        migrations.AlterField(
            model_name='propertyprospect',
            name='ocr_raw_text',
            field=models.TextField(blank=True, verbose_name='Texto extraído (raw)'),
        ),
        migrations.AlterField(
            model_name='propertyprospect',
            name='operation_type',
            field=models.CharField(blank=True, choices=[('alquiler', 'Alquiler'), ('venta', 'Venta')], max_length=20, verbose_name='Operación'),
        ),
        migrations.AlterField(
            model_name='propertyprospect',
            name='owner_name',
            field=models.CharField(blank=True, max_length=200, verbose_name='Nombre propietario'),
        ),
        migrations.AlterField(
            model_name='propertyprospect',
            name='phone',
            field=models.CharField(blank=True, max_length=30, verbose_name='Teléfono'),
        ),
        migrations.AlterField(
            model_name='propertyprospect',
            name='photo',
            field=models.ImageField(upload_to='prospects/photos/%Y/%m/', verbose_name='Foto del anuncio'),
        ),
        migrations.AlterField(
            model_name='propertyprospect',
            name='property_type',
            field=models.CharField(blank=True, choices=[('departamento', 'Departamento'), ('casa', 'Casa'), ('local', 'Local comercial'), ('terreno', 'Terreno'), ('oficina', 'Oficina'), ('otro', 'Otro')], max_length=20, verbose_name='Tipo de inmueble'),
        ),
        migrations.AlterField(
            model_name='propertyprospect',
            name='status',
            field=models.CharField(choices=[('borrador', 'Borrador'), ('pendiente', 'Pendiente'), ('contactado', 'Contactado'), ('negociando', 'Negociando'), ('captado', 'Captado'), ('descartado', 'Descartado')], default='borrador', max_length=20, verbose_name='Estado'),
        ),
    ]
