from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .map_layers import map_layers_api

router = DefaultRouter()
router.register(r'zonas', views.ZonaValorViewSet, basename='zona')
router.register(r'valoraciones', views.PropiedadValoracionViewSet, basename='valoracion')
router.register(r'estadisticas', views.EstadisticaZonaViewSet, basename='estadistica')
router.register(r'historial-precios', views.HistorialPrecioZonaViewSet, basename='historial-precio')

urlpatterns = [
    path('', include(router.urls)),
    
    # Endpoints adicionales
    path('estimar-precio/', views.EstimacionPrecioAPIView.as_view(), name='estimar-precio'),
    path('zonas/<int:zona_id>/calcular-precio/', views.CalcularPrecioM2APIView.as_view(), name='calcular-precio-zona'),
    
    # Endpoints específicos de zonas
    path('zonas/punto-en-zona/', views.ZonaValorViewSet.as_view({'post': 'punto_en_zona'}), name='punto-en-zona'),
    
    # Vistas HTML
    path('mapa/', views.mapa_zonas_valor, name='mapa_zonas_valor'),
    path(
        'propiedades-propify-disponibles/',
        views.api_propify_available_properties,
        name='api_propify_available_properties',
    ),
    path(
        'propiedades-mapa-disponibles/',
        views.api_available_map_properties,
        name='api_available_map_properties',
    ),
    path('jerarquia/', views.configurar_jerarquia, name='configurar_jerarquia'),
    path('capas-raster/', views.api_capas_raster, name='api_capas_raster'),
    path('capas-mapa/', map_layers_api, name='api_capas_mapa'),
    path('zonificacion/leyenda/', views.api_zonificacion_leyenda, name='api_zonificacion_leyenda'),
    path(
        'zonificacion/clasificar/',
        views.api_clasificar_zonificacion,
        name='api_clasificar_zonificacion',
    ),
    path('zonificacion/', views.api_zonificaciones, name='api_zonificaciones'),
    path(
        'zonificacion/verificar/',
        views.api_verificar_zonificacion,
        name='api_verificar_zonificacion',
    ),
    path(
        'zonificacion/recalcular/',
        views.api_recalcular_zonificacion,
        name='api_recalcular_zonificacion',
    ),
    path('heatmap/', views.mapa_heatmap, name='mapa_heatmap'),
    path('heatmap-data/', views.api_heatmap_data, name='api_heatmap_data'),
]
