from django.contrib import admin
from .models import PropertyProspect


@admin.register(PropertyProspect)
class PropertyProspectAdmin(admin.ModelAdmin):
    list_display = [
        'pk', 'agent', 'district', 'property_type',
        'operation_type', 'price', 'currency',
        'status', 'created_at',
    ]
    list_filter = ['status', 'property_type', 'operation_type', 'district']
    search_fields = ['owner_name', 'phone', 'address', 'district', 'notes']
    readonly_fields = ['created_at', 'updated_at', 'ocr_processed_at']
    raw_id_fields = ['agent']

    fieldsets = (
        ('Foto y Ubicación', {
            'fields': ('photo', 'latitude', 'longitude', 'address', 'district'),
        }),
        ('Datos del Propietario', {
            'fields': ('owner_name', 'phone'),
        }),
        ('Información del Inmueble', {
            'fields': ('operation_type', 'property_type', 'price', 'currency', 'bedrooms', 'area_m2'),
        }),
        ('Procesamiento IA', {
            'fields': ('ocr_raw_text', 'ocr_processed_at'),
            'classes': ('collapse',),
        }),
        ('Seguimiento', {
            'fields': ('status', 'notes', 'agent'),
        }),
        ('Fechas', {
            'fields': ('created_at', 'updated_at'),
        }),
    )
