import uuid
import random
from django.db import models
from django.conf import settings


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
