from django.db import models


# ─────────────────────────────────────────────
#  CHOICES
# ─────────────────────────────────────────────

class FuenteChoices(models.TextChoices):
    EXITO        = 'exito_inmobiliario',  'Whatsapp Éxito Inmobiliario'
    UNIDAS       = 'inmobiliarias_unidas', 'Whatsapp Inmobiliarias Unidas'
    RED_INMOBILIARIA = 'red_inmobiliaria', 'WhatsApp Red Inmobiliaria Arequipa'
    OTRO         = 'otro',                'Otro'


class CondicionChoices(models.TextChoices):
    COMPRA          = 'compra',          'Compra'
    ALQUILER        = 'alquiler',        'Alquiler'
    AMBOS           = 'ambos',           'Compra y Alquiler'
    NO_ESPECIFICADO = 'no_especificado', 'No Especificado'


class TipoPropiedadChoices(models.TextChoices):
    DEPARTAMENTO    = 'departamento',    'Departamento'
    CASA            = 'casa',            'Casa'
    TERRENO         = 'terreno',         'Terreno'
    OFICINA         = 'oficina',         'Oficina'
    LOCAL_COMERCIAL = 'local_comercial', 'Local Comercial'
    ALMACEN         = 'almacen',         'Almacén'
    NO_ESPECIFICADO = 'no_especificado', 'No Especificado'


class TipoOriginalChoices(models.TextChoices):
    REQUERIMIENTO        = 'REQUERIMIENTO',                          'Requerimiento'
    REQ_COMPRA           = 'REQUERIMIENTO COMPRA',                   'Requerimiento Compra'
    REQ_ALQUILER         = 'REQUERIMIENTO ALQUILER',                 'Requerimiento Alquiler'
    REQ_COMPRA_ALQUILER  = 'REQUERIMIENTO COMPRA, REQUERIMIENTO ALQUILER', 'Req. Compra + Alquiler'
    REQ_ALQUILER_COMPRA  = 'REQUERIMIENTO ALQUILER, REQUERIMIENTO COMPRA', 'Req. Alquiler + Compra'
    PROPIEDAD_VENTA      = 'PROPIEDAD VENTA',                        'Propiedad en Venta'
    MIXTO                = 'MIXTO',                                  'Mixto'
    BASURA               = 'BASURA',                                 'Basura / Irrelevante'
    OTRO                 = 'OTRO',                                   'Otro'


class MonedaChoices(models.TextChoices):
    USD             = 'USD',             'Dólares (USD)'
    PEN             = 'PEN',             'Soles (PEN)'
    NO_ESPECIFICADO = 'no_especificado', 'No Especificado'


class FormaPagoChoices(models.TextChoices):
    CONTADO         = 'contado',         'Al Contado'
    FINANCIADO      = 'financiado',      'Financiado / Crédito'
    NO_ESPECIFICADO = 'no_especificado', 'No Especificado'


class TernarioChoices(models.TextChoices):
    """Para campos sí / no / indiferente"""
    SI          = 'si',          'Sí'
    NO          = 'no',          'No'
    INDIFERENTE = 'indiferente', 'Indiferente'


# ─────────────────────────────────────────────
#  MODELO PRINCIPAL
# ─────────────────────────────────────────────

