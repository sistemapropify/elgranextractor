import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('intelligence', '0020_add_skill_name_campos_faltantes'),
    ]

    operations = [
        migrations.CreateModel(
            name='SystemTrace',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('trace_id', models.CharField(db_index=True, max_length=64, unique=True)),
                ('request_kind', models.CharField(db_index=True, default='unknown', max_length=50)),
                ('normalized_query_hash', models.CharField(blank=True, db_index=True, default='', max_length=64)),
                ('query_redacted', models.TextField(blank=True, default='')),
                ('status', models.CharField(choices=[('started', 'Iniciada'), ('completed', 'Completada'), ('completed_empty', 'Completada sin resultados'), ('failed', 'Fallida'), ('timeout', 'Timeout'), ('blocked', 'Bloqueada por guardrail')], db_index=True, default='started', max_length=30)),
                ('technical_success', models.BooleanField(default=False)),
                ('grounded', models.BooleanField(blank=True, db_index=True, null=True)),
                ('result_count', models.IntegerField(blank=True, null=True)),
                ('orchestration_mode', models.CharField(blank=True, default='', max_length=50)),
                ('code_version', models.CharField(blank=True, default='unknown', max_length=64)),
                ('config_version', models.CharField(blank=True, default='unknown', max_length=64)),
                ('embedding_version', models.CharField(blank=True, default='unknown', max_length=64)),
                ('latency_ms', models.IntegerField(blank=True, null=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('started_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('conversation', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='system_traces', to='intelligence.conversation')),
            ],
            options={
                'db_table': 'intelligence_system_trace',
                'ordering': ['-started_at'],
            },
        ),
        migrations.CreateModel(
            name='SystemEvent',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('sequence', models.PositiveIntegerField()),
                ('event_type', models.CharField(db_index=True, max_length=80)),
                ('component', models.CharField(db_index=True, max_length=100)),
                ('outcome', models.CharField(db_index=True, default='info', max_length=30)),
                ('error_code', models.CharField(blank=True, db_index=True, default='', max_length=80)),
                ('payload', models.JSONField(blank=True, default=dict)),
                ('duration_ms', models.IntegerField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('trace', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='events', to='intelligence.systemtrace')),
            ],
            options={
                'db_table': 'intelligence_system_event',
                'ordering': ['sequence'],
            },
        ),
        migrations.AddIndex(
            model_name='systemtrace',
            index=models.Index(fields=['status', 'started_at'], name='intel_trace_status_idx'),
        ),
        migrations.AddIndex(
            model_name='systemtrace',
            index=models.Index(fields=['request_kind', 'started_at'], name='intel_trace_kind_idx'),
        ),
        migrations.AddIndex(
            model_name='systemtrace',
            index=models.Index(fields=['grounded', 'started_at'], name='intel_trace_ground_idx'),
        ),
        migrations.AddIndex(
            model_name='systemevent',
            index=models.Index(fields=['event_type', 'created_at'], name='intel_event_type_idx'),
        ),
        migrations.AddIndex(
            model_name='systemevent',
            index=models.Index(fields=['error_code', 'created_at'], name='intel_event_error_idx'),
        ),
        migrations.AddConstraint(
            model_name='systemevent',
            constraint=models.UniqueConstraint(fields=('trace', 'sequence'), name='unique_event_sequence_per_trace'),
        ),
    ]
