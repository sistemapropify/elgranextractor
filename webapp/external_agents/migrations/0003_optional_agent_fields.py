import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('external_agents', '0002_default_attachment_type'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='externalagent',
            name='external_agents_unique_person_document',
        ),
        migrations.AlterField(
            model_name='externalagent',
            name='first_name',
            field=models.CharField(
                blank=True,
                max_length=120,
                verbose_name='Nombre',
            ),
        ),
        migrations.AlterField(
            model_name='externalagent',
            name='paternal_last_name',
            field=models.CharField(
                blank=True,
                max_length=120,
                verbose_name='Apellido paterno',
            ),
        ),
        migrations.AlterField(
            model_name='externalagent',
            name='personal_document_type',
            field=models.ForeignKey(
                blank=True,
                limit_choices_to={'scope': 'personal'},
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='agents',
                to='external_agents.documenttype',
                verbose_name='Tipo de documento personal',
            ),
        ),
        migrations.AlterField(
            model_name='externalagent',
            name='document_number',
            field=models.CharField(
                blank=True,
                db_index=True,
                max_length=50,
                verbose_name='Número de documento',
            ),
        ),
        migrations.AlterField(
            model_name='externalagent',
            name='address',
            field=models.CharField(
                blank=True,
                max_length=300,
                verbose_name='Dirección',
            ),
        ),
        migrations.AlterField(
            model_name='externalagent',
            name='email',
            field=models.EmailField(
                blank=True,
                max_length=254,
                verbose_name='Correo electrónico',
            ),
        ),
        migrations.AlterField(
            model_name='externalagent',
            name='mobile',
            field=models.CharField(
                blank=True,
                max_length=30,
                verbose_name='Celular',
            ),
        ),
    ]
