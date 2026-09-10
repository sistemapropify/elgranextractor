import uuid

from django.conf import settings
from django.db import models


class CampoDinamico(models.Model):
    """Campos dinámicos creados por usuarios para extender PropiedadRaw."""
    nombre_campo_bd = models.CharField(max_length=100, unique=True)
    titulo_display = models.CharField(max_length=150)
    tipo_dato = models.CharField(max_length=50)  # VARCHAR, INTEGER, DECIMAL, BOOLEAN, DATE
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
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
    # Condición: venta (compra) o alquiler
    CONDICION_CHOICES = [
        ('venta', 'Venta'),
        ('compra', 'Compra'),  # Mantener por compatibilidad
        ('alquiler', 'Alquiler'),
        ('anticresis', 'Anticresis'),
        ('ambos', 'Compra y Alquiler'),
        ('no_especificado', 'No Especificado'),
    ]
    condicion = models.CharField(
        max_length=20,
        choices=CONDICION_CHOICES,
        default='no_especificado',
        null=True,
        blank=True,
        verbose_name='Condición (Venta/Alquiler)',
        help_text='Indica si la propiedad está en venta, alquiler, anticresis o ambos'
    )
    propiedad_verificada = models.BooleanField(
        default=False,
        verbose_name='Propiedad Verificada',
        help_text='Indica si los campos están óptimos para el análisis del ACM'
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


class PropiedadesCompetencia(models.Model):
    """
    Tabla unificada para propiedades scrapeadas de portales de competencia.
    Cada scraper-skill (Remax, Adondevivir, Properati, Urbania) inserta aquí.
    Unique: fuente + id_origen para evitar duplicados al re-scrapear.
    """

    TIPO_INMUEBLE_CHOICES = [
        ('Casa', 'Casa'),
        ('Departamento', 'Departamento'),
        ('Terreno', 'Terreno'),
        ('Oficina', 'Oficina'),
        ('Local', 'Local'),
        ('Hotel', 'Hotel'),
        ('Otro', 'Otro'),
    ]

    TIPO_OPERACION_CHOICES = [
        ('Venta', 'Venta'),
        ('Alquiler', 'Alquiler'),
        ('Ambos', 'Compra y Alquiler'),
        ('No especificado', 'No especificado'),
    ]

    ESTADO_PUBLICACION_CHOICES = [
        ('sin_verificar', 'Sin verificar'),
        ('activa', 'Activa'),
        ('posible_retirada', 'Posible retirada'),
        ('retirada', 'Retirada'),
    ]

    PRECISION_UBICACION_CHOICES = [
        ('exacta', 'Exacta'),
        ('aproximada', 'Aproximada'),
        ('desconocida', 'Desconocida'),
    ]

    # ── Identificación ──
    fuente = models.CharField(
        max_length=50,
        verbose_name='Portal de origen',
        help_text='remax, adondevivir, properati, urbania'
    )
    id_origen = models.CharField(
        max_length=100,
        verbose_name='ID en el portal',
        help_text='ID único de la propiedad en el portal de origen'
    )
    fecha_extraccion = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Fecha de extracción'
    )

    # ── Datos de la propiedad ──
    titulo = models.CharField(
        max_length=255, null=True, blank=True,
        verbose_name='Título'
    )
    tipo_inmueble = models.CharField(
        max_length=50, choices=TIPO_INMUEBLE_CHOICES,
        null=True, blank=True,
        verbose_name='Tipo de inmueble'
    )
    tipo_operacion = models.CharField(
        max_length=20, choices=TIPO_OPERACION_CHOICES,
        null=True, blank=True,
        verbose_name='Tipo de operación'
    )
    precio_soles = models.DecimalField(
        max_digits=15, decimal_places=2,
        null=True, blank=True,
        verbose_name='Precio en Soles'
    )
    precio_usd = models.DecimalField(
        max_digits=15, decimal_places=2,
        null=True, blank=True,
        verbose_name='Precio en USD'
    )
    area_m2 = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True,
        verbose_name='Área (m²)'
    )
    dormitorios = models.IntegerField(
        null=True, blank=True,
        verbose_name='Dormitorios'
    )
    banos = models.IntegerField(
        null=True, blank=True,
        verbose_name='Baños'
    )
    estacionamientos = models.IntegerField(
        null=True, blank=True,
        verbose_name='Estacionamientos'
    )

    # ── Ubicación ──
    distrito = models.CharField(
        max_length=100, null=True, blank=True
    )
    provincia = models.CharField(
        max_length=100, null=True, blank=True
    )
    departamento = models.CharField(
        max_length=100, null=True, blank=True
    )
    direccion_texto = models.TextField(
        null=True, blank=True,
        verbose_name='Dirección'
    )
    latitud = models.DecimalField(
        max_digits=10, decimal_places=7,
        null=True, blank=True
    )
    longitud = models.DecimalField(
        max_digits=10, decimal_places=7,
        null=True, blank=True
    )
    precision_ubicacion = models.CharField(
        max_length=12,
        choices=PRECISION_UBICACION_CHOICES,
        default='desconocida',
        db_index=True,
        verbose_name='Precisión de ubicación',
        help_text='exacta, aproximada o desconocida (si el anunciante ocultó la dirección)'
    )

    # ── Descripción ──
    descripcion = models.TextField(
        null=True, blank=True
    )
    amenities = models.TextField(
        null=True, blank=True,
        verbose_name='Servicios / Amenities'
    )

    # ── Enlaces ──
    url = models.URLField(
        max_length=500, null=True, blank=True,
        verbose_name='URL de la propiedad'
    )
    imagen_url = models.URLField(
        max_length=500, null=True, blank=True,
        verbose_name='URL de imagen'
    )

    # ── Metadata ──
    antiguedad_anios = models.IntegerField(
        null=True, blank=True,
        verbose_name='Antigüedad (años)'
    )
    agencia_agente = models.CharField(
        max_length=200, null=True, blank=True,
        verbose_name='Agencia / Agente'
    )

    # ── Ciclo de vida en el portal ──
    estado_publicacion = models.CharField(
        max_length=24,
        choices=ESTADO_PUBLICACION_CHOICES,
        default='sin_verificar',
        db_index=True,
        verbose_name='Estado de publicación',
    )
    primera_vez_vista = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Primera vez vista',
    )
    ultima_vez_vista = models.DateTimeField(
        null=True, blank=True, db_index=True,
        verbose_name='Última vez vista',
    )
    fecha_primera_ausencia = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Primera ausencia detectada',
    )
    fecha_retiro_confirmado = models.DateTimeField(
        null=True, blank=True, db_index=True,
        verbose_name='Retiro confirmado',
    )
    ausencias_consecutivas = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Ausencias consecutivas',
    )
    ultima_ejecucion_vista = models.ForeignKey(
        'EjecucionPortal',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='publicaciones_ultima_vista',
        verbose_name='Última ejecución donde fue vista',
    )

    # ── Respaldo RAW para QA ──
    datos_crudos = models.JSONField(
        null=True, blank=True,
        verbose_name='Datos originales del scraper',
        help_text='Respaldo del diccionario raw para depuración'
    )

    # ── Timestamps ──
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'propiedades_competencia'
        verbose_name = "Propiedad de Competencia"
        verbose_name_plural = "Propiedades de Competencia"
        unique_together = ['fuente', 'id_origen']
        indexes = [
            models.Index(fields=['fuente'], name='prop_comp_fuente_idx'),
            models.Index(fields=['fuente', 'fecha_extraccion'], name='prop_comp_fuente_fecha_idx'),
            models.Index(fields=['tipo_inmueble'], name='prop_comp_tipo_idx'),
            models.Index(fields=['distrito'], name='prop_comp_distrito_idx'),
        ]
        ordering = ['-fecha_extraccion']

    def __str__(self):
        return f"[{self.fuente}] {self.titulo or 'Sin título'} - {self.distrito or 'Sin distrito'}"


