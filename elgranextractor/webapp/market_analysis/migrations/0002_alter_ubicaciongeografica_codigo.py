from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('market_analysis', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ubicaciongeografica',
            name='codigo',
            field=models.CharField(blank=True, help_text='Código opcional (ej: UBIGEO, fuente de datos)', max_length=200, null=True, verbose_name='Código'),
        ),
    ]
