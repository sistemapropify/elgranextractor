# Generated manually para evitar conflictos con base de datos 'propifai'

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('intelligence', '0010_alter_user_username_user_unique_phone_when_not_null_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='SkillExecution',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('skill_name', models.CharField(db_index=True, max_length=100)),
                ('parameters', models.JSONField(blank=True, default=dict)),
                ('result', models.JSONField(blank=True, default=dict, null=True)),
                ('status', models.CharField(choices=[('success', 'Success'), ('error', 'Error'), ('timeout', 'Timeout'), ('cached', 'Cached')], db_index=True, default='success', max_length=20)),
                ('latency_ms', models.FloatField(default=0)),
                ('error_message', models.TextField(blank=True, null=True)),
                ('cached', models.BooleanField(default=False)),
                ('executed_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('conversation', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='intelligence.conversation')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='intelligence.user')),
            ],
            options={
                'verbose_name': 'Ejecución de Skill',
                'verbose_name_plural': 'Ejecuciones de Skills',
                'db_table': 'intelligence_skill_execution',
                'ordering': ['-executed_at'],
                'indexes': [
                    models.Index(fields=['skill_name', 'executed_at'], name='intel_skil_skill_n_1a0b2c'),
                    models.Index(fields=['status', 'executed_at'], name='intel_skil_status_3d4e5f'),
                ],
            },
        ),
    ]
