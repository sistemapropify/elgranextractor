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


class CommissionPayment(models.Model):
    """Pago de comisión generado desde un cierre de Propify.

    Se registra de forma local en Prometeo para no escribir en la base de
    Propify. Cada fila corresponde a un pago a Propify, al agente vendedor o
    al agente comprador, y mantiene su estado de conciliación.
    """

    class BeneficiaryType(models.TextChoices):
        PROPIFFY = 'propify', 'Propify'
        SELLER = 'agente_vendedor', 'Agente vendedor'
        BUYER = 'agente_comprador', 'Agente comprador'
        OTHER = 'otro', 'Otro'

    class Status(models.TextChoices):
        PENDING = 'pendiente', 'Pendiente'
        PAID = 'pagado', 'Pagado'
        ANNULLED = 'anulado', 'Anulado'

    operation_code = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        verbose_name='Código de operación',
    )
    property_name = models.CharField(
        max_length=300,
        blank=True,
        verbose_name='Propiedad',
    )
    beneficiary_type = models.CharField(
        max_length=30,
        choices=BeneficiaryType.choices,
        db_index=True,
        verbose_name='Tipo de beneficiario',
    )
    beneficiary_name = models.CharField(
        max_length=300,
        blank=True,
        verbose_name='Beneficiario',
    )
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name='Importe a pagar',
    )
    currency_code = models.CharField(
        max_length=3,
        default='USD',
        verbose_name='Moneda',
    )
    due_date = models.DateField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name='Fecha de vencimiento',
    )
    payment_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Fecha de pago',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name='Estado',
    )
    payment_method = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Medio de pago',
    )
    account = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Cuenta de salida',
    )
    voucher = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Comprobante',
    )
    approved_by = models.CharField(
        max_length=150,
        blank=True,
        verbose_name='Aprobado por',
    )
    notes = models.TextField(
        blank=True,
        default='',
        verbose_name='Observaciones',
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
        db_table = 'external_agents_commission_payment'
        ordering = ['-due_date', '-pk']
        verbose_name = 'Pago de comisión'
        verbose_name_plural = 'Pagos de comisiones'

    def __str__(self):
        return f'{self.operation_code} · {self.get_beneficiary_type_display()}'


class CommissionCollection(models.Model):
    """Cobro por comisión detectado desde un cierre de Propify.

    Representa el monto que el propietario debe pagar a Propify por la
    comisión del cierre. Se sincroniza al leer los cierres y guarda el avance
    de cobranza de forma local en Prometeo.
    """

    class Status(models.TextChoices):
        PENDING = 'pendiente', 'Pendiente'
        PARTIAL = 'parcial', 'Parcial'
        COLLECTED = 'cobrado', 'Cobrado'

    operation_code = models.CharField(
        max_length=100,
        db_index=True,
        unique=True,
        verbose_name='Código de operación',
    )
    property_name = models.CharField(
        max_length=300,
        blank=True,
        verbose_name='Propiedad',
    )
    amount_to_collect = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        verbose_name='Monto a cobrar al propietario',
    )
    collected_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        verbose_name='Monto cobrado',
    )
    amount_for_agents = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        verbose_name='Comisión para agentes',
    )
    amount_for_brokers = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        verbose_name='Comisión para brokers',
    )
    amount_for_propify = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        verbose_name='Comisión para Propify',
    )
    currency_code = models.CharField(
        max_length=3,
        default='USD',
        verbose_name='Moneda',
    )
    closing_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Fecha de cierre',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name='Estado',
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
        db_table = 'external_agents_commission_collection'
        ordering = ['-closing_date', '-pk']
        verbose_name = 'Cobro de comisión'
        verbose_name_plural = 'Cobros de comisiones'

    def __str__(self):
        return f'{self.operation_code} · {self.get_status_display()}'


class CommissionCollectionEntry(models.Model):
    """Abono recibido del propietario para una comisión de cierre."""

    collection = models.ForeignKey(
        CommissionCollection,
        on_delete=models.CASCADE,
        related_name='entries',
        verbose_name='Cobro de comisión',
    )
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name='Importe recibido',
    )
    collection_date = models.DateField(
        db_index=True,
        verbose_name='Fecha del abono',
    )
    payment_method = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Medio de pago',
    )
    account = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Cuenta de destino',
    )
    voucher = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Comprobante',
    )
    notes = models.TextField(
        blank=True,
        default='',
        verbose_name='Observaciones',
    )
    registered_by_username = models.CharField(
        max_length=150,
        blank=True,
        verbose_name='Registrado por',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Creado el')

    class Meta:
        db_table = 'external_agents_commission_collection_entry'
        ordering = ['-collection_date', '-pk']
        verbose_name = 'Abono de comisión'
        verbose_name_plural = 'Abonos de comisiones'

    def __str__(self):
        return f'{self.collection.operation_code} · {self.amount}'


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
