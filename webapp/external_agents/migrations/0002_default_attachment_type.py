from django.db import migrations


def create_default_attachment_type(apps, schema_editor):
    DocumentType = apps.get_model('external_agents', 'DocumentType')
    DocumentType.objects.get_or_create(
        scope='attachment',
        name='Documento general',
        defaults={'sort_order': 100},
    )


class Migration(migrations.Migration):

    dependencies = [
        ('external_agents', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            create_default_attachment_type,
            migrations.RunPython.noop,
        ),
    ]
