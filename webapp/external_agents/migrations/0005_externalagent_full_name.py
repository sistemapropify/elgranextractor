from django.db import migrations, models


def combine_agent_names(apps, schema_editor):
    ExternalAgent = apps.get_model('external_agents', 'ExternalAgent')
    for agent in ExternalAgent.objects.all().iterator():
        agent.full_name = ' '.join(
            part.strip()
            for part in (
                agent.first_name or '',
                agent.paternal_last_name or '',
                agent.maternal_last_name or '',
            )
            if part.strip()
        )
        agent.save(update_fields=['full_name'])


class Migration(migrations.Migration):

    dependencies = [
        ('external_agents', '0004_externalagent_level'),
    ]

    operations = [
        migrations.AddField(
            model_name='externalagent',
            name='full_name',
            field=models.CharField(
                blank=True,
                db_index=True,
                default='',
                max_length=400,
                verbose_name='Nombre completo',
            ),
            preserve_default=False,
        ),
        migrations.RunPython(combine_agent_names, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='externalagent',
            name='first_name',
        ),
        migrations.RemoveField(
            model_name='externalagent',
            name='paternal_last_name',
        ),
        migrations.RemoveField(
            model_name='externalagent',
            name='maternal_last_name',
        ),
        migrations.AlterModelOptions(
            name='externalagent',
            options={
                'ordering': ['full_name', 'pk'],
                'verbose_name': 'Agente externo',
                'verbose_name_plural': 'Agentes externos',
            },
        ),
    ]
