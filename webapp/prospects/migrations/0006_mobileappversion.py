from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('prospects', '0005_mobile_prospect_identity')]
    operations = [migrations.CreateModel(
        name='MobileAppVersion',
        fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('version_code', models.PositiveBigIntegerField(unique=True, verbose_name='Version code')),
            ('version_name', models.CharField(blank=True, max_length=50, verbose_name='Versión')),
            ('download_url', models.URLField(max_length=1000, verbose_name='URL del APK')),
            ('sha256', models.CharField(blank=True, max_length=64, verbose_name='SHA-256')),
            ('min_supported_version_code', models.PositiveBigIntegerField(default=1)),
            ('force_update', models.BooleanField(default=False, verbose_name='Actualización obligatoria')),
            ('published', models.BooleanField(default=False, verbose_name='Publicada')),
            ('release_notes', models.TextField(blank=True, verbose_name='Notas de versión')),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('published_at', models.DateTimeField(blank=True, null=True)),
        ],
        options={'ordering': ['-version_code'], 'verbose_name': 'Versión de propitools', 'verbose_name_plural': 'Versiones de propitools'},
    )]
