from django.urls import path
from . import views

print("[DEBUG] market_analysis/urls.py cargado")

app_name = 'market_analysis'

urlpatterns = [
    # Dashboard principal
    path('dashboard/', views.dashboard_view, name='dashboard'),
    # Heatmap principal
    path('heatmap/', views.heatmap_view, name='heatmap'),
    path('api/heatmap-data/', views.api_heatmap_data, name='api_heatmap_data'),
    # API para estadísticas del dashboard
    path('api/dashboard-stats/', views.api_dashboard_stats, name='api_dashboard_stats'),
    # Dashboard avanzado de calidad de datos
    path('data-quality/', views.data_quality_dashboard, name='data_quality_dashboard'),
    path('api/data-quality-metrics/', views.api_data_quality_metrics, name='api_data_quality_metrics'),
    # Lista de propiedades (nueva pestaña)
    path('property-list/', views.property_list_dashboard, name='property_list_dashboard'),
    # API para actualizar propiedades desde el dashboard
    path('api/update-property-field/', views.api_update_property_field, name='api_update_property_field'),
    # Vista alternativa de detalle de propiedad (para evitar error ModuleNotFoundError)
    path('property-quick-detail/<int:property_id>/', views.property_quick_detail, name='property_quick_detail'),
]