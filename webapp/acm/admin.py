from django.contrib import admin
from django.utils.html import format_html
from .models import ACMLink

# Dominio base para enlaces públicos
DOMINIO_BASE = "https://acm.propifai.com"


@admin.register(ACMLink)
class ACMLinkAdmin(admin.ModelAdmin):
    """
    Admin para gestionar enlaces ACM compartidos por WhatsApp.
    Muestra el historial de análisis compartidos y sus clicks.
    """
    list_display = [
        'short_id',
        'enlace_pdf',
        'user',
        'tipo_propiedad',
        'area_m2',
        'valor_comercial_formateado',
        'click_count',
        'created_at',
    ]
    list_filter = [
        'tipo_propiedad',
        'es_terreno',
        'created_at',
    ]
    search_fields = [
        'user__username',
        'user__email',
        'tipo_propiedad',
    ]
    readonly_fields = [
        'id',
        'enlace_pdf_detalle',
        'click_count',
        'created_at',
        'last_click_at',
        'propiedades_json',
    ]
    ordering = ['-created_at']
    date_hierarchy = 'created_at'

    fieldsets = [
        ('Información del usuario', {
            'fields': ['user', 'id'],
        }),
        ('Enlace público', {
            'fields': ['enlace_pdf_detalle'],
        }),
        ('Parámetros del análisis', {
            'fields': [
                'tipo_propiedad',
                'area_m2',
                'es_terreno',
            ],
        }),
        ('Resultados del análisis', {
            'fields': [
                'precio_min_m2',
                'precio_max_m2',
                'precio_promedio_m2',
                'precio_promedio_ponderado_m2',
                'valor_comercial',
                'precio_venta_sugerido',
                'valor_realizacion',
                'num_comparables',
            ],
        }),
        ('Tracking', {
            'fields': ['click_count', 'last_click_at', 'created_at'],
        }),
        ('Datos completos (solo lectura)', {
            'fields': ['propiedades_json'],
            'classes': ['collapse'],
        }),
    ]

    def short_id(self, obj):
        return obj.short_id
    short_id.short_description = 'ID'

    def enlace_pdf(self, obj):
        """Muestra el enlace al PDF como un link clickeable en la lista."""
        url = f"{DOMINIO_BASE}/acm/ver-pdf/{obj.id}/"
        return format_html(
            '<a href="{}" target="_blank" title="Abrir PDF en nueva pestaña">🔗 {}</a>',
            url, obj.short_id
        )
    enlace_pdf.short_description = 'PDF'

    def enlace_pdf_detalle(self, obj):
        """Muestra el enlace completo en la vista de detalle."""
        url = f"{DOMINIO_BASE}/acm/ver-pdf/{obj.id}/"
        return format_html(
            '<a href="{}" target="_blank" style="font-size:14px;">{}</a><br>'
            '<small style="color:#6b7280;">Haz clic para abrir el PDF del análisis en una nueva pestaña</small>',
            url, url
        )
    enlace_pdf_detalle.short_description = 'Enlace público'

    def valor_comercial_formateado(self, obj):
        """Muestra el valor comercial formateado."""
        try:
            return f"US$ {float(obj.valor_comercial):,.2f}"
        except (ValueError, TypeError):
            return obj.valor_comercial
    valor_comercial_formateado.short_description = 'Valor comercial'
