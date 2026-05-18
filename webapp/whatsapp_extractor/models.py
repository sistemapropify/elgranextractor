"""
Modelos de la app whatsapp_extractor.

Gestiona la configuración de sesiones de grupos WhatsApp y el registro
de ejecuciones del sistema de extracción basado en exportación manual
de archivos .txt desde WhatsApp.

Refactorización (Camino 1):
    - Eliminado campo cookie_path (ya no se necesita login/cookies)
    - Eliminada lógica de scraping automático con Playwright
    - Nuevo modelo ArchivoExtraccionWhatsApp para trazabilidad de archivos
    - ExtractorLog ampliado con campos de archivo y usuario responsable
"""
from django.db import models
from django.conf import settings


# ─────────────────────────────────────────────
#  CHOICES
# ─────────────────────────────────────────────

class EstadoExtraccionChoices(models.TextChoices):
    """Estados posibles de una ejecución de extracción."""
    PENDING  = 'pending',   'Pendiente'
    RUNNING  = 'running',   'En ejecución'
    PAUSED   = 'paused',    'Pausado'
    COMPLETED = 'completed', 'Completado'
    ERROR    = 'error',     'Error'


# ─────────────────────────────────────────────
#  MODELO PRINCIPAL: WhatsappGroupSession
# ─────────────────────────────────────────────

class WhatsappGroupSession(models.Model):
    """
    Gestiona la configuración de sesiones para cada grupo de WhatsApp.

    Cada registro representa un grupo de WhatsApp del cual se extraen
    requerimientos inmobiliarios mediante exportación manual de .txt.

    Relación con Requerimientos:
        - fuente_choice se vincula con FuenteChoices del módulo requerimientos
        - Los mensajes extraídos se transforman en objetos Requerimiento

    Nota: El campo cookie_path fue eliminado en la refactorización
    al migrar de scraping automático a exportación manual.
    """

    nombre_grupo = models.CharField(
        max_length=255,
        unique=True,
        verbose_name='Nombre del grupo',
        help_text='Nombre exacto como aparece en WhatsApp',
        db_index=True,
    )
    fuente_choice = models.CharField(
        max_length=50,
        verbose_name='Fuente (choice)',
        help_text='Valor de FuenteChoices del módulo requerimientos para vincular',
        db_index=True,
    )
    ultima_extraccion = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Última extracción',
        help_text='Fecha/hora de la última extracción exitosa',
    )
    activo = models.BooleanField(
        default=True,
        verbose_name='Activo',
        help_text='Si está activo, el grupo aparecerá como opción al subir archivos',
        db_index=True,
    )
    mensaje_error = models.TextField(
        blank=True,
        verbose_name='Último error',
        help_text='Último mensaje de error registrado durante la extracción',
    )

    # ── Auditoría ─────────────────────────────
    creado_en = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Creado en',
    )
    actualizado_en = models.DateTimeField(
        auto_now=True,
        verbose_name='Actualizado en',
    )

    class Meta:
        db_table = 'whatsapp_group_session'
        verbose_name = 'Sesión de Grupo WhatsApp'
        verbose_name_plural = 'Sesiones de Grupos WhatsApp'
        ordering = ['-activo', 'nombre_grupo']
        indexes = [
            models.Index(fields=['activo', 'fuente_choice'], name='idx_ws_grupo_activo_fuente'),
        ]

    def __str__(self):
        return f"[{'ACT' if self.activo else 'INA'}] {self.nombre_grupo}"

    def marcar_extraccion_exitosa(self):
        """Actualiza la fecha de última extracción y limpia errores."""
        from django.utils import timezone
        self.ultima_extraccion = timezone.now()
        self.mensaje_error = ''
        self.save(update_fields=['ultima_extraccion', 'mensaje_error', 'actualizado_en'])

    def marcar_error(self, error_msg: str):
        """Registra un mensaje de error en la sesión."""
        self.mensaje_error = error_msg[:2000]  # Limitar longitud
        self.save(update_fields=['mensaje_error', 'actualizado_en'])


# ─────────────────────────────────────────────
#  MODELO DE LOG: ExtractorLog
# ─────────────────────────────────────────────

