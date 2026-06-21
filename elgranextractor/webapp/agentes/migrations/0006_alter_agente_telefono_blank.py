# Generated manually - make telefono field optional (blank=True)
# Allows creating agents without a phone number

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agentes', '0005_agente_foto_perfil_agente_tiktok_url'),
    ]

    operations = [
        migrations.AlterField(
            model_name='agente',
            name='telefono',
            field=models.CharField(
                blank=True,
                help_text='Número de contacto del agente (formato E.164: +51999888777)',
                max_length=20,
                verbose_name='Teléfono',
            ),
        ),
    ]
