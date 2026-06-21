from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='UbicacionGeografica',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=200, verbose_name='Nombre')),
                ('nivel', models.CharField(choices=[('departamento', 'Departamento'), ('provincia', 'Provincia'), ('distrito', 'Distrito')], max_length=20, verbose_name='Nivel')),
                ('codigo', models.CharField(blank=True, help_text='Código opcional (ej: UBIGEO)', max_length=20, null=True, verbose_name='Código')),
                ('activo', models.BooleanField(default=True, verbose_name='Activo')),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')),
                ('fecha_actualizacion', models.DateTimeField(auto_now=True, verbose_name='Última actualización')),
                ('parent', models.ForeignKey(blank=True, help_text='Nivel superior en la jerarquía (ej: Provincia padre del Distrito)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='children', to='market_analysis.ubicaciongeografica', verbose_name='Padre')),
            ],
            options={
                'verbose_name': 'Ubicación Geográfica',
                'verbose_name_plural': 'Ubicaciones Geográficas',
                'ordering': ['nivel', 'nombre'],
                'indexes': [models.Index(fields=['nivel'], name='market_anal_nivel_0b4c9d_idx'), models.Index(fields=['parent'], name='market_anal_parent_5e1b8f_idx'), models.Index(fields=['nombre'], name='market_anal_nombre_3a7c2e_idx')],
                'unique_together': {('nombre', 'parent', 'nivel')},
            },
        ),
    ]
