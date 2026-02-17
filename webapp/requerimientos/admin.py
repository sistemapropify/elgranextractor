from django.contrib import admin
from .models import (
    CampoDinamicoRequerimiento,
    MapeoFuenteRequerimiento,
    RequerimientoRaw,
    MigracionPendienteRequerimiento
)


@admin.register(CampoDinamicoRequerimiento)
class CampoDinamicoRequerimientoAdmin(admin.ModelAdmin):
    list_display = ('nombre_campo_bd', 'titulo_display', 'tipo_dato', 'creado_por', 'creado_en')
    list_filter = ('tipo_dato', 'creado_en')
    search_fields = ('nombre_campo_bd', 'titulo_display')
    readonly_fields = ('creado_en',)


@admin.register(MapeoFuenteRequerimiento)
class MapeoFuenteRequerimientoAdmin(admin.ModelAdmin):
    list_display = ('nombre_fuente', 'portal_origen', 'creado_en', 'actualizado_en')
    list_filter = ('portal_origen', 'creado_en')
    search_fields = ('nombre_fuente', 'portal_origen')
    readonly_fields = ('creado_en', 'actualizado_en')


@admin.register(RequerimientoRaw)
class RequerimientoRawAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'fuente_excel',
        'fecha_ingesta',
        'get_cliente_nombre',
        'get_tipo_requerimiento',
    )
    list_filter = ('fuente_excel', 'fecha_ingesta')
    search_fields = ('atributos_extras', 'fuente_excel')
    readonly_fields = ('fecha_ingesta',)
    fieldsets = (
        ('Metadatos', {
            'fields': ('fuente_excel', 'fecha_ingesta')
        }),
        ('Atributos Dinámicos', {
            'fields': ('atributos_extras',),
            'description': 'Todos los campos del Excel se almacenan aquí como JSON'
        }),
    )
    
    def get_cliente_nombre(self, obj):
        return obj.atributos_extras.get('cliente_nombre', 'Sin nombre')
    get_cliente_nombre.short_description = 'Cliente'
    
    def get_tipo_requerimiento(self, obj):
        return obj.atributos_extras.get('tipo_requerimiento', 'Sin tipo')
    get_tipo_requerimiento.short_description = 'Tipo'


@admin.register(MigracionPendienteRequerimiento)
class MigracionPendienteRequerimientoAdmin(admin.ModelAdmin):
    list_display = ('nombre_campo_bd', 'titulo_display', 'tipo_dato', 'estado', 'creado_en', 'ejecutada_en')
    list_filter = ('estado', 'tipo_dato', 'creado_en')
    search_fields = ('nombre_campo_bd', 'titulo_display', 'error_mensaje')
    readonly_fields = ('creado_en', 'ejecutada_en', 'error_mensaje')
