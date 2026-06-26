"""Add ArchivoLienzo model for canvas file uploads."""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """Adds ArchivoLienzo model to store uploaded file metadata."""

    dependencies = [
        ('canvas', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ArchivoLienzo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(help_text='Nombre original del archivo', max_length=255)),
                ('tipo', models.CharField(choices=[('excel', 'Excel'), ('word', 'Word'), ('pdf', 'PDF'), ('image', 'Imagen'), ('other', 'Otro')], max_length=20)),
                ('blob_url', models.URLField(blank=True, default='', help_text='URL en Azure Blob Storage', max_length=1024)),
                ('blob_name', models.CharField(blank=True, default='', help_text='Nombre del blob en Azure', max_length=512)),
                ('tamano', models.BigIntegerField(default=0, help_text='Tamaño en bytes')),
                ('x', models.IntegerField(default=100)),
                ('y', models.IntegerField(default=100)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('lienzo', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='archivos', to='canvas.lienzo')),
            ],
        ),
    ]
