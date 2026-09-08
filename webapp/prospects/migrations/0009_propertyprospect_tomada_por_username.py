from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('prospects', '0008_alter_propertyprospect_address_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='propertyprospect',
            name='tomada_por_username',
            field=models.CharField(
                blank=True,
                db_index=True,
                default='',
                help_text='Username Propify del agente que marcó esta captación como suya.',
                max_length=150,
                verbose_name='Usuario que tomó la prospección',
            ),
        ),
    ]
