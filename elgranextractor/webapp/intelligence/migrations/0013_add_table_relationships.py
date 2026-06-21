from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('intelligence', '0012_add_conversation_flows'),
    ]

    operations = [
        migrations.AddField(
            model_name='intelligencecollection',
            name='table_relationships',
            field=models.JSONField(
                default=list,
                verbose_name='Relaciones entre tablas',
                help_text="Lista de relaciones FK para resolver durante sync: [{'foreign_key_field': 'district_fk_id', 'referenced_table': 'districts', 'referenced_display_fields': ['name'], 'label': 'Distrito'}]"
            ),
        ),
    ]
