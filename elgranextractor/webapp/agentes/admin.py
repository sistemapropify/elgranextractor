from django.contrib import admin
from .models import Inmobiliaria, Agente


@admin.register(Inmobiliaria)
class InmobiliariaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'direccion', 'latitud', 'longitud', 'creado_en']
    search_fields = ['nombre']
    list_filter = []
    ordering = ['nombre']


@admin.register(Agente)
class AgenteAdmin(admin.ModelAdmin):
    list_display = ['nombre_completo', 'telefono', 'tipo_agente', 'inmobiliaria', 'creado_en']
    list_filter = ['tipo_agente', 'inmobiliaria']
    search_fields = ['nombre_completo', 'telefono']
    ordering = ['nombre_completo']
