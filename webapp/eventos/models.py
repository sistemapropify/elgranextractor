from django.db import models


class EventType(models.Model):
    """
    Modelo para los tipos de eventos (event_types) en la base de datos propifai.
    """
    id = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=7)
    is_active = models.BooleanField()
    created_at = models.DateTimeField()

    class Meta:
        db_table = 'event_types'
        managed = False  # La tabla ya existe en la base de datos

    def __str__(self):
        return self.name


class Event(models.Model):
    """
    Modelo para los eventos (events) en la base de datos propifai.
    """
    id = models.BigIntegerField(primary_key=True)
    code = models.CharField(max_length=20)
    titulo = models.CharField(max_length=200)
    fecha_evento = models.DateField()
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    detalle = models.TextField()  # nvarchar(-1) es equivalente a TextField
    interesado = models.CharField(max_length=200)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    is_active = models.BooleanField()
    created_by_id = models.BigIntegerField()
    property_id = models.BigIntegerField(null=True, blank=True)
    event_type = models.ForeignKey(
        EventType,
        on_delete=models.DO_NOTHING,
        db_column='event_type_id'
    )
    contact_id = models.BigIntegerField(null=True, blank=True)
    assigned_agent_id = models.BigIntegerField(null=True, blank=True)
    seguimiento = models.TextField()
    lead_id = models.BigIntegerField(null=True, blank=True)
    proposal_id = models.BigIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20)
    rejection_reason = models.TextField()

    class Meta:
        db_table = 'events'
        managed = False  # La tabla ya existe en la base de datos
        indexes = [
            models.Index(fields=['fecha_evento']),
            models.Index(fields=['property_id']),
            models.Index(fields=['event_type']),
            models.Index(fields=['assigned_agent_id']),
        ]

    def __str__(self):
        return f"{self.code} - {self.titulo}"

    @property
    def fecha_completa(self):
        """Retorna la fecha y hora de inicio combinadas."""
        from django.utils import timezone
        import datetime
        if self.hora_inicio:
            return datetime.datetime.combine(self.fecha_evento, self.hora_inicio)
        return datetime.datetime.combine(self.fecha_evento, datetime.time.min)
