"""
URLs para la API REST del sistema de monitoreo web.

Este módulo define las rutas de la API para interactuar con
el sistema de monitoreo web de bienes raíces en Arequipa.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from . import views
from . import views_mejoradas

# Configurar router para ViewSets
router = DefaultRouter()
router.register(r'fuentes', views.FuenteWebViewSet, basename='fuente')
router.register(r'capturas', views.CapturaCrudaViewSet, basename='captura')
router.register(r'eventos', views.EventoDeteccionViewSet, basename='evento')
router.register(r'propiedades-raw', views.PropiedadRawViewSet, basename='propiedadraw')
router.register(r'propiedades-propifai', views.PropifaiPropertyViewSet, basename='propifaiproperty')

# URLs de la API
urlpatterns = [
    # Autenticación JWT
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Endpoints principales (ViewSets)
    path('', include(router.urls)),
    
    # Endpoints adicionales
    path('sistema/', views.SistemaAPIView.as_view(), name='sistema'),
    path('descubrimiento/', views.DescubrimientoAPIView.as_view(), name='descubrimiento'),
    path('estadisticas/', views.EstadisticasAPIView.as_view(), name='estadisticas'),
    path('tareas/', views.TareasAPIView.as_view(), name='tareas'),
    path('tareas/<str:task_id>/', views.TareasAPIView.as_view(), name='tarea_detalle'),
    
    # Endpoints mejorados para captura
    path('captura-mejorada/', views_mejoradas.CapturaMejoradaAPIView.as_view(), name='captura-mejorada'),
    path('reprocesamiento/', views_mejoradas.ReprocesamientoAPIView.as_view(), name='reprocesamiento'),
    path('calidad-capturas/', views_mejoradas.CalidadCapturasAPIView.as_view(), name='calidad-capturas'),
    path('comparacion-capturas/<int:fuente_id>/', views_mejoradas.ComparacionCapturasAPIView.as_view(), name='comparacion-capturas'),
    path('captura-manual-mejorada/', views_mejoradas.CapturaManualMejoradaAPIView.as_view(), name='captura-manual-mejorada'),
    
    # Documentación de la API (solo en desarrollo)
    # path('docs/', include_docs_urls(title='API del Gran Extractor')),
    
    # Endpoint simulado para propiedades externas (para pruebas)
    path('propiedades-externas-simuladas/', views.PropiedadesExternasSimuladasAPIView.as_view(), name='propiedades-externas-simuladas'),
    
    # Endpoint para buscar comparables
    path('comparables/', views.ComparablesAPIView.as_view(), name='comparables'),
]

# Agregar prefijo de versión (comentado porque ya hay prefijo en webapp/urls.py)
# urlpatterns = [path('api/v1/', include(urlpatterns))]