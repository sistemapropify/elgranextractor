"""
Migration for ScrapingJob and ScrapingLog models.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ingestas', '0013_propiedadescompetencia'),
    ]

    operations = [
        migrations.CreateModel(
            name='ScrapingJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('estado', models.CharField(choices=[('idle', 'Inactivo'), ('running', 'Ejecutando'), ('paused', 'Pausado'), ('completed', 'Completado'), ('error', 'Error'), ('stopped', 'Detenido')], default='idle', max_length=20, verbose_name='Estado')),
                ('portal_actual', models.CharField(blank=True, max_length=50, null=True, verbose_name='Portal actual')),
                ('progreso', models.IntegerField(default=0, verbose_name='Progreso (%)')),
                ('total_propiedades', models.IntegerField(default=0, verbose_name='Total propiedades')),
                ('procesadas', models.IntegerField(default=0, verbose_name='Procesadas')),
                ('nuevas', models.IntegerField(default=0, verbose_name='Nuevas insertadas')),
                ('actualizadas', models.IntegerField(default=0, verbose_name='Actualizadas')),
                ('errores', models.IntegerField(default=0, verbose_name='Con error')),
                ('parametros', models.JSONField(blank=True, default=dict, help_text='Portales seleccionados, max_paginas, etc.', null=True, verbose_name='Parámetros de ejecución')),
                ('mensaje_error', models.TextField(blank=True, null=True, verbose_name='Mensaje de error')),
                ('iniciado_en', models.DateTimeField(blank=True, null=True, verbose_name='Iniciado en')),
                ('completado_en', models.DateTimeField(blank=True, null=True, verbose_name='Completado en')),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Trabajo de Scraping',
                'verbose_name_plural': 'Trabajos de Scraping',
                'db_table': 'scraping_jobs',
                'ordering': ['-creado_en'],
            },
        ),
        migrations.CreateModel(
            name='ScrapingLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nivel', models.CharField(choices=[('info', 'Info'), ('success', 'Success'), ('warning', 'Warning'), ('error', 'Error'), ('debug', 'Debug')], default='info', max_length=20, verbose_name='Nivel')),
                ('mensaje', models.TextField(verbose_name='Mensaje')),
                ('portal', models.CharField(blank=True, max_length=50, null=True, verbose_name='Portal')),
                ('propiedad_id', models.CharField(blank=True, max_length=100, null=True, verbose_name='ID de propiedad')),
                ('timestamp', models.DateTimeField(auto_now_add=True, verbose_name='Timestamp')),
                ('job', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='logs', to='ingestas.scrapingjob', verbose_name='Trabajo')),
            ],
            options={
                'verbose_name': 'Log de Scraping',
                'verbose_name_plural': 'Logs de Scraping',
                'db_table': 'scraping_logs',
                'ordering': ['timestamp'],
            },
        ),
    ]
