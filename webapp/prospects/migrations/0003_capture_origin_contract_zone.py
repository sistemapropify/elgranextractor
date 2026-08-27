from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('prospects', '0002_update_model')]
    operations = [
        migrations.AddField('propertyprospect', 'origin', models.CharField(blank=True, choices=[('marketplace', 'Marketplace'), ('calle', 'Calle'), ('otros', 'Otros')], max_length=20, verbose_name='Origen')),
        migrations.AddField('propertyprospect', 'origin_other', models.CharField(blank=True, max_length=120, verbose_name='Otro origen')),
        migrations.AddField('propertyprospect', 'marketplace_url', models.URLField(blank=True, max_length=500, verbose_name='Enlace Marketplace')),
        migrations.AddField('propertyprospect', 'zone', models.CharField(blank=True, max_length=150, verbose_name='Zona')),
        migrations.AddField('propertyprospect', 'contract_type', models.CharField(blank=True, choices=[('trato_directo', 'Trato directo'), ('inmobiliaria', 'Inmobiliaria')], max_length=20, verbose_name='Tipo de contrato')),
    ]
