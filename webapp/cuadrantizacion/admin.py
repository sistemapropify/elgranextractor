from django.contrib import admin

from .models import CapaRasterMapa


@admin.register(CapaRasterMapa)
class CapaRasterMapaAdmin(admin.ModelAdmin):
    list_display = (
        'nombre', 'activo', 'visible', 'bloqueado',
        'opacidad', 'rotacion', 'escala', 'orden',
    )
    list_filter = ('activo', 'visible', 'bloqueado')
    search_fields = ('nombre', 'descripcion', 'imagen_url')
    readonly_fields = ('fecha_creacion', 'fecha_actualizacion')
    fieldsets = (
        ('Identificación', {
            'fields': ('nombre', 'descripcion', 'imagen_url', 'orden')
        }),
        ('Georreferenciación', {
            'fields': ('esquinas',),
            'description': 'Esquinas de la imagen en [longitud, latitud]: '
                           'tl, tr, br y bl.'
        }),
        ('Ajuste fino', {
            'fields': ('opacidad', 'rotacion', 'escala', 'offset_x', 'offset_y'),
            'description': 'Se puede calibrar visualmente en /cuadrantizacion/mapa/.'
        }),
        ('Estado', {
            'fields': ('visible', 'activo', 'bloqueado',
                       'fecha_creacion', 'fecha_actualizacion')
        }),
    )
