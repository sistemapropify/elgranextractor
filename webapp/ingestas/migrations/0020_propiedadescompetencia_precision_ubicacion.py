from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ingestas', '0019_scraping_history_repair'),
    ]

    operations = [
        migrations.AddField(
            model_name='propiedadescompetencia',
            name='precision_ubicacion',
            field=models.CharField(
                choices=[('exacta', 'Exacta'), ('aproximada', 'Aproximada'),
                         ('desconocida', 'Desconocida')],
                db_index=True,
                default='desconocida',
                help_text='exacta, aproximada o desconocida (si el anunciante ocultó la dirección)',
                max_length=12,
                verbose_name='Precisión de ubicación',
            ),
        ),
    ]
