"""
Generated migration for AIConsumptionLog model.
"""
from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('intelligence', '0016_add_semantic_tags_to_collection'),
    ]

    operations = [
        migrations.CreateModel(
            name='AIConsumptionLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('model_name', models.CharField(default='deepseek-chat', max_length=100, verbose_name='Modelo usado')),
                ('endpoint', models.CharField(blank=True, default='', max_length=255, verbose_name='Endpoint o función que llamó a la API')),
                ('caller_app', models.CharField(blank=True, default='', max_length=100, verbose_name='App Django que originó la llamada')),
                ('prompt_tokens', models.IntegerField(default=0, verbose_name='Tokens de entrada (prompt)')),
                ('completion_tokens', models.IntegerField(default=0, verbose_name='Tokens de salida (completion)')),
                ('total_tokens', models.IntegerField(default=0, verbose_name='Tokens totales')),
                ('estimated_cost_usd', models.DecimalField(decimal_places=8, default=0, max_digits=10, verbose_name='Costo estimado USD')),
                ('duration_ms', models.IntegerField(default=0, verbose_name='Duración de la llamada (ms)')),
                ('success', models.BooleanField(default=True, verbose_name='¿La llamada fue exitosa?')),
                ('status_code', models.IntegerField(blank=True, null=True, verbose_name='Código de estado HTTP')),
                ('error_message', models.TextField(blank=True, default='', verbose_name='Mensaje de error si falló')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Fecha/hora de la llamada')),
            ],
            options={
                'verbose_name': 'Registro de consumo IA',
                'verbose_name_plural': 'Registros de consumo IA',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='aiconsumptionlog',
            index=models.Index(fields=['created_at'], name='intelligenc_created_3e5b3b_idx'),
        ),
        migrations.AddIndex(
            model_name='aiconsumptionlog',
            index=models.Index(fields=['model_name'], name='intelligenc_model_n_8e9fdb_idx'),
        ),
        migrations.AddIndex(
            model_name='aiconsumptionlog',
            index=models.Index(fields=['success'], name='intelligenc_success_9e0e5a_idx'),
        ),
    ]
