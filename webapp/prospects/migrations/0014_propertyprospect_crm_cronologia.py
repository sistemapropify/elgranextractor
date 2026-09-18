from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('prospects', '0013_propertyprospect_origin_crm'),
    ]

    operations = [
        migrations.AddField(
            model_name='propertyprospect',
            name='crm_cronologia',
            field=models.TextField(blank=True, default='', verbose_name='Cronología del lead (JSON)'),
        ),
    ]
