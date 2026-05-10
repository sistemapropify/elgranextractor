"""
Configuración del admin de Django para el sistema de Puntos de Interés (POIs).
Permite gestionar categorías/capas y puntos de interés desde el panel de admin.
"""
from django.contrib import admin
from .models import CategoriaPOI, PointOfInterest


@admin.register(CategoriaPOI)
class CategoriaPOIAdmin(admin.ModelAdmin):
    """
    Admin para gestionar categorías/capas de POIs.
    Cada categoría es una capa que puede activarse/desactivarse.
    """
    list_display = (
        'nombre', 'slug', 'icono', 'color_swatch', 'orden',
        'is_active', 'total_pois'
    )
    list_filter = ('is_active',)
    search_fields = ('nombre', 'slug', 'descripcion')
    prepopulated_fields = {'slug': ('nombre',)}
    ordering = ('orden', 'nombre')
    list_editable = ('orden', 'is_active')
    fieldsets = (
        ('Información básica', {
            'fields': ('nombre', 'slug', 'icono', 'color', 'descripcion'),
        }),
        ('Configuración', {
            'fields': ('orden', 'is_active'),
        }),
    )

    def color_swatch(self, obj):
        """Muestra una muestra del color en la lista."""
        return f'<span style="display:inline-block;width:20px;height:20px;border-radius:4px;background:{obj.color};border:1px solid #30363d;"></span> <code>{obj.color}</code>'
    color_swatch.short_description = 'Color'
    color_swatch.allow_tags = True

    def total_pois(self, obj):
        """Cantidad de POIs en esta categoría."""
        return obj.puntos.count()
    total_pois.short_description = 'POIs'


@admin.register(PointOfInterest)
class PointOfInterestAdmin(admin.ModelAdmin):
    """
    Admin para gestionar Puntos de Interés individuales.
    """
    list_display = (
        'nombre', 'categoria', 'latitud', 'longitud',
        'direccion_corta', 'is_active'
    )
    list_filter = ('categoria', 'is_active', 'categoria__is_active')
    search_fields = ('nombre', 'direccion', 'descripcion', 'telefono')
    ordering = ('categoria__nombre', 'nombre')
    list_editable = ('is_active',)
    list_select_related = ('categoria',)
    fieldsets = (
        ('Información básica', {
            'fields': ('nombre', 'categoria', 'is_active'),
        }),
        ('Ubicación', {
            'fields': ('latitud', 'longitud', 'direccion'),
        }),
        ('Contacto', {
            'fields': ('telefono', 'sitio_web'),
            'classes': ('collapse',),
        }),
        ('Descripción', {
            'fields': ('descripcion',),
            'classes': ('collapse',),
        }),
    )

    def direccion_corta(self, obj):
        """Dirección truncada para la lista."""
        if obj.direccion and len(obj.direccion) > 50:
            return obj.direccion[:50] + '...'
        return obj.direccion or '—'
    direccion_corta.short_description = 'Dirección'
