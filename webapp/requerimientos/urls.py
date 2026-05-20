from django.urls import path
from . import views

app_name = 'requerimientos'

urlpatterns = [
    # Lista de requerimientos
    path('lista/', views.ListaRequerimientosView.as_view(), name='lista'),
    path('toggle-verificado/', views.ToggleVerificadoView.as_view(), name='toggle_verificado'),
    
    # Editar requerimiento (AJAX)
    path('editar/', views.EditarRequerimientoView.as_view(), name='editar'),
    
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

    # API: Búsqueda y creación rápida de agentes
    path('api/buscar-agente/', views.BuscarAgentePorTelefonoView.as_view(), name='buscar_agente'),
    path('api/buscar-agente-por-nombre/', views.BuscarAgentePorNombreView.as_view(), name='buscar_agente_por_nombre'),
    path('api/crear-agente-rapido/', views.CrearAgenteRapidoView.as_view(), name='crear_agente_rapido'),

    # API: Autocomplete de ZonaCalle (zonas y calles)
    path('api/zonas-calles/autocomplete/', views.ApiZonaCalleAutocompleteView.as_view(), name='api_zonas_calles_autocomplete'),

    # Quality Score - Configuración
    path('config-calidad/', views.ConfiguracionCalidadView.as_view(), name='config_calidad'),
    path('api/config-calidad/', views.ApiConfiguracionCalidadView.as_view(), name='api_config_calidad'),
    path('api/estadisticas-calidad/', views.ApiEstadisticasCalidadView.as_view(), name='api_estadisticas_calidad'),
    path('api/recalcular-quality/', views.ApiRecalcularQualityView.as_view(), name='api_recalcular_quality'),
    path('api/clonar/', views.ClonarRequerimientoView.as_view(), name='api_clonar'),

    # API: Guardar filtros en sesión (para evitar URL explosion)
    path('api/guardar-filtros-sesion/', views.ApiGuardarFiltrosSesionView.as_view(), name='api_guardar_filtros_sesion'),
]