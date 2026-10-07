from django.contrib import admin

from .models import CapaRasterMapa, CapaVectorialMapa, ZonaUso, Zonificacion


@admin.register(CapaVectorialMapa)
class CapaVectorialMapaAdmin(admin.ModelAdmin):
    list_display = (
        'nombre', 'activo', 'visible', 'opacidad',
        'color_borde', 'grosor_borde', 'orden',
    )
    list_filter = ('activo', 'visible')
    search_fields = ('nombre', 'descripcion', 'geojson_url')
    readonly_fields = ('fecha_creacion', 'fecha_actualizacion')


@admin.register(Zonificacion)
class ZonificacionAdmin(admin.ModelAdmin):
    list_display = (
        'fuente', 'propiedad_id', 'codigo', 'nombre',
        'confianza', 'verificada', 'fecha_verificacion',
    )
    list_filter = ('fuente', 'codigo', 'verificada', 'confianza', 'origen_calculo')
    search_fields = ('propiedad_id', 'propiedad_ref', 'codigo', 'nombre')
    readonly_fields = ('fecha_calculo', 'fecha_actualizacion')
    list_editable = ('verificada',)
    list_per_page = 50


@admin.register(ZonaUso)
class ZonaUsoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'categoria', 'color', 'orden', 'activo')
    list_filter = ('categoria', 'activo')
    search_fields = ('codigo', 'nombre', 'categoria')
    ordering = ('orden', 'codigo')
    readonly_fields = ('fecha_creacion', 'fecha_actualizacion')


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