class ScrapingJob(models.Model):
    """
    Estado de un trabajo de scraping en ejecución.
    Permite controlar (pausar/reanudar/detener) desde el dashboard.
    """
    heartbeat_at = models.DateTimeField(null=True, blank=True)
    lease_expires_at = models.DateTimeField(null=True, blank=True, db_index=True)

    ESTADOS = [
        ('idle', 'Inactivo'),
        ('running', 'Ejecutando'),
        ('paused', 'Pausado'),
        ('completed', 'Completado'),
        ('error', 'Error'),
        ('stopped', 'Detenido'),
    ]

    estado = models.CharField(
        max_length=20, choices=ESTADOS, default='idle',
        verbose_name='Estado'
    )
    execution_token = models.UUIDField(
        null=True, blank=True, editable=False, db_index=True,
        verbose_name='Token de ejecución',
        help_text='Impide que un proceso huérfano siga escribiendo tras una reanudación.',
    )
    portal_actual = models.CharField(
        max_length=50, null=True, blank=True,
        verbose_name='Portal actual'
    )
    progreso = models.IntegerField(
        default=0,
        verbose_name='Progreso (%)'
    )
    total_propiedades = models.IntegerField(
        default=0,
        verbose_name='Total propiedades'
    )
    procesadas = models.IntegerField(
        default=0,
        verbose_name='Procesadas'
    )
    nuevas = models.IntegerField(
        default=0,
        verbose_name='Nuevas insertadas'
    )
    actualizadas = models.IntegerField(
        default=0,
        verbose_name='Actualizadas'
    )
    errores = models.IntegerField(
        default=0,
        verbose_name='Con error'
    )
    parametros = models.JSONField(
        default=dict, null=True, blank=True,
        verbose_name='Parámetros de ejecución',
        help_text='Portales seleccionados, max_paginas, etc.'
    )
    mensaje_error = models.TextField(
        null=True, blank=True,
        verbose_name='Mensaje de error'
    )
    iniciado_en = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Iniciado en'
    )
    completado_en = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Completado en'
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'scraping_jobs'
        verbose_name = "Trabajo de Scraping"
        verbose_name_plural = "Trabajos de Scraping"
        ordering = ['-creado_en']

    def __str__(self):
        return f"Scraping #{self.id} - {self.get_estado_display()}"


