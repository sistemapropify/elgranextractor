from django.urls import path
from . import views

app_name = 'ingestas'

urlpatterns = [
    path('', views.IngestasIndexView.as_view(), name='index'),
    path('subir/', views.SubirExcelView.as_view(), name='subir_excel'),
    path('validar/', views.ValidarMapeoView.as_view(), name='validar_mapeo'),
    path('resultado/', views.ResultadoView.as_view(), name='resultado_ingesta'),
    path('limpiar-sesion/', views.LimpiarSesionView.as_view(), name='limpiar_sesion'),
    path('limpiar-logs/', views.LimpiarLogsView.as_view(), name='limpiar_logs'),
    # Nueva ruta para listar propiedades
    path('propiedades/', views.ListaPropiedadesView.as_view(), name='lista_propiedades'),
    path('propiedades/completa/', views.ListaPropiedadesCompletaView.as_view(), name='lista_propiedades_completa'),
    path('propiedades/filtradas/', views.PropiedadesFiltradasView.as_view(), name='propiedades_filtradas'),
    path('propiedades/<int:pk>/', views.DetallePropiedadView.as_view(), name='detalle_propiedad'),
    path('propiedades/<int:pk>/editar/', views.EditarPropiedadView.as_view(), name='editar_propiedad'),
    # Nuevas rutas para procesamiento con IA
    path('procesar-ia/', views.ProcesarConIAView.as_view(), name='procesar_ia'),
    path('resultado-ia/', views.ResultadoIAView.as_view(), name='resultado_ia'),
    
    # Vista temporal para propiedades Propify
    path('propiedades-propify/', views.vista_propiedades_propify, name='propiedades_propify'),
    # Vista directa para propiedades Propify (HTML generado directamente)
    path('propiedades-propify-directa/', views.vista_propiedades_propify_directa, name='propiedades_propify_directa'),
    # API para crear propiedad desde formulario modal
    path('api/crear-propiedad/', views.CrearPropiedadAPIView.as_view(), name='crear_propiedad_api'),

    # ── Scraping Dashboard ──
    path('scraping/dashboard/', views.ScrapingDashboardView.as_view(), name='scraping_dashboard'),
    path('scraping/control/', views.ScrapingControlView.as_view(), name='scraping_control'),
    path('scraping/stream/<int:job_id>/', views.ScrapingStreamView.as_view(), name='scraping_stream'),
    path('scraping/status/<int:job_id>/', views.ScrapingStatusView.as_view(), name='scraping_status'),
    path('scraping/propiedades/', views.ScrapingPropiedadesView.as_view(), name='scraping_propiedades'),
    path('scraping/historial/', views.ScrapingHistorialView.as_view(), name='scraping_historial'),
    path('scraping/test-import/', views.test_camoufox_import, name='test_import'),
]