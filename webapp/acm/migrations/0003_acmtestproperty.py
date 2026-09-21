from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('acm', '0002_rename_acm_links_user_created_idx_acm_links_user_id_123283_idx_and_more')]
    operations = [migrations.CreateModel(
        name='ACMTestProperty',
        fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('source_id', models.CharField(max_length=120, unique=True)),
            ('source', models.CharField(blank=True, default='', max_length=50)),
            ('tipo_propiedad', models.CharField(blank=True, default='', max_length=100)),
            ('precio_usd', models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True)),
            ('precio_final_venta', models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True)),
            ('descripcion', models.TextField(blank=True, default='')),
            ('portal', models.CharField(blank=True, default='', max_length=50)),
            ('url_propiedad', models.URLField(blank=True, default='', max_length=500)),
            ('coordenadas', models.CharField(blank=True, default='', max_length=100)),
            ('departamento', models.CharField(blank=True, default='', max_length=100)),
            ('provincia', models.CharField(blank=True, default='', max_length=100)),
            ('distrito', models.CharField(blank=True, default='', max_length=100)),
            ('area_terreno', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
            ('area_construida', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
            ('numero_habitaciones', models.IntegerField(blank=True, null=True)),
            ('numero_banos', models.IntegerField(blank=True, null=True)),
            ('numero_cocheras', models.IntegerField(blank=True, null=True)),
            ('imagenes_propiedad', models.TextField(blank=True, default='')),
            ('estado_propiedad', models.CharField(blank=True, default='', max_length=50)),
            ('datos_crudos', models.JSONField(blank=True, default=dict)),
            ('synced_at', models.DateTimeField(auto_now=True)),
        ],
        options={'db_table': 'acm_test_properties', 'ordering': ['-synced_at', 'id']},
    )]
