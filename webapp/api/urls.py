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

# Configurar router para ViewSets
router = DefaultRouter()
router.register(r'fuentes', views.FuenteWebViewSet, basename='fuente')
router.register(r'capturas', views.CapturaCrudaViewSet, basename='captura')
router.register(r'eventos', views.EventoDeteccionViewSet, basename='evento')

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
    
    # Documentación de la API (solo en desarrollo)
    # path('docs/', include_docs_urls(title='API del Gran Extractor')),
]

# Agregar prefijo de versión
urlpatterns = [path('api/v1/', include(urlpatterns))]