from django.urls import path
from . import views

app_name = 'requerimientos'

urlpatterns = [
    # Lista de requerimientos
    path('lista/', views.ListaRequerimientosView.as_view(), name='lista'),
    
    # Detalle de requerimiento
    path('detalle/<int:pk>/', views.DetalleRequerimientoView.as_view(), name='detalle'),
    
    # Subir Excel (redirige a ingestas)
    path('subir/', views.SubirExcelView.as_view(), name='subir'),
    
    # Dashboard de análisis temporal
    path('dashboard-analisis/', views.DashboardAnalisisTemporalView.as_view(), name='dashboard_analisis'),
    
    # API para datos del dashboard (AJAX)
    path('api/analisis-temporal/', views.ApiAnalisisTemporalView.as_view(), name='api_analisis_temporal'),
    
    # Exportaciones
    path('exportar-excel/', views.ExportarAnalisisExcelView.as_view(), name='exportar_excel'),
    path('exportar-pdf/', views.ExportarAnalisisPDFView.as_view(), name='exportar_pdf'),
]