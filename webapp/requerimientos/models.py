from django.db import models


# ─────────────────────────────────────────────
#  CHOICES
# ─────────────────────────────────────────────

class FuenteChoices(models.TextChoices):
    EXITO        = 'exito_inmobiliario',  'Whatsapp Éxito Inmobiliario'
    UNIDAS       = 'inmobiliarias_unidas', 'Whatsapp Inmobiliarias Unidas'
    RED_INMOBILIARIA = 'red_inmobiliaria', 'WhatsApp Red Inmobiliaria Arequipa'
    # Nuevos grupos WhatsApp para extracción automática
    GRUPO_NUEVO_1 = 'grupo_whatsapp_1',  'Grupo WhatsApp Inmobiliario 1'
    GRUPO_NUEVO_2 = 'grupo_whatsapp_2',  'Grupo WhatsApp Inmobiliario 2'
    GRUPO_NUEVO_3 = 'grupo_whatsapp_3',  'Grupo WhatsApp Inmobiliario 3'
    OTRO         = 'otro',                'Otro'


class CondicionChoices(models.TextChoices):
    COMPRA          = 'compra',          'Compra'
    ALQUILER        = 'alquiler',        'Alquiler'
    ANTICRESIS      = 'anticresis',      'Anticresis'
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
    extractor_log = models.ForeignKey(
        'whatsapp_extractor.ExtractorLog',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Log de extracción',
        help_text='Log de extracción WhatsApp que originó este requerimiento',
        related_name='requerimientos_generados',
    )
    fuente = models.CharField(
        max_length=60,
        default=FuenteChoices.OTRO,
        verbose_name='Grupo WhatsApp',
        help_text='Grupo de WhatsApp de donde proviene el mensaje (nombre real del grupo)',
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

    # ── Ubicación específica ──────────────────
    urbanizacion = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Urbanización',
        help_text='Nombre de la urbanización o residencial',
    )
    zona = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='Zona / Calles / Edificio',
        help_text='Calles específicas, nombres de edificios o referencias, separados por coma',
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

    # ── Verificación / Revisión ────────────────
    verificado = models.BooleanField(
        default=False,
        verbose_name='Verificado',
        help_text='Marcar como TRUE cuando el requerimiento haya sido revisado manualmente',
    )

    # ── Quality Score (persistente) ────────────
    quality_score = models.DecimalField(
        max_digits=5, decimal_places=1,
        null=True, blank=True,
        verbose_name='Score de calidad',
        help_text='Score total de calidad (0-100). Se recalcula automáticamente.',
    )
    quality_nivel = models.CharField(
        max_length=20,
        null=True, blank=True,
        verbose_name='Nivel de calidad',
        help_text='Excelente/Bueno/Regular/Malo',
    )
    quality_detalle = models.JSONField(
        null=True, blank=True,
        verbose_name='Detalle de calidad',
        help_text='Desglose de dimensiones: completitud, especificidad, presupuesto, antigüedad',
    )
    quality_actualizado_en = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Quality Score actualizado en',
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

    def recalcular_quality_score(self, config=None, guardar=True):
        """
        Recalcula y persiste el Quality Score en los campos del modelo.
        
        Args:
            config: Dict de configuración (opcional, usa la activa o defaults)
            guardar: Si True, hace save() después de actualizar los campos
        
        Returns:
            dict: Resultado del cálculo completo
        """
        from .analytics import calcular_quality_score
        from django.utils import timezone
        
        resultado = calcular_quality_score(self, config)
        
        self.quality_score = resultado['score']
        self.quality_nivel = resultado['nivel']
        self.quality_detalle = resultado['dimensiones']
        self.quality_actualizado_en = timezone.now()
        
        if guardar:
            self.save(update_fields=['quality_score', 'quality_nivel', 'quality_detalle', 'quality_actualizado_en'])
        
        return resultado

    @property
    def quality_score_cached(self) -> dict:
        """
        Retorna el Quality Score desde los campos persistidos.
        Si no está calculado, lo calcula y guarda.
        """
        if self.quality_score is not None and self.quality_detalle is not None:
            return {
                'score': float(self.quality_score),
                'nivel': self.quality_nivel,
                'dimensiones': self.quality_detalle,
            }
        return self.recalcular_quality_score()


