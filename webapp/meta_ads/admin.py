"""
Configuración del admin para la app meta_ads.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import MetaCampaign, MetaCampaignInsight


@admin.register(MetaCampaign)
class MetaCampaignAdmin(admin.ModelAdmin):
    """
    Admin para el modelo MetaCampaign.
    """
    list_display = [
        'name',
        'campaign_id',
        'status_badge',
        'objective',
        'daily_budget_formatted',
        'created_at_meta',
        'updated_at',
    ]
    
    list_filter = [
        'status',
        'objective',
        'created_at_meta',
    ]
    
    search_fields = [
        'name',
        'campaign_id',
        'objective',
    ]
    
    readonly_fields = [
        'campaign_id',
        'created_at',
        'updated_at',
    ]
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('campaign_id', 'name', 'status', 'objective')
        }),
        ('Presupuesto', {
            'fields': ('daily_budget',)
        }),
        ('Fechas', {
            'fields': ('created_at_meta', 'created_at', 'updated_at')
        }),
    )
    
    def status_badge(self, obj):
        """
        Muestra el estado como un badge con color.
        """
        colors = {
            'ACTIVE': 'success',
            'PAUSED': 'warning',
            'ARCHIVED': 'secondary',
            'DELETED': 'danger',
        }
        color = colors.get(obj.status, 'secondary')
        
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Estado'
    status_badge.admin_order_field = 'status'
    
    def daily_budget_formatted(self, obj):
        """
        Formatea el presupuesto diario.
        """
        if obj.daily_budget:
            return f'S/ {obj.daily_budget:,.2f}'
        return '—'
    daily_budget_formatted.short_description = 'Presupuesto Diario'
    daily_budget_formatted.admin_order_field = 'daily_budget'
    
    def has_add_permission(self, request):
        """
        No permitir agregar campañas manualmente desde el admin.
        Las campañas deben sincronizarse desde la API de Meta.
        """
        return False
    
    def has_delete_permission(self, request, obj=None):
        """
        No permitir eliminar campañas desde el admin.
        """
        return False


@admin.register(MetaCampaignInsight)
class MetaCampaignInsightAdmin(admin.ModelAdmin):
    """
    Admin para el modelo MetaCampaignInsight.
    """
    list_display = [
        'campaign_link',
        'date',
        'spend_formatted',
        'clicks',
        'impressions',
        'cpc_formatted',
        'ctr_percentage_display',
        'synced_at',
    ]
    
    list_filter = [
        'date',
        'campaign__status',
        'campaign',
    ]
    
    search_fields = [
        'campaign__name',
        'campaign__campaign_id',
    ]
    
    readonly_fields = [
        'campaign',
        'date',
        'impressions',
        'clicks',
        'spend',
        'reach',
        'cpc',
        'ctr',
        'frequency',
        'synced_at',
    ]
    
    ordering = ['-date', 'campaign']
    
    def campaign_link(self, obj):
        """
        Muestra un enlace a la campaña.
        """
        return format_html(
            '<a href="{}">{}</a>',
            f'../metacampaign/{obj.campaign.id}/change/',
            obj.campaign.name[:30] + ('...' if len(obj.campaign.name) > 30 else '')
        )
    campaign_link.short_description = 'Campaña'
    campaign_link.admin_order_field = 'campaign__name'
    
    def spend_formatted(self, obj):
        """
        Formatea el gasto.
        """
        return f'S/ {obj.spend:,.2f}'
    spend_formatted.short_description = 'Gasto'
    spend_formatted.admin_order_field = 'spend'
    
    def cpc_formatted(self, obj):
        """
        Formatea el CPC.
        """
        if obj.cpc:
            return f'S/ {obj.cpc:,.4f}'
        return '—'
    cpc_formatted.short_description = 'CPC'
    cpc_formatted.admin_order_field = 'cpc'
    
    def ctr_percentage_display(self, obj):
        """
        Muestra el CTR como porcentaje.
        """
        return obj.ctr_percentage
    ctr_percentage_display.short_description = 'CTR'
    ctr_percentage_display.admin_order_field = 'ctr'
    
    def has_add_permission(self, request):
        """
        No permitir agregar insights manualmente.
        Los insights deben sincronizarse desde la API de Meta.
        """
        return False
    
    def has_delete_permission(self, request, obj=None):
        """
        No permitir eliminar insights.
        """
        return False
    
    def get_queryset(self, request):
        """
        Optimizar las consultas para el admin.
        """
        return super().get_queryset(request).select_related('campaign')
