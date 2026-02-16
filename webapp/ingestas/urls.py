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
]