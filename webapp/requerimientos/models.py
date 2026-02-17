from django.db import models
from django.contrib.auth.models import User


class CampoDinamicoRequerimiento(models.Model):
    """Campos dinámicos creados por usuarios para extender RequerimientoRaw."""
    nombre_campo_bd = models.CharField(max_length=100, unique=True)
    titulo_display = models.CharField(max_length=150)
    tipo_dato = models.CharField(max_length=50)  # VARCHAR, INTEGER, DECIMAL, BOOLEAN, DATE
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Campo Dinámico Requerimiento"
        verbose_name_plural = "Campos Dinámicos Requerimiento"
        ordering = ['creado_en']

    def __str__(self):
        return f"{self.nombre_campo_bd} ({self.tipo_dato})"


class MapeoFuenteRequerimiento(models.Model):
    """Mapeo de columnas de fuente externa a campos de la base de datos para requerimientos."""
    nombre_fuente = models.CharField(max_length=100)
    portal_origen = models.CharField(max_length=50)
    mapeos_confirmados = models.JSONField(default=dict)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Mapeo de Fuente Requerimiento"
        verbose_name_plural = "Mapeos de Fuentes Requerimiento"
        unique_together = ['nombre_fuente', 'portal_origen']

    def __str__(self):
        return f"{self.nombre_fuente} ({self.portal_origen})"


class RequerimientoRaw(models.Model):
    """Modelo base para requerimientos de clientes con campos dinámicos."""
    # Campos base mínimos
    fuente_excel = models.CharField(max_length=100)
    fecha_ingesta = models.DateTimeField(auto_now_add=True)
    # Todos los demás campos serán dinámicos o estarán en atributos_extras
    atributos_extras = models.JSONField(default=dict)

    class Meta:
        verbose_name = "Requerimiento Raw"
        verbose_name_plural = "Requerimientos Raw"
        indexes = [
            models.Index(fields=['fuente_excel', 'fecha_ingesta']),
        ]

    def __str__(self):
        # Intentar obtener algún identificador de los atributos extras
        if 'cliente_nombre' in self.atributos_extras:
            return f"{self.atributos_extras.get('cliente_nombre', 'Sin nombre')} - {self.fuente_excel}"
        return f"Requerimiento {self.id} - {self.fuente_excel}"


class MigracionPendienteRequerimiento(models.Model):
    """Registro de migraciones pendientes de campos dinámicos para requerimientos."""
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
        verbose_name = "Migración Pendiente Requerimiento"
        verbose_name_plural = "Migraciones Pendientes Requerimiento"
        ordering = ['creado_en']

    def __str__(self):
        return f"{self.nombre_campo_bd} - {self.estado}"
