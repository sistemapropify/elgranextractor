"""
Modelos para almacenamiento y gestión de capturas crudas de contenido web.
"""
from django.db import models
from django.utils import timezone
from semillas.models import FuenteWeb
import hashlib


class CapturaCruda(models.Model):
    """
    Representa una captura cruda del contenido HTML de una fuente web en un momento específico.
    """
    ESTADO_CAPTURA_CHOICES = [
        ('exito', 'Éxito'),
        ('error', 'Error'),
        ('timeout', 'Timeout'),
        ('bloqueado', 'Bloqueado'),
    ]
    
    # Relación con la fuente
    fuente = models.ForeignKey(
        FuenteWeb,
        on_delete=models.CASCADE,
        related_name='capturas',
        verbose_name='Fuente web'
    )
    
    # Metadatos de la captura
    fecha_captura = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de captura'
    )
    estado = models.CharField(
        max_length=10,
        choices=ESTADO_CAPTURA_CHOICES,
        default='exito',
        verbose_name='Estado de la captura'
    )
    
    # Información de la respuesta HTTP
    status_code = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Código de estado HTTP'
    )
    content_type = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Content-Type'
    )
    content_length = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Longitud del contenido (bytes)'
    )
    encoding = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Codificación del contenido'
    )
    
    # Contenido y hash
    contenido_html = models.TextField(
        verbose_name='Contenido HTML crudo'
    )
    hash_sha256 = models.CharField(
        max_length=64,
        db_index=True,
        verbose_name='Hash SHA-256 del contenido'
    )
    hash_simplificado = models.CharField(
        max_length=64,
        db_index=True,
        verbose_name='Hash simplificado (sin whitespace)'
    )
    
    # Estadísticas del contenido
    num_palabras = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Número de palabras'
    )
    num_lineas = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Número de líneas'
    )
    num_links = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Número de enlaces'
    )
    
    # Información de rendimiento
    tiempo_respuesta_ms = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Tiempo de respuesta (ms)'
    )
    tamaño_bytes = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Tamaño en bytes'
    )
    
    # Campos para manejo de errores
    mensaje_error = models.TextField(
        blank=True,
        verbose_name='Mensaje de error'
    )
    stack_trace = models.TextField(
        blank=True,
        verbose_name='Stack trace (si aplica)'
    )
    
    class Meta:
        verbose_name = 'Captura Cruda'
        verbose_name_plural = 'Capturas Crudas'
        ordering = ['-fecha_captura']
        indexes = [
            models.Index(fields=['fuente', '-fecha_captura']),
            models.Index(fields=['hash_sha256']),
            models.Index(fields=['estado', 'fecha_captura']),
        ]
        unique_together = [['fuente', 'hash_sha256']]
    
    def __str__(self):
        return f'Captura de {self.fuente.nombre} - {self.fecha_captura.strftime("%Y-%m-%d %H:%M")}'
    
    def save(self, *args, **kwargs):
        """Calcula los hashes antes de guardar."""
        if self.contenido_html and not self.hash_sha256:
            self.hash_sha256 = self.calcular_hash_sha256(self.contenido_html)
            self.hash_simplificado = self.calcular_hash_simplificado(self.contenido_html)
        
        # Calcular estadísticas básicas si no están definidas
        if self.contenido_html and self.num_palabras is None:
            self.calcular_estadisticas()
        
        super().save(*args, **kwargs)
    
    @staticmethod
    def calcular_hash_sha256(contenido):
        """Calcula el hash SHA-256 del contenido."""
        return hashlib.sha256(contenido.encode('utf-8')).hexdigest()
    
    @staticmethod
    def calcular_hash_simplificado(contenido):
        """
        Calcula un hash simplificado que ignora whitespace y diferencias menores.
        Útil para detectar cambios significativos.
        """
        # Eliminar espacios en blanco múltiples y saltos de línea
        contenido_simplificado = ' '.join(contenido.split())
        # Convertir a minúsculas para hacerlo case-insensitive
        contenido_simplificado = contenido_simplificado.lower()
        return hashlib.sha256(contenido_simplificado.encode('utf-8')).hexdigest()
    
    def calcular_estadisticas(self):
        """Calcula estadísticas básicas del contenido HTML."""
        if not self.contenido_html:
            return
        
        # Número de palabras (aproximado)
        palabras = self.contenido_html.split()
        self.num_palabras = len(palabras)
        
        # Número de líneas
        self.num_lineas = self.contenido_html.count('\n') + 1
        
        # Número de enlaces (contando href=)
        self.num_links = self.contenido_html.count('href=') + self.contenido_html.count('src=')
        
        # Tamaño en bytes
        self.tamaño_bytes = len(self.contenido_html.encode('utf-8'))
    
    def es_duplicado_de(self, otra_captura):
        """Verifica si esta captura es duplicado de otra captura."""
        return self.hash_sha256 == otra_captura.hash_sha256
    
    def obtener_captura_anterior(self):
        """Obtiene la captura anterior de la misma fuente."""
        return CapturaCruda.objects.filter(
            fuente=self.fuente,
            fecha_captura__lt=self.fecha_captura
        ).order_by('-fecha_captura').first()
    
    def generar_resumen(self, max_length=200):
        """Genera un resumen del contenido para visualización."""
        if not self.contenido_html:
            return ''
        
        # Extraer texto limpio (sin etiquetas HTML)
        import re
        texto_limpio = re.sub(r'<[^>]+>', ' ', self.contenido_html)
        texto_limpio = re.sub(r'\s+', ' ', texto_limpio).strip()
        
        if len(texto_limpio) <= max_length:
            return texto_limpio
        
        return texto_limpio[:max_length] + '...'


