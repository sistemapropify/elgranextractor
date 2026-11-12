from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('external_agents', '0009_commission_ledgers'),
    ]

    operations = [
        migrations.AddField(
            model_name='commissioncollection',
            name='deal_type',
            field=models.CharField(
                choices=[
                    ('sale', 'Venta'),
                    ('rent', 'Alquiler'),
                ],
                db_index=True,
                default='sale',
                max_length=10,
                verbose_name='Tipo de operación',
            ),
        ),
    ]
