import uuid
import random
from django.db import models
from django.conf import settings
from decimal import Decimal


def generar_codigo_acm():
    """
    Genera un código único para ACM con formato ACM####### (ej: ACM9342453).
    Usa 7 dígitos aleatorios para evitar colisiones de concurrencia.
    """
    while True:
        codigo = f"ACM{random.randint(1000000, 9999999)}"
        if not ACMLink.objects.filter(codigo=codigo).exists():
            return codigo


class ACMLink(models.Model):
    """
    Enlace único para compartir resultado ACM por WhatsApp.
    Cada vez que se genera un análisis ACM, se crea un registro con un UUID único.
    El enlace público permite ver el PDF y trackear clicks.
    """
    ORIGEN_CHOICES = [
        ('pdf', 'Generar PDF'),
        ('compartir', 'Compartir WhatsApp'),
        ('ambos', 'Ambos'),
        ('componentes', 'ACM por componentes'),
    ]

    METODO_CHOICES = [
        ('clasico', 'ACM clásico'),
        ('componentes', 'Suelo + construcción y mejoras'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo = models.CharField(
        max_length=20, unique=True, null=True, blank=True,
        verbose_name='Código ACM (ej: ACM9342453)'
    )
    origen = models.CharField(
        max_length=20, choices=ORIGEN_CHOICES, default='compartir',
        verbose_name='Origen del guardado'
    )
    metodo = models.CharField(max_length=20, choices=METODO_CHOICES, default='clasico')
    parametros_json = models.JSONField(default=dict, blank=True)
    resultado_json = models.JSONField(default=dict, blank=True)
    selection_fingerprint = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    user = models.ForeignKey(
        'intelligence.User',
        on_delete=models.CASCADE,
        related_name='acm_links',
        verbose_name='Usuario que generó el enlace'
    )
    # Parámetros del análisis ACM
    tipo_propiedad = models.CharField(max_length=50, verbose_name='Tipo de propiedad')
    area_m2 = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Área en m²')
    es_terreno = models.BooleanField(default=False, verbose_name='Es terreno')
    # Estadísticas del análisis
    precio_min_m2 = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Precio mínimo m²')
    precio_max_m2 = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Precio máximo m²')
    precio_promedio_m2 = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Precio promedio m²')
    precio_promedio_ponderado_m2 = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Precio promedio ponderado m²')
    valor_comercial = models.DecimalField(max_digits=14, decimal_places=2, verbose_name='Valor comercial estimado')
    precio_venta_sugerido = models.DecimalField(max_digits=14, decimal_places=2, verbose_name='Precio venta sugerido')
    valor_realizacion = models.DecimalField(max_digits=14, decimal_places=2, verbose_name='Valor realización inmediata')
    num_comparables = models.IntegerField(default=0, verbose_name='Número de comparables')
    # Datos serializados de las propiedades comparables (JSON)
    propiedades_json = models.JSONField(default=list, verbose_name='Propiedades comparables')
    # Tracking
    click_count = models.IntegerField(default=0, verbose_name='Contador de clicks')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Creado')
    last_click_at = models.DateTimeField(null=True, blank=True, verbose_name='Último click')

    class Meta:
        db_table = 'acm_links'
        verbose_name = 'Enlace ACM'
        verbose_name_plural = 'Enlaces ACM'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['created_at']),
            models.Index(fields=['codigo']),
        ]

    def __str__(self):
        codigo_str = self.codigo or str(self.id)[:8]
        return f"{codigo_str} - {self.tipo_propiedad} - {self.user.username}"

    def registrar_click(self):
        """Incrementa el contador de clicks y actualiza la fecha del último click."""
        from django.utils import timezone
        self.click_count = models.F('click_count') + 1
        self.last_click_at = timezone.now()
        self.save(update_fields=['click_count', 'last_click_at'])

    @property
    def short_id(self):
        """Retorna los primeros 8 caracteres del UUID para identificación rápida."""
        return str(self.id)[:8]

    @property
    def codigo_display(self):
        """Retorna el código ACM o un fallback con UUID corto."""
        return self.codigo or f"ACM-{self.short_id}"


class ACMTestProperty(models.Model):
    """Snapshot editable for ACM experiments; never writes to PropiedadRaw."""
    source_id = models.CharField(max_length=120, unique=True)
    source = models.CharField(max_length=50, blank=True, default='')
    tipo_propiedad = models.CharField(max_length=100, blank=True, default='')
    precio_usd = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    precio_final_venta = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    descripcion = models.TextField(blank=True, default='')
    portal = models.CharField(max_length=50, blank=True, default='')
    url_propiedad = models.URLField(max_length=500, blank=True, default='')
    coordenadas = models.CharField(max_length=100, blank=True, default='')
    departamento = models.CharField(max_length=100, blank=True, default='')
    provincia = models.CharField(max_length=100, blank=True, default='')
    distrito = models.CharField(max_length=100, blank=True, default='')
    area_terreno = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    area_construida = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    numero_habitaciones = models.IntegerField(null=True, blank=True)
    numero_banos = models.IntegerField(null=True, blank=True)
    numero_cocheras = models.IntegerField(null=True, blank=True)
    imagenes_propiedad = models.TextField(blank=True, default='')
    estado_propiedad = models.CharField(max_length=50, blank=True, default='')
    datos_crudos = models.JSONField(default=dict, blank=True)
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'acm_test_properties'
        ordering = ['-synced_at', 'id']

    @property
    def lat(self):
        try:
            return float(str(self.coordenadas).split(',')[0].strip())
        except (ValueError, IndexError, AttributeError):
            return None

    @property
    def lng(self):
        try:
            return float(str(self.coordenadas).split(',')[1].strip())
        except (ValueError, IndexError, AttributeError):
            return None

    def primera_imagen(self):
        return str(self.imagenes_propiedad).split(',')[0].strip() or None

    @property
    def id_propiedad(self):
        return self.source_id

    def get_estado_propiedad_display(self):
        return self.estado_propiedad or 'En Publicación'
