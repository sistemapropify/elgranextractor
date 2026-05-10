# Generated manually para evitar InconsistentMigrationHistory
# Agrega FK a ExtractorLog en modelo Requerimiento

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp_extractor', '0003_refactor_camino1_export_manual'),
        ('requerimientos', '0004_add_fuente_red_inmobiliaria'),
    ]

    operations = [
        migrations.AddField(
            model_name='requerimiento',
            name='extractor_log',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='requerimientos_generados',
                to='whatsapp_extractor.extractorlog',
                verbose_name='Log de extracción',
                help_text='Log de extracción WhatsApp que originó este requerimiento',
            ),
        ),
    ]
