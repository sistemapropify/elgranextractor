from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('ingestas', '0022_merge_0021_areas_y_verification')]
    operations = [
        migrations.CreateModel(name='RevisionPropiedadScraping', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('excluida', models.BooleanField(default=False, db_index=True)),
            ('motivo', models.TextField(blank=True, default='')),
            ('campos_protegidos', models.JSONField(default=list)),
            ('actualizado_en', models.DateTimeField(auto_now=True)),
            ('propiedad', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,
                 related_name='revision_calidad', to='ingestas.propiedadescompetencia')),
        ]),
        migrations.CreateModel(name='CambioPropiedadScraping', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('usuario', models.CharField(max_length=200)),
            ('cambios', models.JSONField()),
            ('creado_en', models.DateTimeField(auto_now_add=True)),
            ('propiedad', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                 related_name='cambios_manuales', to='ingestas.propiedadescompetencia')),
        ]),
    ]
