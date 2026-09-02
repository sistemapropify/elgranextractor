from django.contrib import admin
from .models import CrmVisitIntentAlert, MobileAppVersion, MobileNotificationDevice, MobileProspectUser, PropertyProspect


@admin.register(MobileProspectUser)
class MobileProspectUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'can_view_crm_alerts', 'created_at')
    list_editable = ('can_view_crm_alerts',)


@admin.register(CrmVisitIntentAlert)
class CrmVisitIntentAlertAdmin(admin.ModelAdmin):
    list_display = ('source_lead_id', 'agent_name', 'contact_name', 'detected_at', 'responded_at', 'status')
    list_filter = ('status', 'agent_name')
    search_fields = ('contact_name', 'phone', 'agent_name', 'property_code')


@admin.register(MobileNotificationDevice)
class MobileNotificationDeviceAdmin(admin.ModelAdmin):
    list_display = ('user', 'device_name', 'target_type', 'active', 'updated_at')
    list_filter = ('target_type', 'active')


@admin.register(MobileAppVersion)
class MobileAppVersionAdmin(admin.ModelAdmin):
    list_display = ('version_code', 'version_name', 'published', 'force_update', 'min_supported_version_code', 'created_at')
    list_filter = ('published', 'force_update')
    search_fields = ('version_name', 'release_notes')
    ordering = ('-version_code',)


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
