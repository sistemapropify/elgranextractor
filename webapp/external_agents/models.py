from django.core.validators import FileExtensionValidator
from django.db import models

from .storage import ExternalAgentDocumentStorage


class DocumentType(models.Model):
    """Catálogo configurable, separado por su uso funcional."""

    class Scope(models.TextChoices):
        PERSONAL = 'personal', 'Datos personales'
        ATTACHMENT = 'attachment', 'Documento adjunto'

    name = models.CharField(max_length=80, verbose_name='Nombre')
    scope = models.CharField(
        max_length=20,
        choices=Scope.choices,
        db_index=True,
        verbose_name='Categoría',
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name='Activo',
    )
    sort_order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Orden',
    )
    created_by_username = models.CharField(
        max_length=150,
        blank=True,
        verbose_name='Creado por',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Creado el')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Actualizado el')

    class Meta:
        db_table = 'external_agents_documenttype'
        ordering = ['scope', 'sort_order', 'name', 'pk']
        verbose_name = 'Tipo de documento'
        verbose_name_plural = 'Tipos de documento'
        constraints = [
            models.UniqueConstraint(
                fields=['scope', 'name'],
                name='external_agents_unique_document_type',
            ),
        ]

    def __str__(self):
        return f'{self.name} · {self.get_scope_display()}'


class ExternalAgent(models.Model):
    """Agente inmobiliario externo registrado por el equipo Propify."""

    first_name = models.CharField(max_length=120, verbose_name='Nombre')
    paternal_last_name = models.CharField(
        max_length=120,
        verbose_name='Apellido paterno',
    )
    maternal_last_name = models.CharField(
        max_length=120,
        blank=True,
        verbose_name='Apellido materno',
    )
    personal_document_type = models.ForeignKey(
        DocumentType,
        on_delete=models.PROTECT,
        related_name='agents',
        limit_choices_to={'scope': DocumentType.Scope.PERSONAL},
        verbose_name='Tipo de documento personal',
    )
    document_number = models.CharField(
        max_length=50,
        db_index=True,
        verbose_name='Número de documento',
    )
    address = models.CharField(max_length=300, verbose_name='Dirección')
    email = models.EmailField(verbose_name='Correo electrónico')
    mobile = models.CharField(max_length=30, verbose_name='Celular')
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name='Activo',
    )
    created_by_username = models.CharField(
        max_length=150,
        blank=True,
        verbose_name='Registrado por',
    )
    updated_by_username = models.CharField(
        max_length=150,
        blank=True,
        verbose_name='Actualizado por',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Creado el')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Actualizado el')

    class Meta:
        db_table = 'external_agents_agent'
        ordering = ['paternal_last_name', 'maternal_last_name', 'first_name', 'pk']
        verbose_name = 'Agente externo'
        verbose_name_plural = 'Agentes externos'
        constraints = [
            models.UniqueConstraint(
                fields=['personal_document_type', 'document_number'],
                name='external_agents_unique_person_document',
            ),
        ]

    @property
    def full_name(self):
        return ' '.join(
            part for part in (
                self.first_name,
                self.paternal_last_name,
                self.maternal_last_name,
            ) if part
        ).strip()

    @property
    def initials(self):
        letters = [
            (self.first_name or '').strip()[:1],
            (self.paternal_last_name or '').strip()[:1],
        ]
        return ''.join(letter.upper() for letter in letters if letter) or 'AE'

    def __str__(self):
        return self.full_name


class ExternalAgentAttachment(models.Model):
    """Documento digital asociado a un agente externo."""

    agent = models.ForeignKey(
        ExternalAgent,
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name='Agente',
    )
    document_type = models.ForeignKey(
        DocumentType,
        on_delete=models.PROTECT,
        related_name='attachments',
        limit_choices_to={'scope': DocumentType.Scope.ATTACHMENT},
        verbose_name='Tipo de documento',
    )
    file = models.FileField(
        upload_to='agentes-externos/%Y/%m/',
        storage=ExternalAgentDocumentStorage(),
        validators=[
            FileExtensionValidator(['pdf', 'png', 'jpg', 'jpeg', 'webp']),
        ],
        verbose_name='Archivo',
    )
    original_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Nombre original',
    )
    uploaded_by_username = models.CharField(
        max_length=150,
        blank=True,
        verbose_name='Subido por',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Subido el')

    class Meta:
        db_table = 'external_agents_attachment'
        ordering = ['-created_at', '-pk']
        verbose_name = 'Documento adjunto'
        verbose_name_plural = 'Documentos adjuntos'

    def __str__(self):
        return self.original_name or self.file.name
