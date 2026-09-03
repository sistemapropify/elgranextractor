from django.db import models
from django.conf import settings


class MobileAppVersion(models.Model):
    version_code = models.PositiveBigIntegerField(unique=True, verbose_name='Version code')
    version_name = models.CharField(max_length=50, blank=True, verbose_name='Versión')
    download_url = models.URLField(max_length=1000, verbose_name='URL del APK')
    sha256 = models.CharField(max_length=64, blank=True, verbose_name='SHA-256')
    min_supported_version_code = models.PositiveBigIntegerField(default=1)
    force_update = models.BooleanField(default=False, verbose_name='Actualización obligatoria')
    published = models.BooleanField(default=False, verbose_name='Publicada')
    release_notes = models.TextField(blank=True, verbose_name='Notas de versión')
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-version_code']
        verbose_name = 'Versión de propitools'
        verbose_name_plural = 'Versiones de propitools'


class MobileProspectUser(models.Model):
    """Identidad de Propify usada por el módulo de prospección.

    No es un usuario de Prometeo. Solo conserva la referencia mínima necesaria
    para asociar capturas realizadas desde la APK o desde la vista web.
    """

    username = models.CharField(max_length=150, unique=True)
    propify_user_id = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    can_view_crm_alerts = models.BooleanField(
        default=False,
        verbose_name='Supervisor de alertas CRM',
    )

    def __str__(self):
        return self.username


class MobileProspectSession(models.Model):
    """Sesiones antiguas conservadas solo por compatibilidad de esquema."""

    user = models.ForeignKey(MobileProspectUser, on_delete=models.CASCADE, related_name='sessions')
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(auto_now=True)