class ZonaCalle(models.Model):
    """
    Tabla de Zonas y Calles extraídas de los requerimientos.
    Cada tag del campo 'zona' de Requerimiento se guarda aquí como registro único.
    Sirve como fuente de autocomplete al escribir nuevas zonas/calles.
    """
    nombre = models.CharField(
        max_length=200,
        unique=True,
        verbose_name='Nombre de zona/calle',
        help_text='Nombre de la zona, calle, edificio o referencia',
        db_index=True,
    )
    veces_usado = models.PositiveIntegerField(
        default=1,
        verbose_name='Veces usado',
        help_text='Contador de cuántas veces aparece este tag en requerimientos',
    )
    creado_en = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Creado en',
    )
    actualizado_en = models.DateTimeField(
        auto_now=True,
        verbose_name='Actualizado en',
    )

    class Meta:
        db_table = 'zona_calle'
        verbose_name = 'Zona / Calle'
        verbose_name_plural = 'Zonas y Calles'
        ordering = ['-veces_usado', 'nombre']

    def __str__(self):
        return self.nombre


# ─────────────────────────────────────────────
#  CONFIGURACIÓN DE CALIDAD
# ─────────────────────────────────────────────

CONFIG_CALIDAD_DEFAULT = {
    'pesos_dimensiones': {
        'completitud': 35,
        'especificidad': 25,
        'presupuesto': 25,
        'antiguedad': 15,
    },
    'completitud_tiers': {
        'criticos': {
            'campos': ['distritos', 'tipo_propiedad', 'condicion'],
            'puntos_por_campo': 3,
        },
        'importantes': {
            'campos': ['presupuesto_monto', 'habitaciones', 'urbanizacion', 'agente'],
            'puntos_por_campo': 2,
        },
        'complementarios': {
            'campos': [
                'presupuesto_moneda', 'presupuesto_forma_pago', 'banos',
                'area_m2', 'zona', 'cochera', 'ascensor', 'amueblado',
            ],
            'puntos_por_campo': 1,
        },
    },
    'especificidad_niveles': [
        {'nombre': 'Muy específico', 'score': 100, 'requisito': 'zona+urbanizacion+1distrito'},
        {'nombre': 'Específico', 'score': 75, 'requisito': 'urbanizacion_o_zona'},
        {'nombre': 'Preciso', 'score': 50, 'requisito': '1_distrito'},
        {'nombre': 'Amplio', 'score': 30, 'requisito': 'multi_distrito'},
        {'nombre': 'Sin ubicación', 'score': 0, 'requisito': 'sin_distrito'},
    ],
    'antiguedad_rangos': [
        {'dias_max': 7, 'score': 100},
        {'dias_max': 30, 'score': 75},
        {'dias_max': 90, 'score': 40},
        {'dias_max': 180, 'score': 15},
        {'dias_max': 999999, 'score': 5},
    ],
    'presupuesto_percentiles': {
        'p25_score': 100,
        'p25_a_p50_score': 80,
        'p50_a_p75_score': 50,
        'mayor_p75_score': 20,
        'sin_presupuesto_score': 0,
        'min_muestras': 10,
    },
}


class ConfiguracionCalidad(models.Model):
    """
    Almacena la configuración del Quality Score.
    Solo un registro activo a la vez.
    """
    activo = models.BooleanField(default=True, verbose_name='Configuración activa')
    config = models.JSONField(default=dict, verbose_name='Configuración JSON')
    nombre = models.CharField(max_length=100, blank=True, default='Default',
                              verbose_name='Nombre de configuración')
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name='Creado en')
    actualizado_en = models.DateTimeField(auto_now=True, verbose_name='Actualizado en')

    class Meta:
        db_table = 'config_calidad'
        verbose_name = 'Configuración de Calidad'
        verbose_name_plural = 'Configuraciones de Calidad'

    def __str__(self):
        return f'{self.nombre} (activo={self.activo})'

    @classmethod
    def get_config(cls):
        """Retorna la configuración activa o los defaults si no existe."""
        try:
            cfg = cls.objects.get(activo=True)
            return cfg.config
        except cls.DoesNotExist:
            return CONFIG_CALIDAD_DEFAULT
