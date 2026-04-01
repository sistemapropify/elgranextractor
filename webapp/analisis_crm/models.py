from django.db import models


class Lead(models.Model):
    """
    Modelo que representa un lead del CRM (tabla crm_leads en la base de datos propifai).
    Solo lectura, ya que la tabla pertenece a otra aplicación.
    """
    id = models.BigIntegerField(primary_key=True)
    full_name = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=30)
    email = models.EmailField(max_length=254, blank=True, null=True)
    notes = models.TextField()
    date_entry = models.DateTimeField(blank=True, null=True)
    id_chatwoot = models.CharField(max_length=100, blank=True, null=True)
    date_last_message = models.DateTimeField(blank=True, null=True)
    user_last_message = models.CharField(max_length=10, blank=True, null=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    is_active = models.BooleanField()
    canal_lead_id = models.BigIntegerField(blank=True, null=True)
    created_by_id = models.BigIntegerField(blank=True, null=True)
    lead_status_id = models.BigIntegerField(blank=True, null=True)
    username = models.CharField(max_length=150)

    class Meta:
        managed = False
        db_table = 'crm_leads'
        verbose_name = 'Lead'
        verbose_name_plural = 'Leads'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.full_name or 'Sin nombre'} ({self.phone})"
