from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

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
    path('jerarquia/', views.configurar_jerarquia, name='configurar_jerarquia'),
    path('heatmap/', views.mapa_heatmap, name='mapa_heatmap'),
    path('heatmap-data/', views.api_heatmap_data, name='api_heatmap_data'),
]