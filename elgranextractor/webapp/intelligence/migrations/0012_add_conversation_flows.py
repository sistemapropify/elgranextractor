from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('intelligence', '0011_skillexecution'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConversationFlow',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=200, unique=True, verbose_name='Nombre del flujo')),
                ('description', models.TextField(blank=True, verbose_name='Descripción')),
                ('states', models.JSONField(default=dict, verbose_name='Estados del flujo', help_text='JSON con estados del flujo.')),
                ('initial_state', models.CharField(default='start', max_length=100, verbose_name='Estado inicial')),
                ('metadata', models.JSONField(default=dict, verbose_name='Metadatos')),
                ('is_active', models.BooleanField(default=True, verbose_name='Activo')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'intelligence_conversation_flows',
                'verbose_name': 'Flujo de Conversación',
                'verbose_name_plural': 'Flujos de Conversación',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='ConversationFlowState',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('current_state', models.CharField(max_length=100, verbose_name='Estado actual')),
                ('collected_data', models.JSONField(default=dict, verbose_name='Datos recopilados', help_text='Datos que el usuario ha proporcionado durante el flujo')),
                ('state_history', models.JSONField(default=list, verbose_name='Historial de estados', help_text='Lista de estados por los que ha pasado la conversación')),
                ('is_completed', models.BooleanField(default=False, verbose_name='Completado')),
                ('completed_at', models.DateTimeField(blank=True, null=True, verbose_name='Completado en')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('conversation', models.OneToOneField(on_delete=models.CASCADE, related_name='flow_state', to='intelligence.conversation', verbose_name='Conversación')),
                ('flow', models.ForeignKey(on_delete=models.CASCADE, related_name='active_conversations', to='intelligence.conversationflow', verbose_name='Flujo')),
            ],
            options={
                'db_table': 'intelligence_conversation_flow_states',
                'verbose_name': 'Estado de Flujo de Conversación',
                'verbose_name_plural': 'Estados de Flujo de Conversación',
                'ordering': ['-updated_at'],
            },
        ),
    ]