class CrmVisitIntentAlert(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendiente'
        FOLLOW_UP = 'follow_up', 'Seguimiento'
        CLOSED = 'closed', 'Cerrada'

    source_lead_id = models.BigIntegerField(db_index=True)
    agent_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    agent_name = models.CharField(max_length=200, blank=True)
    contact_name = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    property_id = models.BigIntegerField(null=True, blank=True)
    property_code = models.CharField(max_length=100, blank=True)
    property_title = models.CharField(max_length=300, blank=True)
    evidence = models.JSONField(default=list)
    detected_at = models.DateTimeField(db_index=True)
    responded_at = models.DateTimeField(null=True, blank=True, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-detected_at']
        constraints = [
            models.UniqueConstraint(
                fields=['source_lead_id', 'detected_at'],
                name='unique_crm_visit_intent_alert',
            )
        ]


class MobileNotificationDevice(models.Model):
    class TargetType(models.TextChoices):
        FID = 'fid', 'Firebase Installation ID'
        TOKEN = 'token', 'Token heredado'

    user = models.ForeignKey(
        MobileProspectUser,
        on_delete=models.CASCADE,
        related_name='notification_devices',
    )
    registration_id = models.CharField(max_length=512, unique=True)
    target_type = models.CharField(
        max_length=10,
        choices=TargetType.choices,
        default=TargetType.FID,
    )
    device_name = models.CharField(max_length=200, blank=True)
    active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class PropertyProspect(models.Model):
    ORIGIN_CHOICES = [('marketplace', 'Marketplace'), ('calle', 'Calle'), ('otros', 'Otros')]
    CONTRACT_CHOICES = [('trato_directo', 'Trato directo'), ('inmobiliaria', 'Inmobiliaria')]

    OPERATION_CHOICES = [
        ('alquiler', 'Alquiler'),
        ('venta', 'Venta'),
    ]

    PROPERTY_TYPES = [
        ('departamento', 'Departamento'),
        ('casa', 'Casa'),
        ('local', 'Local comercial'),
        ('terreno', 'Terreno'),
        ('oficina', 'Oficina'),
        ('otro', 'Otro'),
    ]

    STATUS_CHOICES = [
        ('borrador', 'Borrador'),        # foto guardada, sin procesar
        ('pendiente', 'Pendiente'),      # OCR procesado, sin contactar
        ('contactado', 'Contactado'),
        ('negociando', 'Negociando'),
        ('captado', 'Captado'),          # propiedad dentro de cartera
        ('descartado', 'Descartado'),
    ]

    CURRENCY_CHOICES = [
        ('USD', 'USD'),
        ('PEN', 'PEN (Soles)'),
    ]

    # ── Relaciones ──────────────────────────────────────────────
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='prospects',
        verbose_name='Agente',
        null=True,
        blank=True,
    )
    mobile_user = models.ForeignKey(
        MobileProspectUser,
        on_delete=models.SET_NULL,
        related_name='prospects',
        null=True,
        blank=True,
        verbose_name='Usuario móvil',
    )

    # ── Foto ────────────────────────────────────────────────────
    photo = models.ImageField(
        upload_to='prospects/photos/%Y/%m/',
        blank=True,
        verbose_name='Foto del anuncio',
    )
    # Esta columna ya existe en la base compartida por la migración de la APK.
    # También debe estar en el modelo web para que el INSERT nunca envíe NULL.
    captured_by_username = models.CharField(
        max_length=150,
        blank=True,
        db_index=True,
        verbose_name='Usuario que realizó la captura',
    )
    origin = models.CharField(max_length=20, choices=ORIGIN_CHOICES, blank=True, verbose_name='Origen')
    origin_other = models.CharField(max_length=120, blank=True, verbose_name='Otro origen')
    marketplace_url = models.URLField(max_length=500, blank=True, verbose_name='Enlace Marketplace')

    # ── GPS (solo coordenadas — dirección se llena manual) ───────
    latitude = models.DecimalField(
        max_digits=10, decimal_places=7,
        null=True, blank=True,
        verbose_name='Latitud',
    )
    longitude = models.DecimalField(
        max_digits=10, decimal_places=7,
        null=True, blank=True,
        verbose_name='Longitud',
    )
    # Dirección legible: manzana, lote, calle — ingresada manualmente
    address = models.CharField(
        max_length=300, blank=True,
        verbose_name='Dirección (Mz/Lote/Calle)',
        help_text='Ej: Mz. D Lote 12, Urb. La Encalada',
    )
    zone = models.CharField(max_length=150, blank=True, verbose_name='Zona')
    district = models.CharField(
        max_length=100, blank=True,
        verbose_name='Distrito',
    )

    # ── Datos extraídos por IA (todos editables) ─────────────────
    owner_name = models.CharField(
        max_length=200, blank=True,
        verbose_name='Nombre propietario',
    )
    phone = models.CharField(
        max_length=30, blank=True,
        verbose_name='Teléfono',
    )
    operation_type = models.CharField(
        max_length=20, choices=OPERATION_CHOICES,
        blank=True, verbose_name='Operación',
    )
    contract_type = models.CharField(max_length=20, choices=CONTRACT_CHOICES, blank=True, verbose_name='Tipo de contrato')
    property_type = models.CharField(
        max_length=20, choices=PROPERTY_TYPES,
        blank=True, verbose_name='Tipo de inmueble',
    )
    price = models.DecimalField(
        max_digits=12, decimal_places=2,
        null=True, blank=True,
        verbose_name='Precio',
    )
    currency = models.CharField(
        max_length=5, choices=CURRENCY_CHOICES,
        default='USD', verbose_name='Moneda',
    )
    bedrooms = models.PositiveSmallIntegerField(
        null=True, blank=True,
        verbose_name='Dormitorios',
    )
    area_m2 = models.DecimalField(
        max_digits=8, decimal_places=2,
        null=True, blank=True,
        verbose_name='Área m²',
    )

    # ── OCR metadata ────────────────────────────────────────────
    ocr_raw_text = models.TextField(
        blank=True,
        verbose_name='Texto extraído (raw)',
    )
    ocr_processed_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Procesado con IA el',
    )

    # ── Estado y notas ───────────────────────────────────────────
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES,
        default='borrador', verbose_name='Estado',
    )
    notes = models.TextField(
        blank=True,
        verbose_name='Notas del agente',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Prospecto'
        verbose_name_plural = 'Prospectos'
        ordering = ['-created_at']

    def __str__(self):
        return f"Prospecto #{self.pk} — {self.district or 'Sin distrito'} ({self.get_status_display()})"

    @property
    def has_gps(self):
        return self.latitude is not None and self.longitude is not None

    @property
    def ocr_done(self):
        return bool(self.ocr_processed_at)

    @property
    def coords_display(self):
        if self.has_gps:
            return f"{self.latitude}, {self.longitude}"
        return "Sin coordenadas"
