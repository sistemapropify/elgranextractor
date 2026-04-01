"""
Modelos para la integración con Meta Marketing API.
"""
from django.db import models
from django.utils import timezone


class MetaCampaign(models.Model):
    """
    Modelo que representa una campaña publicitaria de Meta (Facebook/Instagram).
    """
    # Estados posibles de una campaña
    STATUS_ACTIVE = 'ACTIVE'
    STATUS_PAUSED = 'PAUSED'
    STATUS_ARCHIVED = 'ARCHIVED'
    STATUS_DELETED = 'DELETED'
    
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Activa'),
        (STATUS_PAUSED, 'Pausada'),
        (STATUS_ARCHIVED, 'Archivada'),
        (STATUS_DELETED, 'Eliminada'),
    ]
    
    # Campos principales
    campaign_id = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='ID de campaña en Meta'
    )
    name = models.CharField(
        max_length=255,
        verbose_name='Nombre de la campaña'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        verbose_name='Estado'
    )
    objective = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Objetivo de la campaña'
    )
    daily_budget = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Presupuesto diario'
    )
    created_at_meta = models.DateField(
        null=True,
        blank=True,
        verbose_name='Fecha de creación en Meta'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Fecha de última actualización'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de creación'
    )
    
    class Meta:
        verbose_name = 'Campaña Meta'
        verbose_name_plural = 'Campañas Meta'
        ordering = ['-created_at_meta', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.campaign_id})"
    
    @property
    def is_active(self):
        """Retorna True si la campaña está activa."""
        return self.status == self.STATUS_ACTIVE
    
    def get_current_month_spend(self):
        """
        Retorna el gasto total de la campaña en el mes actual.
        """
        from django.db.models import Sum
        from django.utils import timezone
        
        today = timezone.now().date()
        first_day_of_month = today.replace(day=1)
        
        total = self.insights.filter(
            date__gte=first_day_of_month,
            date__lte=today
        ).aggregate(total_spend=Sum('spend'))['total_spend']
        
        return total or 0
    
    def get_current_month_clicks(self):
        """
        Retorna el total de clics de la campaña en el mes actual.
        """
        from django.db.models import Sum
        from django.utils import timezone
        
        today = timezone.now().date()
        first_day_of_month = today.replace(day=1)
        
        total = self.insights.filter(
            date__gte=first_day_of_month,
            date__lte=today
        ).aggregate(total_clicks=Sum('clicks'))['total_clicks']
        
        return total or 0


class MetaCampaignInsight(models.Model):
    """
    Modelo que almacena métricas diarias de una campaña publicitaria de Meta.
    """
    campaign = models.ForeignKey(
        MetaCampaign,
        on_delete=models.CASCADE,
        related_name='insights',
        verbose_name='Campaña'
    )
    date = models.DateField(verbose_name='Fecha')
    
    # Métricas principales
    impressions = models.IntegerField(
        default=0,
        verbose_name='Impresiones'
    )
    clicks = models.IntegerField(
        default=0,
        verbose_name='Clics'
    )
    spend = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name='Gasto'
    )
    reach = models.IntegerField(
        default=0,
        verbose_name='Alcance'
    )
    
    # Métricas derivadas
    cpc = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name='Costo por clic (CPC)'
    )
    ctr = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name='Tasa de clics (CTR)'
    )
    frequency = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name='Frecuencia'
    )
    
    # Metadatos
    synced_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Fecha de sincronización'
    )
    
    class Meta:
        verbose_name = 'Métrica diaria de campaña'
        verbose_name_plural = 'Métricas diarias de campañas'
        unique_together = ['campaign', 'date']
        ordering = ['-date', 'campaign']
    
    def __str__(self):
        return f"{self.campaign.name} - {self.date}"
    
    def save(self, *args, **kwargs):
        """
        Calcula automáticamente CPC y CTR si no están definidos.
        """
        # Calcular CPC si hay clics y gasto
        if self.clicks > 0 and self.spend > 0:
            self.cpc = self.spend / self.clicks
        
        # Calcular CTR si hay impresiones y clics
        if self.impressions > 0 and self.clicks > 0:
            self.ctr = (self.clicks / self.impressions) * 100
        
        # Calcular frecuencia si hay alcance e impresiones
        if self.reach > 0 and self.impressions > 0:
            self.frequency = self.impressions / self.reach
        
        super().save(*args, **kwargs)
    
    @property
    def ctr_percentage(self):
        """Retorna el CTR como porcentaje formateado."""
        if self.ctr:
            return f"{self.ctr:.2f}%"
        return "0.00%"
