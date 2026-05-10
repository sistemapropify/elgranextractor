from django.contrib import admin
from .models import WhatsappGroupSession, ExtractorLog, ArchivoExtraccionWhatsApp


@admin.register(WhatsappGroupSession)
class WhatsappGroupSessionAdmin(admin.ModelAdmin):
    list_display = (
        'nombre_grupo', 'fuente_choice', 'activo',
        'ultima_extraccion', 'mensaje_error'
    )
    list_filter = ('activo', 'fuente_choice')
    search_fields = ('nombre_grupo',)
    readonly_fields = ('creado_en', 'actualizado_en')
    fieldsets = (
        ('Configuración del Grupo', {
            'fields': (
                'nombre_grupo', 'fuente_choice', 'activo',
            )
        }),
        ('Estado de Extracción', {
            'fields': (
                'ultima_extraccion', 'cookie_path', 'mensaje_error',
            )
        }),
        ('Auditoría', {
            'fields': ('creado_en', 'actualizado_en'),
            'classes': ('collapse',),
        }),
    )


@admin.register(ExtractorLog)
class ExtractorLogAdmin(admin.ModelAdmin):
    list_display = (
        'ejecucion_fecha', 'estado', 'mensajes_extraidos_total',
        'requerimientos_nuevos', 'requerimientos_duplicados',
        'tiempo_proceso_segundos'
    )
    list_filter = ('estado', 'ejecucion_fecha')
    readonly_fields = (
        'ejecucion_fecha', 'estado', 'mensajes_extraidos_total',
        'mensajes_validos', 'requerimientos_nuevos',
        'requerimientos_duplicados', 'requerimientos_basura_filtrados',
        'mensaje_error', 'stack_trace', 'tiempo_proceso_segundos',
        'grupo_procesado_ids'
    )

    def has_add_permission(self, request):
        # Los logs solo se crean automáticamente desde las tareas Celery
        return False

    def has_change_permission(self, request, obj=None):
        # Los logs son de solo lectura
        return False


@admin.register(ArchivoExtraccionWhatsApp)
class ArchivoExtraccionWhatsAppAdmin(admin.ModelAdmin):
    list_display = (
        'nombre_archivo_original', 'fecha_subida', 'tamanio_kb',
        'procesado', 'grupo_relacionado',
    )
    list_filter = ('procesado', 'fecha_subida')
    search_fields = ('nombre_archivo_original',)
    readonly_fields = ('fecha_subida', 'tamanio_kb')
    fieldsets = (
        ('Información del Archivo', {
            'fields': (
                'nombre_archivo_original', 'ruta_almacenamiento', 'tamanio_kb',
            )
        }),
        ('Estado de Procesamiento', {
            'fields': (
                'procesado', 'grupo_relacionado', 'log_asociado',
            )
        }),
        ('Auditoría', {
            'fields': ('fecha_subida', 'usuario_subida_id'),
            'classes': ('collapse',),
        }),
    )
