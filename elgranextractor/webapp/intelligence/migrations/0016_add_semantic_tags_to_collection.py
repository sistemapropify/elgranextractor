"""
Generated manually — Django makemigrations no disponible por
InconsistentMigrationHistory entre admin e intelligence en db 'propifai'.

Agrega el campo semantic_tags al modelo IntelligenceCollection
para etiquetado semántico de colecciones RAG.

Refactor D1 — SPEC: plans/spec_tecnica_propifai_intelligence.md
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('intelligence', '0015_add_database_alias_to_collection'),
    ]

    operations = [
        migrations.AddField(
            model_name='intelligencecollection',
            name='semantic_tags',
            field=models.JSONField(
                default=list,
                blank=True,
                verbose_name='Etiquetas semánticas',
                help_text="Lista de etiquetas semánticas que describen el contenido de la colección. "
                          "Se inyectan en el embedding durante sync para mejorar búsquedas conceptuales. "
                          "Ej: ['terreno', 'construccion', 'educacion', 'comercial', 'vivienda']"
            ),
        ),
    ]
