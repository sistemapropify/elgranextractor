"""
Configuración simplificada del Django Admin para la app de Semillas.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import FuenteWeb


@admin.register(FuenteWeb)
class FuenteWebAdmin(admin.ModelAdmin):
    """Admin simplificado para el modelo FuenteWeb."""
    
    list_display = [
        'nombre',
        'url_truncada',
        'tipo',
        'categoria',
        'estado',
        'prioridad',
        'fecha_ultima_revision',
        'total_capturas',
    ]
    
    list_filter = [
        'tipo',
        'categoria',
        'estado',
        'prioridad',
    ]
    
    search_fields = [
        'nombre',
        'url',
    ]
    
    readonly_fields = [
        'fecha_creacion',
        'fecha_ultima_revision',
        'fecha_proxima_revision',
        'total_capturas',
        'total_cambios_detectados',
        'tasa_cambio_porcentaje',
    ]
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre', 'url', 'descripcion')
        }),
        ('Configuración de Monitoreo', {
            'fields': (
                'tipo',
                'categoria',
                'estado',
                'prioridad',
                'frecuencia_revision_horas',
            )
        }),
        ('Estadísticas', {
            'fields': (
                'fecha_creacion',
                'fecha_ultima_revision',
                'fecha_proxima_revision',
                'total_capturas',
                'total_cambios_detectados',
                'tasa_cambio_porcentaje',
            )
        }),
    )
    
    actions = [
        'activar_fuentes',
        'pausar_fuentes',
    ]
    
    def url_truncada(self, obj):
        """Muestra la URL truncada para mejor visualización."""
        if len(obj.url) > 40:
            return f'{obj.url[:37]}...'
        return obj.url
    url_truncada.short_description = 'URL'
    
    def activar_fuentes(self, request, queryset):
        """Activa las fuentes seleccionadas."""
        updated = queryset.update(estado='activa')
        self.message_user(
            request,
            f'{updated} fuente(s) activada(s) correctamente.'
        )
    activar_fuentes.short_description = 'Activar fuentes seleccionadas'
    
    def pausar_fuentes(self, request, queryset):
        """Pausa las fuentes seleccionadas."""
        updated = queryset.update(estado='pausada')
        self.message_user(
            request,
            f'{updated} fuente(s) pausada(s) correctamente.'
        )
    pausar_fuentes.short_description = 'Pausar fuentes seleccionadas'