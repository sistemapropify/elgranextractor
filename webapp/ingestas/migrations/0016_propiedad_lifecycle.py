import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ingestas', '0015_scrapingjob_execution_token'),
    ]

    operations = [
        migrations.CreateModel(
            name='EjecucionPortal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name='Token estable de ejecución')),
                ('portal', models.CharField(db_index=True, max_length=50)),
                ('estado', models.CharField(choices=[('running', 'Ejecutando'), ('completed', 'Completada'), ('incomplete', 'Incompleta'), ('error', 'Error')], db_index=True, default='running', max_length=20)),
                ('es_confiable', models.BooleanField(default=False)),
                ('es_linea_base', models.BooleanField(default=False)),
                ('propiedades_vistas', models.PositiveIntegerField(default=0)),
                ('posibles_retiradas', models.PositiveIntegerField(default=0)),
                ('retiros_confirmados', models.PositiveIntegerField(default=0)),
                ('motivo_no_confiable', models.TextField(blank=True, null=True)),
                ('iniciado_en', models.DateTimeField(auto_now_add=True)),
                ('completado_en', models.DateTimeField(blank=True, null=True)),
                ('job', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ejecuciones_portal', to='ingestas.scrapingjob', verbose_name='Trabajo de scraping')),
            ],
            options={
                'verbose_name': 'Ejecución de portal',
                'verbose_name_plural': 'Ejecuciones de portales',
                'db_table': 'scraping_ejecuciones_portal',
                'ordering': ['-iniciado_en'],
                'indexes': [
                    models.Index(fields=['portal', 'estado'], name='ejec_portal_estado_idx'),
                    models.Index(fields=['portal', 'es_confiable', 'completado_en'], name='ejec_portal_conf_fin_idx'),
                ],
            },
        ),
        migrations.AddField(
            model_name='propiedadescompetencia',
            name='ausencias_consecutivas',
            field=models.PositiveSmallIntegerField(default=0, verbose_name='Ausencias consecutivas'),
        ),
        migrations.AddField(
            model_name='propiedadescompetencia',
            name='estado_publicacion',
            field=models.CharField(choices=[('sin_verificar', 'Sin verificar'), ('activa', 'Activa'), ('posible_retirada', 'Posible retirada'), ('retirada', 'Retirada')], db_index=True, default='sin_verificar', max_length=24, verbose_name='Estado de publicación'),
        ),
        migrations.AddField(
            model_name='propiedadescompetencia',
            name='fecha_primera_ausencia',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Primera ausencia detectada'),
        ),
        migrations.AddField(
            model_name='propiedadescompetencia',
            name='fecha_retiro_confirmado',
            field=models.DateTimeField(blank=True, db_index=True, null=True, verbose_name='Retiro confirmado'),
        ),
        migrations.AddField(
            model_name='propiedadescompetencia',
            name='primera_vez_vista',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Primera vez vista'),
        ),
        migrations.AddField(
            model_name='propiedadescompetencia',
            name='ultima_ejecucion_vista',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='publicaciones_ultima_vista', to='ingestas.ejecucionportal', verbose_name='Última ejecución donde fue vista'),
        ),
        migrations.AddField(
            model_name='propiedadescompetencia',
            name='ultima_vez_vista',
            field=models.DateTimeField(blank=True, db_index=True, null=True, verbose_name='Última vez vista'),
        ),
    ]