class Requerimiento(models.Model):

    # ── Trazabilidad / origen ─────────────────
    fuente = models.CharField(
        max_length=60,
        choices=FuenteChoices.choices,
        default=FuenteChoices.OTRO,
        verbose_name='Grupo WhatsApp',
        help_text='Grupo de WhatsApp de donde proviene el mensaje',
        db_index=True,
    )
    fecha = models.DateField(
        null=True, blank=True,
        verbose_name='Fecha del mensaje',
    )
    hora = models.TimeField(
        null=True, blank=True,
        verbose_name='Hora del mensaje',
    )
    agente = models.CharField(
        max_length=120,
        blank=True,
        verbose_name='Agente',
        help_text='Nombre del agente inmobiliario que publicó el mensaje',
        db_index=True,
    )

    # ── Clasificación original del Excel ──────
    tipo_original = models.CharField(
        max_length=80,
        blank=True,
        verbose_name='Tipo original',
        help_text='Valor tal como venía en la columna "tipo" del Excel exportado',
    )

    # ── Campos extraídos / estructurados ──────
    condicion = models.CharField(
        max_length=20,
        choices=CondicionChoices.choices,
        default=CondicionChoices.NO_ESPECIFICADO,
        verbose_name='Condición',
        help_text='¿El cliente busca comprar o alquilar?',
        db_index=True,
    )
    tipo_propiedad = models.CharField(
        max_length=20,
        choices=TipoPropiedadChoices.choices,
        default=TipoPropiedadChoices.NO_ESPECIFICADO,
        verbose_name='Tipo de propiedad',
        db_index=True,
    )
    distritos = models.CharField(
        max_length=300,
        blank=True,
        verbose_name='Distritos',
        help_text='Uno o varios distritos separados por coma. Ej: Cayma, Yanahuara',
    )

    # ── Presupuesto ───────────────────────────
    presupuesto_monto = models.DecimalField(
        max_digits=12, decimal_places=2,
        null=True, blank=True,
        verbose_name='Presupuesto (monto)',
    )
    presupuesto_moneda = models.CharField(
        max_length=20,
        choices=MonedaChoices.choices,
        default=MonedaChoices.NO_ESPECIFICADO,
        verbose_name='Moneda',
    )
    presupuesto_forma_pago = models.CharField(
        max_length=20,
        choices=FormaPagoChoices.choices,
        default=FormaPagoChoices.NO_ESPECIFICADO,
        verbose_name='Forma de pago',
    )

    # ── Características de la propiedad ──────
    habitaciones = models.PositiveSmallIntegerField(
        null=True, blank=True,
        verbose_name='N° habitaciones',
    )
    banos = models.PositiveSmallIntegerField(
        null=True, blank=True,
        verbose_name='N° baños',
    )
    cochera = models.CharField(
        max_length=12,
        choices=TernarioChoices.choices,
        default=TernarioChoices.INDIFERENTE,
        verbose_name='Cochera',
    )
    ascensor = models.CharField(
        max_length=12,
        choices=TernarioChoices.choices,
        default=TernarioChoices.INDIFERENTE,
        verbose_name='Ascensor',
    )
    amueblado = models.CharField(
        max_length=12,
        choices=TernarioChoices.choices,
        default=TernarioChoices.INDIFERENTE,
        verbose_name='Amueblado',
    )
    area_m2 = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='Área (m²)',
    )
    piso_preferencia = models.CharField(
        max_length=60,
        blank=True,
        verbose_name='Preferencia de piso',
        help_text='Ej: "primer piso", "a partir de piso 3", "piso 5"',
    )

    # ── Características extra (tags libres) ──
    caracteristicas_extra = models.CharField(
        max_length=300,
        blank=True,
        verbose_name='Características extra',
        help_text='Lista separada por coma. Ej: balcón, jardín, URGENTE, seguridad',
    )

    # ── Contacto del agente ───────────────────
    agente_telefono = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Teléfono del agente',
    )

    # ── Mensaje original completo ─────────────
    requerimiento = models.TextField(
        verbose_name='Requerimiento (texto original)',
        help_text='Mensaje completo tal como fue publicado en el grupo de WhatsApp',
    )

    # ── Auditoría ─────────────────────────────
    creado_en = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Creado en',
    )
    actualizado_en = models.DateTimeField(
        auto_now=True,
        verbose_name='Actualizado en',
    )

    # ─────────────────────────────────────────
    class Meta:
        db_table            = 'requerimiento'
        verbose_name        = 'Requerimiento'
        verbose_name_plural = 'Requerimientos'
        ordering            = ['-fecha', '-hora']
        indexes = [
            models.Index(fields=['condicion', 'tipo_propiedad'], name='idx_cond_tipo'),
            models.Index(fields=['fecha'],                        name='idx_fecha'),
            models.Index(fields=['presupuesto_moneda', 'presupuesto_monto'], name='idx_presupuesto'),
        ]

    def __str__(self):
        return (
            f"[{self.get_condicion_display()}] "
            f"{self.get_tipo_propiedad_display()} — "
            f"{self.distritos or 'Sin distrito'} — "
            f"{self.agente}"
        )

    # ── Helpers ───────────────────────────────
    @property
    def es_urgente(self) -> bool:
        return 'URGENTE' in (self.caracteristicas_extra or '').upper()

    @property
    def distritos_lista(self) -> list[str]:
        """Devuelve los distritos como lista Python."""
        if not self.distritos:
            return []
        return [d.strip() for d in self.distritos.split(',') if d.strip()]

    @property
    def presupuesto_display(self) -> str:
        if not self.presupuesto_monto:
            return '—'
        simbolo = '$' if self.presupuesto_moneda == 'USD' else 'S/'
        return f"{simbolo}{self.presupuesto_monto:,.0f}"
