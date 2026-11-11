from pathlib import Path

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

    class Level(models.TextChoices):
        TRAINING = 'training', 'Training'
        JUNIOR = 'junior', 'Junior'
        SENIOR = 'senior', 'Senior'

    full_name = models.CharField(
        max_length=400,
        blank=True,
        db_index=True,
        verbose_name='Nombre completo',
    )
    personal_document_type = models.ForeignKey(
        DocumentType,
        on_delete=models.PROTECT,
        related_name='agents',
        limit_choices_to={'scope': DocumentType.Scope.PERSONAL},
        null=True,
        blank=True,
        verbose_name='Tipo de documento personal',
    )
    document_number = models.CharField(
        max_length=50,
        blank=True,
        db_index=True,
        verbose_name='Número de documento',
    )
    address = models.CharField(
        max_length=300,
        blank=True,
        verbose_name='Dirección',
    )
    observations = models.TextField(
        blank=True,
        default='',
        verbose_name='Observaciones',
    )
    email = models.EmailField(blank=True, verbose_name='Correo electrónico')
    mobile = models.CharField(
        max_length=30,
        blank=True,
        verbose_name='Celular',
    )
    level = models.CharField(
        max_length=20,
        choices=Level.choices,
        blank=True,
        db_index=True,
        verbose_name='Nivel',
    )
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
        ordering = ['full_name', 'pk']
        verbose_name = 'Agente externo'
        verbose_name_plural = 'Agentes externos'

    @property
    def display_name(self):
        return (
            (self.full_name or '').strip()
            or (f'Agente externo #{self.pk}' if self.pk else 'Agente externo')
        )

    @property
    def initials(self):
        letters = [
            word[:1] for word in (self.full_name or '').split()[:2]
            if word
        ]
        return ''.join(letter.upper() for letter in letters if letter) or 'AE'

    def __str__(self):
        return self.display_name


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

    @property
    def display_name(self):
        return self.original_name or Path(self.file.name).name

    @property
    def extension(self):
        return Path(self.file.name).suffix.lstrip('.').upper() or 'ARCHIVO'

    @property
    def is_image(self):
        return Path(self.file.name).suffix.lower() in {
            '.png', '.jpg', '.jpeg', '.webp',
        }
