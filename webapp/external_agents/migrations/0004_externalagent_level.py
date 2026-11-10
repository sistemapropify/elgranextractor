from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('external_agents', '0003_optional_agent_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='externalagent',
            name='level',
            field=models.CharField(
                blank=True,
                choices=[
                    ('training', 'Training'),
                    ('junior', 'Junior'),
                    ('senior', 'Senior'),
                ],
                db_index=True,
                max_length=20,
                verbose_name='Nivel',
            ),
        ),
    ]