class ScrapingWorker(models.Model):
    identity = models.CharField(max_length=128, primary_key=True)
    heartbeat_at = models.DateTimeField()
    revision = models.CharField(max_length=64, default='development')

    class Meta:
        db_table = 'scraping_workers'


class EjecucionPortal(models.Model):
    """Ejecución confiable usada para detectar altas, ausencias y retiros."""

    ESTADOS = [
        ('running', 'Ejecutando'),
        ('completed', 'Completada'),
        ('incomplete', 'Incompleta'),
        ('error', 'Error'),
    ]

    token = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False,
        verbose_name='Token estable de ejecución',
    )
    job = models.ForeignKey(
        ScrapingJob,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ejecuciones_portal',
        verbose_name='Trabajo de scraping',
    )
    portal = models.CharField(max_length=50, db_index=True)
    source_key = models.CharField(max_length=64, default='', db_index=True)
    source_config = models.JSONField(default=dict, blank=True)
    discovery = models.JSONField(default=dict, blank=True)
    estado = models.CharField(
        max_length=20, choices=ESTADOS, default='running', db_index=True,
    )
    es_confiable = models.BooleanField(default=False)
    es_linea_base = models.BooleanField(default=False)
    propiedades_vistas = models.PositiveIntegerField(default=0)
    posibles_retiradas = models.PositiveIntegerField(default=0)
    retiros_confirmados = models.PositiveIntegerField(default=0)
    motivo_no_confiable = models.TextField(null=True, blank=True)
    iniciado_en = models.DateTimeField(auto_now_add=True)
    completado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'scraping_ejecuciones_portal'
        verbose_name = 'Ejecución de portal'
        verbose_name_plural = 'Ejecuciones de portales'
        ordering = ['-iniciado_en']
        indexes = [
            models.Index(fields=['portal', 'estado'], name='ejec_portal_estado_idx'),
            models.Index(
                fields=['portal', 'es_confiable', 'completado_en'],
                name='ejec_portal_conf_fin_idx',
            ),
        ]

    def __str__(self):
        return f"{self.portal} · {self.token} · {self.get_estado_display()}"


