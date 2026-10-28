import django.core.validators
import django.db.models.deletion
from django.db import migrations, models

import external_agents.storage


def create_default_document_types(apps, schema_editor):
    DocumentType = apps.get_model('external_agents', 'DocumentType')
    for order, name in enumerate(('DNI', 'Pasaporte'), start=1):
        DocumentType.objects.get_or_create(
            scope='personal',
            name=name,
            defaults={'sort_order': order},
        )


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='DocumentType',
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
                ('name', models.CharField(max_length=80, verbose_name='Nombre')),
                (
                    'scope',
                    models.CharField(
                        choices=[
                            ('personal', 'Datos personales'),
                            ('attachment', 'Documento adjunto'),
                        ],
                        db_index=True,
                        max_length=20,
                        verbose_name='Categoría',
                    ),
                ),
                (
                    'is_active',
                    models.BooleanField(
                        db_index=True,
                        default=True,
                        verbose_name='Activo',
                    ),
                ),
                (
                    'sort_order',
                    models.PositiveSmallIntegerField(
                        default=0,
                        verbose_name='Orden',
                    ),
                ),
                (
                    'created_by_username',
                    models.CharField(
                        blank=True,
                        max_length=150,
                        verbose_name='Creado por',
                    ),
                ),
                (
                    'created_at',
                    models.DateTimeField(
                        auto_now_add=True,
                        verbose_name='Creado el',
                    ),
                ),
                (
                    'updated_at',
                    models.DateTimeField(
                        auto_now=True,
                        verbose_name='Actualizado el',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Tipo de documento',
                'verbose_name_plural': 'Tipos de documento',
                'db_table': 'external_agents_documenttype',
                'ordering': ['scope', 'sort_order', 'name', 'pk'],
            },
        ),
        migrations.CreateModel(
            name='ExternalAgent',
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
                ('first_name', models.CharField(max_length=120, verbose_name='Nombre')),
                (
                    'paternal_last_name',
                    models.CharField(
                        max_length=120,
                        verbose_name='Apellido paterno',
                    ),
                ),
                (
                    'maternal_last_name',
                    models.CharField(
                        blank=True,
                        max_length=120,
                        verbose_name='Apellido materno',
                    ),
                ),
                (
                    'document_number',
                    models.CharField(
                        db_index=True,
                        max_length=50,
                        verbose_name='Número de documento',
                    ),
                ),
                (
                    'address',
                    models.CharField(max_length=300, verbose_name='Dirección'),
                ),
                (
                    'email',
                    models.EmailField(
                        max_length=254,
                        verbose_name='Correo electrónico',
                    ),
                ),
                ('mobile', models.CharField(max_length=30, verbose_name='Celular')),
                (
                    'is_active',
                    models.BooleanField(
                        db_index=True,
                        default=True,
                        verbose_name='Activo',
                    ),
                ),
                (
                    'created_by_username',
                    models.CharField(
                        blank=True,
                        max_length=150,
                        verbose_name='Registrado por',
                    ),
                ),
                (
                    'updated_by_username',
                    models.CharField(
                        blank=True,
                        max_length=150,
                        verbose_name='Actualizado por',
                    ),
                ),
                (
                    'created_at',
                    models.DateTimeField(
                        auto_now_add=True,
                        verbose_name='Creado el',
                    ),
                ),
                (
                    'updated_at',
                    models.DateTimeField(
                        auto_now=True,
                        verbose_name='Actualizado el',
                    ),
                ),
                (
                    'personal_document_type',
                    models.ForeignKey(
                        limit_choices_to={'scope': 'personal'},
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='agents',
                        to='external_agents.documenttype',
                        verbose_name='Tipo de documento personal',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Agente externo',
                'verbose_name_plural': 'Agentes externos',
                'db_table': 'external_agents_agent',
                'ordering': [
                    'paternal_last_name',
                    'maternal_last_name',
                    'first_name',
                    'pk',
                ],
            },
        ),
        migrations.CreateModel(
            name='ExternalAgentAttachment',
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
                    'file',
                    models.FileField(
                        storage=external_agents.storage.ExternalAgentDocumentStorage(),
                        upload_to='agentes-externos/%Y/%m/',
                        validators=[
                            django.core.validators.FileExtensionValidator(
                                ['pdf', 'png', 'jpg', 'jpeg', 'webp']
                            )
                        ],
                        verbose_name='Archivo',
                    ),
                ),
                (
                    'original_name',
                    models.CharField(
                        blank=True,
                        max_length=255,
                        verbose_name='Nombre original',
                    ),
                ),
                (
                    'uploaded_by_username',
                    models.CharField(
                        blank=True,
                        max_length=150,
                        verbose_name='Subido por',
                    ),
                ),
                (
                    'created_at',
                    models.DateTimeField(
                        auto_now_add=True,
                        verbose_name='Subido el',
                    ),
                ),
                (
                    'agent',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='attachments',
                        to='external_agents.externalagent',
                        verbose_name='Agente',
                    ),
                ),
                (
                    'document_type',
                    models.ForeignKey(
                        limit_choices_to={'scope': 'attachment'},
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='attachments',
                        to='external_agents.documenttype',
                        verbose_name='Tipo de documento',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Documento adjunto',
                'verbose_name_plural': 'Documentos adjuntos',
                'db_table': 'external_agents_attachment',
                'ordering': ['-created_at', '-pk'],
            },
        ),
        migrations.AddConstraint(
            model_name='documenttype',
            constraint=models.UniqueConstraint(
                fields=('scope', 'name'),
                name='external_agents_unique_document_type',
            ),
        ),
        migrations.AddConstraint(
            model_name='externalagent',
            constraint=models.UniqueConstraint(
                fields=('personal_document_type', 'document_number'),
                name='external_agents_unique_person_document',
            ),
        ),
        migrations.RunPython(
            create_default_document_types,
            migrations.RunPython.noop,
        ),
    ]
