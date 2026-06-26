# Generated manually - adds es_nuevo and score_anterior fields to MatchResult

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('matching', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='matchresult',
            name='es_nuevo',
            field=models.BooleanField(
                default=True,
                help_text='True si este match apareció en la última ejecución de matching',
                verbose_name='Match nuevo',
            ),
        ),
        migrations.AddField(
            model_name='matchresult',
            name='score_anterior',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Score previo si este match fue actualizado en una ejecución posterior',
                max_digits=5,
                null=True,
                verbose_name='Score anterior',
            ),
        ),
    ]