class EventoDeteccion(models.Model):
    """
    Representa un evento de detección de cambios entre dos capturas de la misma fuente.
    """
    TIPO_CAMBIO_CHOICES = [
        ('contenido', 'Cambio de contenido'),
        ('estructura', 'Cambio de estructura'),
        ('enlaces', 'Cambio en enlaces'),
        ('metadatos', 'Cambio en metadatos'),
        ('error', 'Error en comparación'),
    ]
    
    SEVERIDAD_CHOICES = [
        ('bajo', 'Bajo'),
        ('medio', 'Medio'),
        ('alto', 'Alto'),
        ('critico', 'Crítico'),
    ]
    
    # Relaciones con las capturas
    fuente = models.ForeignKey(
        FuenteWeb,
        on_delete=models.CASCADE,
        related_name='eventos_deteccion',
        verbose_name='Fuente web'
    )
    captura_anterior = models.ForeignKey(
        CapturaCruda,
        on_delete=models.CASCADE,
        related_name='eventos_como_anterior',
        verbose_name='Captura anterior'
    )
    captura_nueva = models.ForeignKey(
        CapturaCruda,
        on_delete=models.CASCADE,
        related_name='eventos_como_nueva',
        verbose_name='Captura nueva'
    )
    
    # Información del evento
    fecha_deteccion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de detección'
    )
    tipo_cambio = models.CharField(
        max_length=20,
        choices=TIPO_CAMBIO_CHOICES,
        verbose_name='Tipo de cambio'
    )
    severidad = models.CharField(
        max_length=10,
        choices=SEVERIDAD_CHOICES,
        default='medio',
        verbose_name='Severidad del cambio'
    )
    
    # Métricas de diferencia
    similitud_porcentaje = models.FloatField(
        verbose_name='Porcentaje de similitud'
    )
    diferencia_palabras = models.IntegerField(
        verbose_name='Diferencia en palabras'
    )
    diferencia_lineas = models.IntegerField(
        verbose_name='Diferencia en líneas'
    )
    diferencia_enlaces = models.IntegerField(
        verbose_name='Diferencia en enlaces'
    )
    
    # Hash comparativos
    hash_anterior = models.CharField(
        max_length=64,
        verbose_name='Hash de la captura anterior'
    )
    hash_nuevo = models.CharField(
        max_length=64,
        verbose_name='Hash de la captura nueva'
    )
    
    # Análisis del cambio
    resumen_cambio = models.TextField(
        verbose_name='Resumen del cambio'
    )
    fragmentos_cambiados = models.JSONField(
        default=list,
        verbose_name='Fragmentos cambiados'
    )
    contexto_anterior = models.TextField(
        blank=True,
        verbose_name='Contexto anterior'
    )
    contexto_nuevo = models.TextField(
        blank=True,
        verbose_name='Contexto nuevo'
    )
    
    # Metadatos
    analizado_por_ia = models.BooleanField(
        default=False,
        verbose_name='Analizado por IA'
    )
    etiquetas_automaticas = models.JSONField(
        default=list,
        verbose_name='Etiquetas automáticas'
    )
    
    class Meta:
        verbose_name = 'Evento de Detección'
        verbose_name_plural = 'Eventos de Detección'
        ordering = ['-fecha_deteccion']
        indexes = [
            models.Index(fields=['fuente', '-fecha_deteccion']),
            models.Index(fields=['tipo_cambio', 'severidad']),
            models.Index(fields=['similitud_porcentaje']),
        ]
    
    def __str__(self):
        return f'Evento en {self.fuente.nombre} - {self.tipo_cambio} ({self.severidad})'
    
    def calcular_metricas_diferencia(self):
        """Calcula métricas de diferencia entre las dos capturas."""
        if not self.captura_anterior or not self.captura_nueva:
            return
        
        # Calcular diferencia en palabras
        palabras_anterior = self.captura_anterior.num_palabras or 0
        palabras_nueva = self.captura_nueva.num_palabras or 0
        self.diferencia_palabras = abs(palabras_nueva - palabras_anterior)
        
        # Calcular diferencia en líneas
        lineas_anterior = self.captura_anterior.num_lineas or 0
        lineas_nueva = self.captura_nueva.num_lineas or 0
        self.diferencia_lineas = abs(lineas_nueva - lineas_anterior)
        
        # Calcular diferencia en enlaces
        enlaces_anterior = self.captura_anterior.num_links or 0
        enlaces_nueva = self.captura_nueva.num_links or 0
        self.diferencia_enlaces = abs(enlaces_nueva - enlaces_anterior)
        
        # Calcular porcentaje de similitud basado en hash simplificado
        if self.captura_anterior.hash_simplificado == self.captura_nueva.hash_simplificado:
            self.similitud_porcentaje = 100.0
        else:
            # Estimación simple basada en tamaño
            tamaño_anterior = self.captura_anterior.tamaño_bytes or 1
            tamaño_nueva = self.captura_nueva.tamaño_bytes or 1
            tamaño_min = min(tamaño_anterior, tamaño_nueva)
            tamaño_max = max(tamaño_anterior, tamaño_nueva)
            self.similitud_porcentaje = (tamaño_min / tamaño_max) * 100
        
        # Guardar hashes
        self.hash_anterior = self.captura_anterior.hash_sha256
        self.hash_nuevo = self.captura_nueva.hash_sha256
        
        self.save()
    
    def determinar_severidad_automaticamente(self):
        """Determina automáticamente la severidad basada en las métricas."""
        if self.similitud_porcentaje > 95:
            self.severidad = 'bajo'
        elif self.similitud_porcentaje > 80:
            self.severidad = 'medio'
        elif self.similitud_porcentaje > 50:
            self.severidad = 'alto'
        else:
            self.severidad = 'critico'
        
        # Ajustar basado en tipo de cambio
        if self.tipo_cambio == 'error':
            self.severidad = 'critico'
        elif self.tipo_cambio == 'estructura':
            self.severidad = max(self.severidad, 'alto')  # Subir al menos a alto
        
        self.save()
    
    def generar_resumen_automatico(self):
        """Genera un resumen automático del cambio."""
        if self.similitud_porcentaje > 99:
            resumen = "Cambios mínimos detectados"
        elif self.similitud_porcentaje > 90:
            resumen = f"Cambios menores: {self.diferencia_palabras} palabras, {self.diferencia_lineas} líneas"
        elif self.similitud_porcentaje > 70:
            resumen = f"Cambios moderados: {self.diferencia_palabras} palabras, {self.diferencia_enlaces} enlaces"
        else:
            resumen = f"Cambios significativos: similitud {self.similitud_porcentaje:.1f}%"
        
        self.resumen_cambio = resumen
        self.save()