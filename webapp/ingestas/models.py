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
    
    # Opciones para tipo de propiedad (estandarizadas)
    TIPO_PROPIEDAD_CHOICES = [
        ('Terreno', 'Terreno'),
        ('Casa', 'Casa'),
        ('Departamento', 'Departamento'),
        ('Oficina', 'Oficina'),
        ('Otros', 'Otros'),
    ]
    
    # Campos base fijos
    fuente_excel = models.CharField(max_length=100)
    fecha_ingesta = models.DateTimeField(auto_now_add=True)
    tipo_propiedad = models.CharField(
        max_length=20,
        choices=TIPO_PROPIEDAD_CHOICES,
        null=True,
        blank=True,
        verbose_name='Tipo de propiedad'
    )
    subtipo_propiedad = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name='Subtipo de propiedad',
        help_text='Ej: Casa de campo, Departamento dúplex, Oficina ejecutiva, etc.'
    )
    precio_usd = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    descripcion = models.TextField(null=True, blank=True)
    # Campos según Excel inmobiliaria-remax-10-febrero-2026
    portal = models.CharField(max_length=50, null=True, blank=True)
    url_propiedad = models.URLField(max_length=500, null=True, blank=True, db_column='url_de_la_propiedad')
    coordenadas = models.CharField(max_length=100, null=True, blank=True)
    departamento = models.CharField(max_length=100, null=True, blank=True)
    provincia = models.CharField(max_length=100, null=True, blank=True)
    distrito = models.CharField(max_length=100, null=True, blank=True)
    area_terreno = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='Área de Terreno (m²)', db_column='area_de_terreno_m2')
    area_construida = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='Área Construida (m²)', db_column='area_construida_m2')
    numero_pisos = models.IntegerField(null=True, blank=True, verbose_name='Número de Pisos', db_column='numero_de_pisos')
    numero_habitaciones = models.IntegerField(null=True, blank=True, verbose_name='Número de Habitaciones', db_column='numero_de_habitaciones')
    numero_banos = models.IntegerField(null=True, blank=True, verbose_name='Número de Baños', db_column='numero_de_banos')
    numero_cocheras = models.IntegerField(null=True, blank=True, verbose_name='Número de Cocheras', db_column='numero_de_cocheras')
    agente_inmobiliario = models.CharField(max_length=200, null=True, blank=True)
    imagenes_propiedad = models.TextField(null=True, blank=True, verbose_name='Imágenes de la Propiedad', db_column='imagenes_de_la_propiedad')
    id_propiedad = models.CharField(max_length=50, null=True, blank=True, verbose_name='ID de la Propiedad', db_column='id_de_la_propiedad')
    identificador_externo = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name='Identificador Externo',
        help_text='ID de la propiedad en la base de datos original de la fuente'
    )
    fecha_publicacion = models.DateField(null=True, blank=True, verbose_name='Fecha de Publicación', db_column='fecha_de_publicacion')
    antiguedad = models.CharField(max_length=50, null=True, blank=True, verbose_name='Antigüedad')
    servicio_agua = models.CharField(max_length=50, null=True, blank=True, db_column='servicio_de_agua')
    energia_electrica = models.CharField(max_length=50, null=True, blank=True)
    servicio_drenaje = models.CharField(max_length=50, null=True, blank=True, db_column='servicio_de_drenaje')
    servicio_gas = models.CharField(max_length=50, null=True, blank=True, db_column='servicio_de_gas')
    email_agente = models.EmailField(max_length=100, null=True, blank=True, db_column='email_del_agente')
    telefono_agente = models.CharField(max_length=20, null=True, blank=True, db_column='telefono_del_agente')
    oficina_remax = models.CharField(max_length=200, null=True, blank=True)
    # Campos de estado de venta
    ESTADO_PROPIEDAD_CHOICES = [
        ('en_publicacion', 'En publicación'),
        ('vendido', 'Vendido'),
        ('reservado', 'Reservado'),
        ('retirado', 'Retirado'),
    ]
    estado_propiedad = models.CharField(
        max_length=20,
        choices=ESTADO_PROPIEDAD_CHOICES,
        default='en_publicacion',
        null=True,
        blank=True,
        verbose_name='Estado de la propiedad'
    )
    fecha_venta = models.DateField(
        null=True,
        blank=True,
        verbose_name='Fecha de venta',
        help_text='Fecha en que se vendió la propiedad'
    )
    precio_final_venta = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Precio final de venta (USD)',
        help_text='Precio final al que se vendió la propiedad'
    )
    # Campos dinámicos se almacenan en JSON
    def default_atributos_extras():
        return {}
    
    atributos_extras = models.JSONField(default=default_atributos_extras, null=True, blank=True)  # Para campos no migrados aún

    class Meta:
        verbose_name = "Propiedad Raw"
        verbose_name_plural = "Propiedades Raw"
        indexes = [
            models.Index(fields=['fuente_excel', 'fecha_ingesta']),
            models.Index(fields=['tipo_propiedad']),
            models.Index(fields=['precio_usd']),
            models.Index(fields=['portal']),
            models.Index(fields=['departamento', 'provincia', 'distrito']),
        ]

    def __str__(self):
        ubicacion = f"{self.departamento or ''} {self.provincia or ''} {self.distrito or ''}".strip()
        if not ubicacion:
            ubicacion = 'Sin ubicación'
        return f"{self.tipo_propiedad or 'Sin tipo'} - {ubicacion}"

    def primera_imagen(self):
        """Devuelve la primera URL de imagen de la propiedad, o None si no hay imágenes."""
        if not self.imagenes_propiedad:
            return None
        # Dividir por comas y tomar la primera
        partes = [p.strip() for p in self.imagenes_propiedad.split(',') if p.strip()]
        return partes[0] if partes else None

    @property
    def lat(self):
        """Devuelve la latitud extraída del campo coordenadas."""
        if not self.coordenadas:
            return None
        try:
            # Formato esperado: "latitud, longitud" o "latitud,longitud"
            parts = self.coordenadas.split(',')
            if len(parts) >= 2:
                return float(parts[0].strip())
        except (ValueError, AttributeError):
            pass
        return None

    @property
    def lng(self):
        """Devuelve la longitud extraída del campo coordenadas."""
        if not self.coordenadas:
            return None
        try:
            parts = self.coordenadas.split(',')
            if len(parts) >= 2:
                return float(parts[1].strip())
        except (ValueError, AttributeError):
            pass
        return None


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