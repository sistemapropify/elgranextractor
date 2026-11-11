from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('external_agents', '0005_externalagent_full_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='externalagent',
            name='observations',
            field=models.TextField(
                blank=True,
                default='',
                verbose_name='Observaciones',
            ),
        ),
    ]
