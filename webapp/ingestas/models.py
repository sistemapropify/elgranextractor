from django.db import models
from django.contrib.auth.models import User


class CampoDinamico(models.Model):
    """Campos dinámicos creados por usuarios para extender PropiedadRaw."""
    nombre_campo_bd = models.CharField(max_length=100, unique=True)
    titulo_display = models.CharField(max_length=150)
    tipo_dato = models.CharField(max_length=50)  # VARCHAR, INTEGER, DECIMAL, BOOLEAN, DATE
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Campo Dinámico"
        verbose_name_plural = "Campos Dinámicos"
        ordering = ['creado_en']

    def __str__(self):
        return f"{self.nombre_campo_bd} ({self.tipo_dato})"


class MapeoFuente(models.Model):
    """Mapeo de columnas de fuente externa a campos de la base de datos."""
    nombre_fuente = models.CharField(max_length=100)
    portal_origen = models.CharField(max_length=50)
    mapeos_confirmados = models.JSONField(default=dict)
    # Ejemplo: {"Tipo de Propiedad": {"campo_bd": "tipo_propiedad", "titulo_display": "Tipo de Propiedad"}}
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Mapeo de Fuente"
        verbose_name_plural = "Mapeos de Fuentes"
        unique_together = ['nombre_fuente', 'portal_origen']

    def __str__(self):
        return f"{self.nombre_fuente} ({self.portal_origen})"


class PropiedadRaw(models.Model):
    """Modelo base para propiedades inmobiliarias con campos fijos y dinámicos."""
    # Campos base fijos
    fuente_excel = models.CharField(max_length=100)
    fecha_ingesta = models.DateTimeField(auto_now_add=True)
    tipo_propiedad = models.CharField(max_length=100, null=True, blank=True)
    precio_usd = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    moneda = models.CharField(max_length=10, default='USD')
    ubicacion = models.CharField(max_length=255, null=True, blank=True)
    metros_cuadrados = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    habitaciones = models.IntegerField(null=True, blank=True)
    banos = models.IntegerField(null=True, blank=True)
    estacionamientos = models.IntegerField(null=True, blank=True)
    descripcion = models.TextField(null=True, blank=True)
    url_fuente = models.URLField(max_length=500, null=True, blank=True)
    # Campos dinámicos se almacenan en JSON
    atributos_extras = models.JSONField(default=dict)  # Para campos no migrados aún

    class Meta:
        verbose_name = "Propiedad Raw"
        verbose_name_plural = "Propiedades Raw"
        indexes = [
            models.Index(fields=['fuente_excel', 'fecha_ingesta']),
            models.Index(fields=['tipo_propiedad']),
            models.Index(fields=['precio_usd']),
        ]

    def __str__(self):
        return f"{self.tipo_propiedad or 'Sin tipo'} - {self.ubicacion or 'Sin ubicación'}"


class MigracionPendiente(models.Model):
    """Registro de migraciones pendientes de campos dinámicos."""
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('completada', 'Completada'),
        ('error', 'Error'),
    ]
    nombre_campo_bd = models.CharField(max_length=100)
    titulo_display = models.CharField(max_length=150)
    tipo_dato = models.CharField(max_length=50)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')
    ejecutada_en = models.DateTimeField(null=True, blank=True)
    error_mensaje = models.TextField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Migración Pendiente"
        verbose_name_plural = "Migraciones Pendientes"
        ordering = ['creado_en']

    def __str__(self):
        return f"{self.nombre_campo_bd} - {self.estado}"