class ExtractorLog(models.Model):
    """
    Registra cada ejecución del sistema de extracción.

    Proporciona trazabilidad completa de cada procesamiento de archivo,
    incluyendo métricas de rendimiento, archivo origen y usuario responsable.

    Este modelo es de SOLO LECTURA desde el admin. Los registros
    se crean automáticamente desde las tareas Celery o vistas de upload.
    """

    ejecucion_fecha = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de ejecución',
        db_index=True,
    )
    estado = models.CharField(
        max_length=20,
        choices=EstadoExtraccionChoices.choices,
        default=EstadoExtraccionChoices.PENDING,
        verbose_name='Estado',
        db_index=True,
    )

    # ── Archivo origen (Camino 1: exportación manual) ──
    archivo_subido = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='Archivo subido',
        help_text='Ruta al archivo .txt subido para procesamiento',
    )
    grupo_asociado = models.ForeignKey(
        WhatsappGroupSession,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Grupo asociado',
        help_text='Grupo seleccionado en UI al subir archivo',
        related_name='logs_extraccion',
    )

    # ── Métricas de extracción ────────────────
    mensajes_extraidos_total = models.IntegerField(
        default=0,
        verbose_name='Total mensajes extraídos',
        help_text='Total de mensajes leídos del archivo .txt',
    )
    mensajes_validos = models.IntegerField(
        default=0,
        verbose_name='Mensajes válidos',
        help_text='Mensajes filtrados que pasaron validación inicial',
    )
    requerimientos_nuevos = models.IntegerField(
        default=0,
        verbose_name='Requerimientos nuevos',
        help_text='Nuevos registros creados en la BD',
    )
    requerimientos_duplicados = models.IntegerField(
        default=0,
        verbose_name='Requerimientos duplicados',
        help_text='Ignorados por deduplicación vía IA',
    )
    requerimientos_basura_filtrados = models.IntegerField(
        default=0,
        verbose_name='Basura filtrada',
        help_text='Mensajes ignorados por reglas de contenido irrelevante',
    )

    # ── Error handling ────────────────────────
    mensaje_error = models.TextField(
        blank=True,
        default='',
        verbose_name='Mensaje de error',
        help_text='Error principal si el estado es "error"',
    )
    stack_trace = models.TextField(
        blank=True,
        default='',
        verbose_name='Stack trace',
        help_text='Rastreo completo del error',
    )

    # ── Métricas de rendimiento ───────────────
    tiempo_proceso_segundos = models.IntegerField(
        null=True, blank=True,
        verbose_name='Tiempo de proceso (s)',
        help_text='Duración total del proceso en segundos',
    )
    grupo_procesado_ids = models.JSONField(
        default=list,
        verbose_name='IDs de grupos procesados',
        help_text='Lista de IDs de WhatsappGroupSession procesados en esta ejecución',
    )

    # ── Usuario responsable (Camino 1) ───────
    usuario_procesador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Usuario procesador',
        help_text='Usuario que realizó la subida del archivo',
        related_name='extracciones_whatsapp',
    )

    class Meta:
        db_table = 'whatsapp_extractor_log'
        verbose_name = 'Log de Extracción'
        verbose_name_plural = 'Logs de Extracción'
        ordering = ['-ejecucion_fecha']
        indexes = [
            models.Index(fields=['estado', 'ejecucion_fecha'], name='idx_ws_log_estado_fecha'),
        ]

    def __str__(self):
        return (
            f"[{self.get_estado_display()}] "
            f"{self.ejecucion_fecha.strftime('%Y-%m-%d %H:%M')} — "
            f"{self.requerimientos_nuevos} nuevos, "
            f"{self.requerimientos_duplicados} duplicados"
        )

    @property
    def duracion_formateada(self) -> str:
        """Devuelve la duración en formato legible."""
        if not self.tiempo_proceso_segundos:
            return '—'
        minutos = self.tiempo_proceso_segundos // 60
        segundos = self.tiempo_proceso_segundos % 60
        if minutos > 0:
            return f'{minutos}m {segundos}s'
        return f'{segundos}s'

    @property
    def tasa_exito(self) -> float:
        """Porcentaje de mensajes que se convirtieron en requerimientos."""
        if self.mensajes_extraidos_total == 0:
            return 0.0
        return round(
            (self.requerimientos_nuevos / self.mensajes_extraidos_total) * 100,
            2
        )


# ─────────────────────────────────────────────
#  LOGS DETALLADOS DE EJECUCIÓN (en vivo)
# ─────────────────────────────────────────────


