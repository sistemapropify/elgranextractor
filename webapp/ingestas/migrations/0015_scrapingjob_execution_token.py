from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('ingestas', '0014_scrapingjob_scrapinglog'),
    ]

    operations = [
        migrations.AddField(
            model_name='scrapingjob',
            name='execution_token',
            field=models.UUIDField(
                blank=True,
                db_index=True,
                editable=False,
                help_text='Impide que un proceso huérfano siga escribiendo tras una reanudación.',
                null=True,
                verbose_name='Token de ejecución',
            ),
        ),
    ]
