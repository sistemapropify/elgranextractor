"""
URLs para la app de matching.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'matching'

router = DefaultRouter()
router.register(r'resultados', views.MatchResultViewSet, basename='matchresult')

# URLs para la API de matching
urlpatterns = [
    # API REST
    path('api/matching/<int:pk>/ejecutar/', views.MatchingViewSet.as_view({'get': 'ejecutar'}), name='matching-ejecutar'),
    path('api/matching/<int:pk>/resumen/', views.MatchingViewSet.as_view({'get': 'resumen'}), name='matching-resumen'),
    path('api/matching/<int:pk>/guardar/', views.MatchingViewSet.as_view({'post': 'guardar'}), name='matching-guardar'),
    path('api/matching/historial/<int:requerimiento_id>/', views.MatchingViewSet.as_view({'get': 'historial'}), name='matching-historial'),
    
    # Incluir router para resultados
    path('api/matching/', include(router.urls)),
    
    # Dashboard visual
    path('dashboard/', views.MatchingDashboardView.as_view(), name='dashboard'),
    path('', views.MatchingDashboardView.as_view(), name='home'),
    
    # Matching masivo
    path('masivo/', views.MatchingMasivoView.as_view(), name='masivo'),
    path('ejecutar-masivo/', views.EjecutarMatchingMasivoView.as_view(), name='ejecutar_masivo'),
]