class LogEntry(models.Model):
    """
    Registro detallado de cada paso de una extracción.

    Permite hacer tracking en vivo del progreso de la tarea Celery.
    Cada entrada tiene un timestamp, nivel (INFO/WARNING/ERROR/DEBUG)
    y un mensaje descriptivo.

    Se relaciona con ExtractorLog para agrupar todos los pasos
    de una misma ejecución.
    """

    NIVELES = [
        ('DEBUG',   'DEBUG'),
        ('INFO',    'INFO'),
        ('WARNING', 'WARNING'),
        ('ERROR',   'ERROR'),
    ]

    extractor_log = models.ForeignKey(
        ExtractorLog,
        on_delete=models.CASCADE,
        related_name='entries',
        verbose_name='Log de extracción',
        db_index=True,
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Timestamp',
        db_index=True,
    )
    nivel = models.CharField(
        max_length=10,
        choices=NIVELES,
        default='INFO',
        verbose_name='Nivel',
    )
    mensaje = models.TextField(
        verbose_name='Mensaje',
        help_text='Descripción del paso ejecutado',
    )
    detalles = models.JSONField(
        default=dict, blank=True,
        verbose_name='Detalles adicionales',
        help_text='Datos estructurados adicionales (métricas parciales, etc.)',
    )

    class Meta:
        db_table = 'whatsapp_extractor_log_entry'
        verbose_name = 'Entrada de log detallado'
        verbose_name_plural = 'Entradas de log detallado'
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['extractor_log', 'timestamp'], name='idx_ws_entry_log_ts'),
        ]

    def __str__(self):
        return f"[{self.get_nivel_display()}] {self.timestamp.strftime('%H:%M:%S')} — {self.mensaje[:80]}"


# ─────────────────────────────────────────────
#  MODELO NUEVO: ArchivoExtraccionWhatsApp
# ─────────────────────────────────────────────

class ArchivoExtraccionWhatsApp(models.Model):
    """
    Rastrea archivos temporales subidos antes del procesamiento.

    Proporciona trazabilidad completa del ciclo de vida del archivo:
    desde la subida hasta el procesamiento, incluyendo metadata
    del archivo original y vinculación con el log resultante.

    Propósito:
        - Auditoría de archivos procesados
        - Posibilidad de re-procesamiento
        - Limpieza automática de archivos temporales
    """

    nombre_archivo_original = models.CharField(
        max_length=255,
        verbose_name='Nombre original',
        help_text='Nombre original del archivo .txt subido',
    )
    ruta_almacenamiento = models.CharField(
        max_length=500,
        verbose_name='Ruta de almacenamiento',
        help_text='Ruta donde se guardó el archivo en el servidor',
    )
    tamanio_kb = models.IntegerField(
        default=0,
        verbose_name='Tamaño (KB)',
        help_text='Tamaño en kilobytes del archivo',
    )
    fecha_subida = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de subida',
        db_index=True,
    )
    grupo_relacionado = models.ForeignKey(
        WhatsappGroupSession,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Grupo relacionado',
        help_text='Grupo de WhatsApp asociado a esta extracción',
        related_name='archivos_extraccion',
    )
    procesado = models.BooleanField(
        default=False,
        verbose_name='Procesado',
        help_text='Indica si el archivo ya fue procesado',
        db_index=True,
    )
    log_asociado = models.ForeignKey(
        ExtractorLog,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Log asociado',
        help_text='Log resultante del procesamiento de este archivo',
        related_name='archivos_origen',
    )
    usuario_subida_id = models.CharField(
        max_length=36,
        null=True, blank=True,
        verbose_name='Usuario que subió (UUID)',
        help_text='UUID del usuario que realizó la subida del archivo',
        db_column='usuario_subida_id',
    )

    class Meta:
        db_table = 'whatsapp_archivo_extraccion'
        verbose_name = 'Archivo de Extracción WhatsApp'
        verbose_name_plural = 'Archivos de Extracción WhatsApp'
        ordering = ['-fecha_subida']
        indexes = [
            models.Index(fields=['procesado', 'fecha_subida'], name='idx_ws_archivo_proc_fecha'),
        ]

    def __str__(self):
        estado = '✓' if self.procesado else '⏳'
        return f"{estado} {self.nombre_archivo_original} ({self.tamanio_kb} KB)"

    @property
    def tamanio_formateado(self) -> str:
        """Retorna el tamaño en formato legible."""
        if self.tamanio_kb < 1024:
            return f"{self.tamanio_kb} KB"
        mb = self.tamanio_kb / 1024
        return f"{mb:.1f} MB"
