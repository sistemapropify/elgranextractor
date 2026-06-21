from django.db import models
from django.conf import settings


class PropertyProspect(models.Model):

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
    )

    # ── Foto ────────────────────────────────────────────────────
    photo = models.ImageField(
        upload_to='prospects/photos/%Y/%m/',
        verbose_name='Foto del anuncio',
    )

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
