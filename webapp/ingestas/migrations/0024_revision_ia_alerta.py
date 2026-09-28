"""Tabla de triaje automatico de alertas de calidad (solo agrega una tabla)."""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('ingestas', '0023_revision_calidad_scraping')]
    operations = [
        migrations.CreateModel(
            name='RevisionIAAlerta',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('veredicto', models.CharField(
                    choices=[('real', 'Alerta real'), ('ruido', 'Falso positivo'),
                             ('dudoso', 'Dudoso'), ('error', 'No se pudo analizar')],
                    db_index=True, max_length=12)),
                ('motivo', models.TextField(blank=True, default='')),
                ('correccion', models.JSONField(
                    blank=True, default=dict,
                    help_text='campo -> valor sugerido, si la alerta es real')),
                ('alertas_revisadas', models.JSONField(blank=True, default=list)),
                ('confianza', models.DecimalField(blank=True, decimal_places=2,
                                                  max_digits=4, null=True)),
                ('modelo', models.CharField(blank=True, default='', max_length=80)),
                ('respuesta_cruda', models.JSONField(blank=True, null=True)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
                ('propiedad', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='revisiones_ia', to='ingestas.propiedadescompetencia')),
            ],
            options={
                'db_table': 'calidad_revision_ia',
                'constraints': [models.UniqueConstraint(
                    fields=('propiedad',), name='calidad_revision_ia_uq')],
            },
        ),
    ]
