from django.urls import path
from . import views

app_name = 'market_analysis'

urlpatterns = [
    # Módulo A: Heatmap
    path('heatmap/', views.heatmap_view, name='heatmap'),
    path('heatmap-simple/', views.heatmap_simple_view, name='heatmap_simple'),
    path('heatmap-test/', views.heatmap_test_view, name='heatmap_test'),
    path('api/heatmap-data/', views.api_heatmap_data, name='api_heatmap_data'),
    path('api/heatmap-stats/', views.api_heatmap_stats, name='api_heatmap_stats'),
    
    # Módulo B: Dashboard
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('api/dashboard-stats/', views.api_dashboard_stats, name='api_dashboard_stats'),
]