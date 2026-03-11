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
]