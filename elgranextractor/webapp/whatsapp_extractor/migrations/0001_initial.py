# Generated manually - migración inicial para whatsapp_extractor
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='WhatsappGroupSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre_grupo', models.CharField(max_length=255, unique=True, verbose_name='Nombre del grupo')),
                ('fuente_choice', models.CharField(blank=True, help_text='Valor de FuenteChoices en requerimientos.models', max_length=50, null=True, verbose_name='Fuente asociada')),
                ('ultima_extraccion', models.DateTimeField(blank=True, null=True, verbose_name='Última extracción')),
                ('cookie_path', models.CharField(blank=True, help_text='Ruta al archivo de cookies guardadas', max_length=500, null=True, verbose_name='Ruta cookies')),
                ('activo', models.BooleanField(default=True, verbose_name='Activo')),
                ('mensaje_error', models.TextField(blank=True, null=True, verbose_name='Último error')),
                ('creado_en', models.DateTimeField(auto_now_add=True, verbose_name='Creado en')),
                ('actualizado_en', models.DateTimeField(auto_now=True, verbose_name='Actualizado en')),
            ],
            options={
                'verbose_name': 'Sesión de Grupo WhatsApp',
                'verbose_name_plural': 'Sesiones de Grupos WhatsApp',
                'db_table': 'whatsapp_group_session',
                'ordering': ['-ultima_extraccion'],
            },
        ),
        migrations.CreateModel(
            name='ExtractorLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ejecucion_fecha', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Fecha de ejecución')),
                ('estado', models.CharField(choices=[('pending', 'Pendiente'), ('running', 'Ejecutando'), ('completed', 'Completado'), ('error', 'Error')], default='pending', max_length=20, verbose_name='Estado')),
                ('mensajes_extraidos_total', models.IntegerField(default=0, verbose_name='Mensajes extraídos')),
                ('mensajes_validos', models.IntegerField(default=0, verbose_name='Mensajes válidos')),
                ('requerimientos_nuevos', models.IntegerField(default=0, verbose_name='Requerimientos nuevos')),
                ('requerimientos_duplicados', models.IntegerField(default=0, verbose_name='Requerimientos duplicados')),
                ('requerimientos_basura_filtrados', models.IntegerField(default=0, verbose_name='Basura filtrada')),
                ('mensaje_error', models.TextField(blank=True, null=True, verbose_name='Mensaje de error')),
                ('stack_trace', models.TextField(blank=True, null=True, verbose_name='Stack trace')),
                ('tiempo_proceso_segundos', models.FloatField(blank=True, null=True, verbose_name='Tiempo de proceso (s)')),
                ('grupo_procesado_ids', models.JSONField(blank=True, default=list, verbose_name='IDs de grupos procesados')),
            ],
            options={
                'verbose_name': 'Log de Extracción',
                'verbose_name_plural': 'Logs de Extracción',
                'db_table': 'whatsapp_extractor_log',
                'ordering': ['-ejecucion_fecha'],
            },
        ),
    ]
