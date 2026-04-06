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


class User(models.Model):
    """
    Modelo para la tabla users en la base de datos propifai.
    """
    id = models.BigIntegerField(primary_key=True)
    password = models.CharField(max_length=128)
    last_login = models.DateTimeField(blank=True, null=True)
    is_superuser = models.BooleanField()
    username = models.CharField(max_length=150)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.CharField(max_length=254)
    is_staff = models.BooleanField()
    is_active = models.BooleanField()
    date_joined = models.DateTimeField()
    phone = models.CharField(max_length=50)
    is_verified = models.BooleanField()
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2)
    is_active_agent = models.BooleanField()
    area_id = models.BigIntegerField(blank=True, null=True)
    role_id = models.BigIntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'users'
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.username})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


class LeadAssignment(models.Model):
    """
    Modelo para la tabla crm_leads_assigned_to que relaciona leads con usuarios.
    """
    id = models.BigIntegerField(primary_key=True)
    lead = models.ForeignKey(Lead, on_delete=models.DO_NOTHING, db_column='lead_id')
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, db_column='customuser_id')

    class Meta:
        managed = False
        db_table = 'crm_leads_assigned_to'
        verbose_name = 'Asignación de Lead'
        verbose_name_plural = 'Asignaciones de Leads'

    def __str__(self):
        return f"Lead {self.lead_id} asignado a {self.user_id}"
