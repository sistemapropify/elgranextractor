from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('prospects', '0012_prospectcomment'),
    ]

    operations = [
        migrations.AddField(
            model_name='propertyprospect',
            name='crm_lead_id',
            field=models.BigIntegerField(blank=True, db_index=True, null=True, verbose_name='Lead CRM origen'),
        ),
        migrations.AlterField(
            model_name='propertyprospect',
            name='origin',
            field=models.CharField(
                blank=True,
                choices=[
                    ('marketplace', 'Marketplace'),
                    ('calle', 'Calle'),
                    ('otros', 'Otros'),
                    ('crm', 'CRM'),
                ],
                max_length=20,
                verbose_name='Origen',
            ),
        ),
    ]
