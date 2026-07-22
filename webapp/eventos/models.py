from django.db import models


class EventType(models.Model):
    """
    Modelo para los tipos de eventos (event_type) en dbpropify_be.
    """
    id = models.BigIntegerField(primary_key=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_by_id = models.BigIntegerField(null=True, blank=True)
    updated_by_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        db_table = 'event_type'
        managed = False  # La tabla ya existe en la base de datos

    def __str__(self):
        return self.name


class Event(models.Model):
    """
    Modelo para los eventos (event) en dbpropify_be.
    Mapeo exacto de las columnas reales de la tabla dbo.event.
    """
    id = models.BigIntegerField(primary_key=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    code = models.CharField(max_length=20)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    tracing = models.TextField(blank=True, default='')
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)
    assigned_agent_id = models.BigIntegerField(null=True, blank=True)
    contact_id = models.BigIntegerField(null=True, blank=True)
    created_by_id = models.BigIntegerField(null=True, blank=True)
    event_type = models.ForeignKey(
        EventType,
        on_delete=models.DO_NOTHING,
        db_column='event_type_id',
        related_name='events'
    )
    property_id = models.BigIntegerField(null=True, blank=True)
    updated_by_id = models.BigIntegerField(null=True, blank=True)
    lead_id = models.BigIntegerField(null=True, blank=True)
    match_id = models.BigIntegerField(null=True, blank=True)
    proposal_id = models.BigIntegerField(null=True, blank=True)
    completed = models.BooleanField(default=False)

    class Meta:
        db_table = 'event'
        managed = False  # La tabla ya existe en la base de datos
        indexes = [
            models.Index(fields=['start_time']),
            models.Index(fields=['property_id']),
            models.Index(fields=['event_type']),
            models.Index(fields=['assigned_agent_id']),
            models.Index(fields=['lead_id']),
        ]

    def __str__(self):
        return f"{self.code} - {self.title}"

    @property
    def fecha_completa(self):
        """Retorna start_time si existe."""
        return self.start_time
