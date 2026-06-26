from django.db import models
from requerimientos.models import Requerimiento
from propifai.models import PropifaiProperty


class PropuestaWhatsApp(models.Model):
    class Status(models.TextChoices):
        ENVIADA = 'enviada', 'Enviada'
        RESPONDIDA = 'respondida', 'Respondida'
        INTERESADO = 'interesado', 'Interesado'
        RECHAZADO = 'rechazado', 'Rechazado'
        NO_INTERESADO = 'no_interesado', 'No interesado'
        VISITA_AGENDADA = 'visita_agendada', 'Visita agendada'
        CERRADA = 'cerrada', 'Cerrada'

    requerimiento = models.ForeignKey(
        Requerimiento, on_delete=models.CASCADE,
        db_constraint=False,
        verbose_name='Requerimiento'
    )
    propiedad_id = models.BigIntegerField(
        null=True, blank=True,
        verbose_name='ID de propiedad en dbpropify_be'
    )
    propiedad_code = models.CharField(max_length=50, blank=True)
    propiedad_title = models.CharField(max_length=500, blank=True)
    propiedad_price = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )
    propiedad_currency_id = models.BigIntegerField(null=True, blank=True)
    propiedad_district_id = models.BigIntegerField(null=True, blank=True)
    agente_nombre = models.CharField(max_length=200, blank=True)
    agente_telefono = models.CharField(max_length=20, blank=True)
    mensaje_enviado = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ENVIADA
    )
    enviado_en = models.DateTimeField(auto_now_add=True)
    respondido_en = models.DateTimeField(null=True, blank=True)
    notas = models.TextField(blank=True)

    class Meta:
        db_table = 'matching_propuestawhatsapp'
        ordering = ['-enviado_en']
        verbose_name = 'Propuesta WhatsApp'
        verbose_name_plural = 'Propuestas WhatsApp'

    def __str__(self):
        return f"Propuesta #{self.id} - Req {self.requerimiento_id} - {self.agente_nombre}"


class MatchResult(models.Model):
    """
    Resultado de un proceso de matching entre un requerimiento y una propiedad.
    Almacena el score y detalles de la compatibilidad.
    """
    requerimiento = models.ForeignKey(
        Requerimiento,
        on_delete=models.CASCADE,
        related_name='match_results',
        verbose_name='Requerimiento evaluado',
        db_constraint=False  # No crear constraint para evitar problemas con tablas no gestionadas
    )
    propiedad = models.ForeignKey(
        PropifaiProperty,
        on_delete=models.CASCADE,
        related_name='match_results',
        verbose_name='Propiedad evaluada',
        db_constraint=False  # No crear constraint porque la tabla no está gestionada por Django
    )
    
    # Score y detalles
    score_total = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name='Score total (0-100)',
        help_text='Puntuación total de compatibilidad'
    )
    score_detalle = models.JSONField(
        verbose_name='Detalle del score',
        help_text='Diccionario JSON con el aporte individual de cada campo'
    )
    fase_eliminada = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name='Fase eliminada',
        help_text='Nombre del campo discriminatorio por el que fue eliminada (si aplica)'
    )
    porcentaje_compatibilidad = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name='Porcentaje de compatibilidad',
        help_text='Representación visual del score (0-100)'
    )
    
    # Metadatos de ejecución
    ejecutado_en = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha y hora de ejecución'
    )
    notificado_al_agente = models.BooleanField(
        default=False,
        verbose_name='Notificado al agente',
        help_text='Indica si los resultados fueron notificados al agente responsable'
    )
    notificado_en = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Fecha de notificación'
    )
    
    # Campos adicionales para análisis
    ranking = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name='Ranking en el matching',
        help_text='Posición que ocupó esta propiedad en el matching específico'
    )
    
    # Flags para detección de cambios entre ejecuciones
    es_nuevo = models.BooleanField(
        default=True,
        verbose_name='Match nuevo',
        help_text='True si este match apareció en la última ejecución de matching'
    )
    score_anterior = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True,
        verbose_name='Score anterior',
        help_text='Score previo si este match fue actualizado en una ejecución posterior'
    )
    
    class Meta:
        db_table = 'matching_matchresult'
        verbose_name = 'Resultado de Matching'
        verbose_name_plural = 'Resultados de Matching'
        ordering = ['-ejecutado_en', '-score_total']
        indexes = [
            models.Index(fields=['requerimiento', 'score_total']),
            models.Index(fields=['ejecutado_en']),
            models.Index(fields=['notificado_al_agente']),
        ]
        unique_together = [['requerimiento', 'propiedad', 'ejecutado_en']]
    
    def __str__(self):
        return f"Matching {self.requerimiento.id} - {self.propiedad.code}: {self.score_total}"
    
    @property
    def es_compatible(self):
        """Indica si la propiedad pasó ambas fases (no fue eliminada)."""
        return self.fase_eliminada is None
    
    @property
    def nivel_compatibilidad(self):
        """Devuelve un nivel de compatibilidad basado en el score."""
        if self.score_total >= 80:
            return "Alta"
        elif self.score_total >= 60:
            return "Media"
        elif self.score_total >= 40:
            return "Baja"
        else:
            return "Muy baja"