class ScrapingLog(models.Model):
    """
    Log individual de cada propiedad procesada durante un scraping.
    Se usa para el terminal en tiempo real vía SSE.
    """

    NIVELES = [
        ('info', 'Info'),
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('debug', 'Debug'),
    ]

    job = models.ForeignKey(
        ScrapingJob, on_delete=models.CASCADE,
        related_name='logs',
        verbose_name='Trabajo'
    )
    nivel = models.CharField(
        max_length=20, choices=NIVELES, default='info',
        verbose_name='Nivel'
    )
    mensaje = models.TextField(
        verbose_name='Mensaje'
    )
    evento = models.CharField(max_length=80, default='message', db_index=True)
    contexto = models.JSONField(default=dict, blank=True)
    portal = models.CharField(
        max_length=50, null=True, blank=True,
        verbose_name='Portal'
    )
    propiedad_id = models.CharField(
        max_length=100, null=True, blank=True,
        verbose_name='ID de propiedad'
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Timestamp'
    )

    class Meta:
        db_table = 'scraping_logs'
        verbose_name = "Log de Scraping"
        verbose_name_plural = "Logs de Scraping"
        ordering = ['timestamp']

    def __str__(self):
        return f"[{self.nivel}] {self.mensaje[:80]}"

    @classmethod
    def log(cls, job, nivel, mensaje, portal=None, propiedad_id=None,
            evento='message', contexto=None):
        """Crea un log y lo retorna (útil para SSE)."""
        from scrapi.telemetry import sanitize
        return cls.objects.create(
            job=job, nivel=nivel, mensaje=sanitize(mensaje),
            portal=portal, propiedad_id=propiedad_id,
            evento=evento, contexto=sanitize(contexto or {}),
        )


class ScrapingCandidate(models.Model):
    """Durable discovery queue and idempotent observation for one portal run."""
    run = models.ForeignKey(EjecucionPortal, on_delete=models.CASCADE, related_name='candidates')
    source_id = models.CharField(max_length=100)
    raw = models.JSONField(default=dict)
    page = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, default='pending', db_index=True)
    save_outcome = models.CharField(max_length=20, default='')
    error = models.TextField(default='', blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'scraping_candidates'
        constraints = [models.UniqueConstraint(fields=['run', 'source_id'], name='scrap_run_candidate_uq')]
        indexes = [models.Index(fields=['run', 'page', 'status'], name='scrap_candidate_pending_idx')]


class ScrapingHistoryRepair(models.Model):
    batch = models.UUIDField(db_index=True)
    propiedad = models.ForeignKey(PropiedadesCompetencia, on_delete=models.PROTECT)
    source = models.CharField(max_length=50)
    source_id = models.CharField(max_length=100)
    changes = models.JSONField()
    raw_sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    rolled_back_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'scraping_history_repairs'
        constraints = [models.UniqueConstraint(fields=['batch', 'propiedad'], name='scrap_repair_property_uq')]


class PublicacionFuente(models.Model):
    """Absences belong to a search scope, including overlapping searches."""
    source_key = models.CharField(max_length=64, db_index=True)
    propiedad = models.ForeignKey(PropiedadesCompetencia, on_delete=models.CASCADE, related_name='fuentes_observadas')
    last_run = models.ForeignKey(EjecucionPortal, on_delete=models.SET_NULL, null=True)
    misses = models.PositiveIntegerField(default=0)
    state = models.CharField(max_length=20, default='activa')
    first_missing_at = models.DateTimeField(null=True, blank=True)
    retired_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'scraping_publicacion_fuente'
        constraints = [models.UniqueConstraint(fields=['source_key', 'propiedad'], name='scrap_source_property_uq')]
