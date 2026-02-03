"""
Configuración de Django Admin para la app de captura.

Este módulo registra los modelos de captura en el panel de administración
de Django para facilitar su gestión.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.db.models import Count, Avg

from .models import CapturaCruda, EventoDeteccion


class EstadoFilter(admin.SimpleListFilter):
    """Filtro personalizado para el estado de capturas."""
    title = 'Estado'
    parameter_name = 'estado'
    
    def lookups(self, request, model_admin):
        return [
            ('exito', 'Éxito'),
            ('error', 'Error'),
            ('timeout', 'Timeout'),
            ('bloqueado', 'Bloqueado'),
        ]
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(estado=self.value())
        return queryset


class TamañoFilter(admin.SimpleListFilter):
    """Filtro personalizado para el tamaño de capturas."""
    title = 'Tamaño'
    parameter_name = 'tamaño'
    
    def lookups(self, request, model_admin):
        return [
            ('pequeno', 'Pequeño (< 10KB)'),
            ('mediano', 'Mediano (10KB - 100KB)'),
            ('grande', 'Grande (> 100KB)'),
        ]
    
    def queryset(self, request, queryset):
        if self.value() == 'pequeno':
            return queryset.filter(tamaño_bytes__lt=10240)
        elif self.value() == 'mediano':
            return queryset.filter(tamaño_bytes__gte=10240, tamaño_bytes__lt=102400)
        elif self.value() == 'grande':
            return queryset.filter(tamaño_bytes__gte=102400)
        return queryset


@admin.register(CapturaCruda)
class CapturaCrudaAdmin(admin.ModelAdmin):
    """Configuración de admin para el modelo CapturaCruda."""
    
    list_display = [
        'id', 'fuente_nombre', 'fecha_captura', 'estado_display',
        'status_code', 'tamaño_kb', 'tiempo_respuesta_ms', 'num_palabras',
        'es_reciente',
    ]
    
    list_filter = [
        EstadoFilter,
        TamañoFilter,
        'fuente',
        'fecha_captura',
        'status_code',
    ]
    
    search_fields = [
        'fuente__nombre',
        'fuente__url',
        'contenido_html',
        'mensaje_error',
    ]
    
    readonly_fields = [
        'fecha_captura', 'hash_sha256', 'hash_simplificado',
        'num_palabras', 'num_lineas', 'num_links', 'tamaño_bytes',
        'resumen_contenido', 'tamaño_kb', 'es_reciente',
    ]
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('fuente', 'fecha_captura', 'estado', 'es_reciente')
        }),
        ('Respuesta HTTP', {
            'fields': ('status_code', 'content_type', 'content_length', 'encoding', 'tiempo_respuesta_ms')
        }),
        ('Contenido', {
            'fields': ('contenido_html', 'resumen_contenido', 'tamaño_kb')
        }),
        ('Hashes', {
            'fields': ('hash_sha256', 'hash_simplificado'),
            'classes': ('collapse',)
        }),
        ('Estadísticas', {
            'fields': ('num_palabras', 'num_lineas', 'num_links'),
            'classes': ('collapse',)
        }),
        ('Errores', {
            'fields': ('mensaje_error', 'stack_trace'),
            'classes': ('collapse',)
        }),
    )
    
    ordering = ['-fecha_captura']
    date_hierarchy = 'fecha_captura'
    list_per_page = 50
    
    def fuente_nombre(self, obj):
        """Muestra el nombre de la fuente con enlace."""
        return format_html(
            '<a href="{}">{}</a>',
            f'/admin/semillas/fuenteweb/{obj.fuente.id}/change/',
            obj.fuente.nombre
        )
    fuente_nombre.short_description = 'Fuente'
    fuente_nombre.admin_order_field = 'fuente__nombre'
    
    def estado_display(self, obj):
        """Muestra el estado con colores."""
        colores = {
            'exito': 'green',
            'error': 'red',
            'timeout': 'orange',
            'bloqueado': 'gray',
        }
        color = colores.get(obj.estado, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_estado_display()
        )
    estado_display.short_description = 'Estado'
    
    def tamaño_kb(self, obj):
        """Muestra el tamaño en KB."""
        if obj.tamaño_bytes:
            return f'{obj.tamaño_bytes / 1024:.1f} KB'
        return 'N/A'
    tamaño_kb.short_description = 'Tamaño'
    
    def resumen_contenido(self, obj):
        """Muestra un resumen del contenido."""
        return obj.generar_resumen(max_length=200)
    resumen_contenido.short_description = 'Resumen'
    
    def es_reciente(self, obj):
        """Indica si la captura es reciente (< 1 hora)."""
        if not obj.fecha_captura:
            return False
        delta = timezone.now() - obj.fecha_captura
        return delta.total_seconds() < 3600
    es_reciente.short_description = 'Reciente'
    es_reciente.boolean = True
    
    actions = ['reprocesar_capturas', 'eliminar_capturas_antiguas']
    
    def reprocesar_capturas(self, request, queryset):
        """Acción para reprocesar capturas seleccionadas."""
        from colas.tasks import analizar_cambios
        
        for captura in queryset:
            analizar_cambios.delay(captura.id)
        
        self.message_user(
            request,
            f'{queryset.count()} capturas programadas para reprocesamiento.'
        )
    reprocesar_capturas.short_description = 'Reprocesar capturas seleccionadas'
    
    def eliminar_capturas_antiguas(self, request, queryset):
        """Acción para eliminar capturas antiguas."""
        # Filtrar capturas con más de 30 días
        from datetime import timedelta
        fecha_limite = timezone.now() - timedelta(days=30)
        
        capturas_antiguas = queryset.filter(fecha_captura__lt=fecha_limite)
        count = capturas_antiguas.count()
        
        if count == 0:
            self.message_user(request, 'No hay capturas antiguas para eliminar.')
            return
        
        capturas_antiguas.delete()
        self.message_user(request, f'{count} capturas antiguas eliminadas.')
    eliminar_capturas_antiguas.short_description = 'Eliminar capturas antiguas (> 30 días)'


class SeveridadFilter(admin.SimpleListFilter):
    """Filtro personalizado para la severidad de eventos."""
    title = 'Severidad'
    parameter_name = 'severidad'
    
    def lookups(self, request, model_admin):
        return [
            ('bajo', 'Bajo'),
            ('medio', 'Medio'),
            ('alto', 'Alto'),
            ('critico', 'Crítico'),
        ]
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(severidad=self.value())
        return queryset


class TipoCambioFilter(admin.SimpleListFilter):
    """Filtro personalizado para el tipo de cambio."""
    title = 'Tipo de Cambio'
    parameter_name = 'tipo_cambio'
    
    def lookups(self, request, model_admin):
        return [
            ('contenido', 'Contenido'),
            ('estructura', 'Estructura'),
            ('enlaces', 'Enlaces'),
            ('metadatos', 'Metadatos'),
            ('error', 'Error'),
        ]
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(tipo_cambio=self.value())
        return queryset


@admin.register(EventoDeteccion)
class EventoDeteccionAdmin(admin.ModelAdmin):
    """Configuración de admin para el modelo EventoDeteccion."""
    
    list_display = [
        'id', 'fuente_nombre', 'fecha_deteccion', 'tipo_cambio_display',
        'severidad_display', 'similitud_porcentaje', 'diferencia_palabras',
        'es_significativo', 'es_reciente',
    ]
    
    list_filter = [
        SeveridadFilter,
        TipoCambioFilter,
        'fuente',
        'fecha_deteccion',
        'analizado_por_ia',
    ]
    
    search_fields = [
        'fuente__nombre',
        'resumen_cambio',
        'contexto_anterior',
        'contexto_nuevo',
    ]
    
    readonly_fields = [
        'fecha_deteccion', 'similitud_porcentaje', 'diferencia_palabras',
        'diferencia_lineas', 'diferencia_enlaces', 'hash_anterior',
        'hash_nuevo', 'resumen_cambio', 'es_significativo', 'es_reciente',
        'tiempo_desde_deteccion',
    ]
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('fuente', 'fecha_deteccion', 'es_reciente', 'tiempo_desde_deteccion')
        }),
        ('Capturas', {
            'fields': ('captura_anterior', 'captura_nueva')
        }),
        ('Análisis', {
            'fields': ('tipo_cambio', 'severidad', 'similitud_porcentaje', 'es_significativo')
        }),
        ('Métricas', {
            'fields': ('diferencia_palabras', 'diferencia_lineas', 'diferencia_enlaces'),
            'classes': ('collapse',)
        }),
        ('Hashes', {
            'fields': ('hash_anterior', 'hash_nuevo'),
            'classes': ('collapse',)
        }),
        ('Contenido', {
            'fields': ('resumen_cambio', 'fragmentos_cambiados'),
            'classes': ('collapse',)
        }),
        ('Contexto', {
            'fields': ('contexto_anterior', 'contexto_nuevo'),
            'classes': ('collapse',)
        }),
        ('Análisis Avanzado', {
            'fields': ('analizado_por_ia', 'etiquetas_automaticas'),
            'classes': ('collapse',)
        }),
    )
    
    ordering = ['-fecha_deteccion']
    date_hierarchy = 'fecha_deteccion'
    list_per_page = 50
    
    def fuente_nombre(self, obj):
        """Muestra el nombre de la fuente con enlace."""
        return format_html(
            '<a href="{}">{}</a>',
            f'/admin/semillas/fuenteweb/{obj.fuente.id}/change/',
            obj.fuente.nombre
        )
    fuente_nombre.short_description = 'Fuente'
    fuente_nombre.admin_order_field = 'fuente__nombre'
    
    def tipo_cambio_display(self, obj):
        """Muestra el tipo de cambio con icono."""
        iconos = {
            'contenido': '📝',
            'estructura': '🏗️',
            'enlaces': '🔗',
            'metadatos': '🏷️',
            'error': '❌',
        }
        icono = iconos.get(obj.tipo_cambio, '')
        return f'{icono} {obj.get_tipo_cambio_display()}'
    tipo_cambio_display.short_description = 'Tipo'
    
    def severidad_display(self, obj):
        """Muestra la severidad con colores."""
        colores = {
            'bajo': 'green',
            'medio': 'blue',
            'alto': 'orange',
            'critico': 'red',
        }
        color = colores.get(obj.severidad, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_severidad_display()
        )
    severidad_display.short_description = 'Severidad'
    
    def es_significativo(self, obj):
        """Indica si el cambio es significativo."""
        return obj.severidad in ['alto', 'critico']
    es_significativo.short_description = 'Significativo'
    es_significativo.boolean = True
    
    def es_reciente(self, obj):
        """Indica si el evento es reciente (< 1 hora)."""
        if not obj.fecha_deteccion:
            return False
        delta = timezone.now() - obj.fecha_deteccion
        return delta.total_seconds() < 3600
    es_reciente.short_description = 'Reciente'
    es_reciente.boolean = True
    
    def tiempo_desde_deteccion(self, obj):
        """Muestra el tiempo desde la detección."""
        if not obj.fecha_deteccion:
            return 'N/A'
        
        delta = timezone.now() - obj.fecha_deteccion
        
        if delta.days > 0:
            return f'{delta.days} días'
        elif delta.seconds >= 3600:
            horas = delta.seconds // 3600
            return f'{horas} horas'
        elif delta.seconds >= 60:
            minutos = delta.seconds // 60
            return f'{minutos} minutos'
        else:
            return f'{delta.seconds} segundos'
    tiempo_desde_deteccion.short_description = 'Hace'
    
    actions = ['marcar_como_analizado', 'exportar_eventos']
    
    def marcar_como_analizado(self, request, queryset):
        """Marca eventos como analizados por IA."""
        updated = queryset.update(analizado_por_ia=True)
        self.message_user(request, f'{updated} eventos marcados como analizados por IA.')
    marcar_como_analizado.short_description = 'Marcar como analizado por IA'
    
    def exportar_eventos(self, request, queryset):
        """Exporta eventos seleccionados (acción de ejemplo)."""
        # En una implementación real, esto generaría un archivo CSV o JSON
        self.message_user(
            request,
            f'Preparando exportación de {queryset.count()} eventos...'
        )
    exportar_eventos.short_description = 'Exportar eventos seleccionados'