# Generated manually: LogEntry model for live extraction tracking
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp_extractor', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='LogEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Timestamp')),
                ('nivel', models.CharField(choices=[('DEBUG', 'DEBUG'), ('INFO', 'INFO'), ('WARNING', 'WARNING'), ('ERROR', 'ERROR')], default='INFO', max_length=10, verbose_name='Nivel')),
                ('mensaje', models.TextField(help_text='Descripción del paso ejecutado', verbose_name='Mensaje')),
                ('detalles', models.JSONField(blank=True, default=dict, help_text='Datos estructurados adicionales (métricas parciales, etc.)', verbose_name='Detalles adicionales')),
                ('extractor_log', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='entries', to='whatsapp_extractor.extractorlog', verbose_name='Log de extracción')),
            ],
            options={
                'verbose_name': 'Entrada de log detallado',
                'verbose_name_plural': 'Entradas de log detallado',
                'db_table': 'whatsapp_extractor_log_entry',
                'ordering': ['timestamp'],
                'indexes': [models.Index(fields=['extractor_log', 'timestamp'], name='idx_ws_entry_log_ts')],
            },
        ),
    ]
