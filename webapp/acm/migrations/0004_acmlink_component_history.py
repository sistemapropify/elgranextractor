from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('acm', '0003_acmtestproperty')]

    operations = [
        migrations.AlterField(
            model_name='acmlink',
            name='origen',
            field=models.CharField(
                choices=[
                    ('pdf', 'Generar PDF'),
                    ('compartir', 'Compartir WhatsApp'),
                    ('ambos', 'Ambos'),
                    ('componentes', 'ACM por componentes'),
                ],
                default='compartir', max_length=20,
                verbose_name='Origen del guardado',
            ),
        ),
        migrations.AddField(
            model_name='acmlink', name='metodo',
            field=models.CharField(
                choices=[('clasico', 'ACM clásico'), ('componentes', 'Suelo + construcción y mejoras')],
                default='clasico', max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='acmlink', name='parametros_json',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='acmlink', name='resultado_json',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='acmlink', name='selection_fingerprint',
            field=models.CharField(blank=True, db_index=True, max_length=64, null=True),
        ),
    ]
