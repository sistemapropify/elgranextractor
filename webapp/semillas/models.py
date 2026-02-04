"""
Modelos para la gestión de fuentes web (semillas) a monitorear.
"""
from django.db import models
from django.utils import timezone
from django.core.validators import URLValidator, MinValueValidator, MaxValueValidator


class FuenteWeb(models.Model):
    """
    Representa una fuente web (URL) que será monitoreada periódicamente.
    Puede ser semilla estática (configurada manualmente) o dinámica (descubierta automáticamente).
    """
    TIPO_FUENTE_CHOICES = [
        ('semilla_listado', 'Semilla Listado'),  # Página con múltiples links
        ('documento_directo_html', 'Documento Directo HTML'),  # Artículo o página individual
        ('documento_directo_pdf', 'Documento Directo PDF'),  # PDF individual
        ('api_feed', 'API/Feed'),  # Fuente estructurada (RSS, JSON)
    ]
    
    ESTADO_CHOICES = [
        ('activa', 'Activa'),
        ('pausada', 'Pausada'),
        ('eliminada', 'Eliminada'),
    ]
    
    PRIORIDAD_CHOICES = [
        (1, 'Muy baja'),
        (2, 'Baja'),
        (3, 'Media'),
        (4, 'Alta'),
        (5, 'Muy alta'),
    ]
    
    CATEGORIA_CHOICES = [
        ('oferta', 'Oferta Activa (Portales)'),
        ('legal', 'Normativa y Leyes'),
        ('infraestructura', 'Obras Públicas'),
        ('inteligencia', 'Análisis de Mercado'),
        ('riesgo', 'Contexto Socio-Ambiental'),
        ('actores', 'Constructoras y Agentes'),
    ]
    
    # Frecuencias recomendadas por categoría (en horas)
    FRECUENCIA_RECOMENDADA = {
        'oferta': 2,
        'legal': 24,
        'infraestructura': 24,
        'inteligencia': 24,
        'riesgo': 6,
        'actores': 24,
    }
    
    # Prioridades recomendadas por categoría (1-5)
    PRIORIDAD_RECOMENDADA = {
        'oferta': 5,
        'legal': 3,
        'infraestructura': 4,
        'inteligencia': 3,
        'riesgo': 5,
        'actores': 2,
    }
    
    # Información básica
    url = models.URLField(
        max_length=500,
        unique=True,
        validators=[URLValidator()],
        verbose_name='URL completa'
    )
    nombre = models.CharField(
        max_length=200,
        verbose_name='Nombre descriptivo'
    )
    descripcion = models.TextField(
        blank=True,
        verbose_name='Descripción'
    )
    
    # Configuración de monitoreo
    tipo = models.CharField(
        max_length=30,
        choices=TIPO_FUENTE_CHOICES,
        default='semilla_listado',
        verbose_name='Tipo de fuente'
    )
    estado = models.CharField(
        max_length=10,
        choices=ESTADO_CHOICES,
        default='activa',
        verbose_name='Estado'
    )
    prioridad = models.IntegerField(
        choices=PRIORIDAD_CHOICES,
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name='Prioridad (1-5)'
    )
    categoria = models.CharField(
        max_length=20,
        choices=CATEGORIA_CHOICES,
        default='oferta',
        verbose_name='Categoría de inteligencia'
    )
    
    # Frecuencia de revisión (en horas)
    frecuencia_revision_horas = models.IntegerField(
        default=24,
        validators=[MinValueValidator(1), MaxValueValidator(168)],  # Máximo 1 semana
        verbose_name='Frecuencia de revisión (horas)'
    )
    
    # Configuración de scraping
    user_agent_personalizado = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='User-Agent personalizado'
    )
    respetar_robots_txt = models.BooleanField(
        default=True,
        verbose_name='Respetar robots.txt'
    )
    delay_entre_requests = models.IntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(30)],
        verbose_name='Delay entre requests (segundos)'
    )
    
    # Metadatos
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de creación'
    )
    fecha_ultima_revision = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha última revisión'
    )
    fecha_proxima_revision = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha próxima revisión'
    )
    
    # Estadísticas
    total_capturas = models.IntegerField(
        default=0,
        verbose_name='Total de capturas'
    )
    total_cambios_detectados = models.IntegerField(
        default=0,
        verbose_name='Total de cambios detectados'
    )
    tasa_cambio_porcentaje = models.FloatField(
        default=0.0,
        verbose_name='Tasa de cambio (%)'
    )
    
    # Campos para descubrimiento automático
    descubierta_por = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='fuentes_descubiertas',
        verbose_name='Descubierta por (fuente padre)'
    )
    profundidad_descubrimiento = models.IntegerField(
        default=0,
        verbose_name='Profundidad de descubrimiento'
    )
    
    # Campos adicionales para gestión
    es_semilla_activa = models.BooleanField(
        default=True,
        verbose_name='Es semilla activa (genera hijos)'
    )
    
    class Meta:
        verbose_name = 'Fuente Web'
        verbose_name_plural = 'Fuentes Web'
        ordering = ['-prioridad', 'fecha_proxima_revision']
        indexes = [
            models.Index(fields=['estado', 'fecha_proxima_revision']),
            models.Index(fields=['tipo', 'prioridad']),
        ]
    
    def __str__(self):
        return f'{self.nombre} ({self.url})'
    
    def actualizar_fecha_proxima_revision(self):
        """Actualiza la fecha de próxima revisión basada en la frecuencia configurada."""
        from datetime import timedelta
        if self.fecha_ultima_revision:
            self.fecha_proxima_revision = self.fecha_ultima_revision + timedelta(
                hours=self.frecuencia_revision_horas
            )
        else:
            self.fecha_proxima_revision = timezone.now() + timedelta(
                hours=self.frecuencia_revision_horas
            )
        self.save(update_fields=['fecha_proxima_revision'])
    
    def incrementar_capturas(self, hubo_cambio=False):
        """Incrementa el contador de capturas y actualiza estadísticas."""
        self.total_capturas += 1
        if hubo_cambio:
            self.total_cambios_detectados += 1
        
        # Calcular tasa de cambio
        if self.total_capturas > 0:
            self.tasa_cambio_porcentaje = (
                self.total_cambios_detectados / self.total_capturas
            ) * 100
        
        self.save(update_fields=[
            'total_capturas',
            'total_cambios_detectados',
            'tasa_cambio_porcentaje'
        ])
    
    def ajustar_frecuencia_automaticamente(self):
        """
        Ajusta automáticamente la frecuencia de revisión basada en la tasa de cambio.
        Si cambia mucho, revisar más seguido; si cambia poco, revisar menos seguido.
        """
        if self.total_capturas < 5:  # Mínimo de capturas para ajustar
            return
        
        if self.tasa_cambio_porcentaje > 50:  # Cambia mucho (>50%)
            nueva_frecuencia = max(1, self.frecuencia_revision_horas // 2)
        elif self.tasa_cambio_porcentaje < 10:  # Cambia poco (<10%)
            nueva_frecuencia = min(168, self.frecuencia_revision_horas * 2)
        else:
            return  # Mantener frecuencia actual
        
        if nueva_frecuencia != self.frecuencia_revision_horas:
            self.frecuencia_revision_horas = nueva_frecuencia
            self.save(update_fields=['frecuencia_revision_horas'])
            self.actualizar_fecha_proxima_revision()

    def frecuencia_recomendada(self):
        """Devuelve la frecuencia de revisión recomendada para la categoría de esta fuente."""
        return self.FRECUENCIA_RECOMENDADA.get(self.categoria, 24)

    def prioridad_recomendada(self):
        """Devuelve la prioridad recomendada para la categoría de esta fuente."""
        return self.PRIORIDAD_RECOMENDADA.get(self.categoria, 3)

    def sugerir_frecuencia_y_prioridad(self):
        """
        Sugiere ajustes de frecuencia y prioridad basados en la categoría.
        Puede usarse para inicializar una nueva fuente.
        """
        return {
            'frecuencia_recomendada': self.frecuencia_recomendada(),
            'prioridad_recomendada': self.prioridad_recomendada(),
        }