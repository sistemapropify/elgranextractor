import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('intelligence', '0009_user_first_name_user_last_login_user_last_name_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='ACMLink',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('tipo_propiedad', models.CharField(max_length=50, verbose_name='Tipo de propiedad')),
                ('area_m2', models.DecimalField(decimal_places=2, max_digits=12, verbose_name='Área en m²')),
                ('es_terreno', models.BooleanField(default=False, verbose_name='Es terreno')),
                ('precio_min_m2', models.DecimalField(decimal_places=2, max_digits=12, verbose_name='Precio mínimo m²')),
                ('precio_max_m2', models.DecimalField(decimal_places=2, max_digits=12, verbose_name='Precio máximo m²')),
                ('precio_promedio_m2', models.DecimalField(decimal_places=2, max_digits=12, verbose_name='Precio promedio m²')),
                ('precio_promedio_ponderado_m2', models.DecimalField(decimal_places=2, max_digits=12, verbose_name='Precio promedio ponderado m²')),
                ('valor_comercial', models.DecimalField(decimal_places=2, max_digits=14, verbose_name='Valor comercial estimado')),
                ('precio_venta_sugerido', models.DecimalField(decimal_places=2, max_digits=14, verbose_name='Precio venta sugerido')),
                ('valor_realizacion', models.DecimalField(decimal_places=2, max_digits=14, verbose_name='Valor realización inmediata')),
                ('num_comparables', models.IntegerField(default=0, verbose_name='Número de comparables')),
                ('propiedades_json', models.JSONField(default=list, verbose_name='Propiedades comparables')),
                ('click_count', models.IntegerField(default=0, verbose_name='Contador de clicks')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Creado')),
                ('last_click_at', models.DateTimeField(blank=True, null=True, verbose_name='Último click')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='acm_links', to='intelligence.user', verbose_name='Usuario que generó el enlace')),
            ],
            options={
                'verbose_name': 'Enlace ACM',
                'verbose_name_plural': 'Enlaces ACM',
                'db_table': 'acm_links',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='acmlink',
            index=models.Index(fields=['user', '-created_at'], name='acm_links_user_created_idx'),
        ),
        migrations.AddIndex(
            model_name='acmlink',
            index=models.Index(fields=['created_at'], name='acm_links_created_idx'),
        ),
    ]
