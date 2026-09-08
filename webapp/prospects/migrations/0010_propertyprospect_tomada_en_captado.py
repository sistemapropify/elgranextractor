from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('prospects', '0009_propertyprospect_tomada_por_username'),
    ]

    operations = [
        migrations.AddField(
            model_name='propertyprospect',
            name='tomada_en',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Fecha y hora en que se tomó la prospección'),
        ),
        migrations.AddField(
            model_name='propertyprospect',
            name='captado',
            field=models.BooleanField(
                default=False,
                help_text='True = CAPTADO · False = NO CAPTADO',
                verbose_name='Captado',
            ),
        ),
    ]
