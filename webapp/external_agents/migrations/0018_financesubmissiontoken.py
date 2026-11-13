from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('external_agents', '0017_clean_seal_recurring_duplicates'),
    ]

    operations = [
        migrations.CreateModel(
            name='FinanceSubmissionToken',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                (
                    'token',
                    models.CharField(
                        max_length=64,
                        unique=True,
                        verbose_name='Token',
                    ),
                ),
                (
                    'operation',
                    models.CharField(
                        db_index=True,
                        max_length=80,
                        verbose_name='Operación',
                    ),
                ),
                (
                    'actor_username',
                    models.CharField(
                        blank=True,
                        max_length=150,
                        verbose_name='Usuario',
                    ),
                ),
                (
                    'created_at',
                    models.DateTimeField(
                        auto_now_add=True,
                        db_index=True,
                    ),
                ),
            ],
            options={
                'verbose_name': 'Token de envío financiero',
                'verbose_name_plural': 'Tokens de envío financiero',
                'db_table': 'external_agents_finance_submission_token',
                'ordering': ['-created_at', '-pk'],
            },
        ),
    ]
