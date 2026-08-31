from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('prospects', '0003_capture_origin_contract_zone')]

    operations = [
        migrations.AlterField(
            model_name='propertyprospect',
            name='photo',
            field=models.ImageField(blank=True, upload_to='prospects/photos/%Y/%m/', verbose_name='Foto del anuncio'),
        ),
    ]
