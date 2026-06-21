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
    path('api/matching/<int:pk>/guardados/', views.MatchingViewSet.as_view({'get': 'guardados'}), name='matching-guardados'),
    path('api/matching/<int:pk>/guardar/', views.MatchingViewSet.as_view({'post': 'guardar'}), name='matching-guardar'),
    path('api/matching/<int:pk>/pipeline/', views.MatchingViewSet.as_view({'get': 'pipeline'}), name='matching-pipeline'),
    path('api/matching/<int:pk>/pipeline-ramas/', views.MatchingViewSet.as_view({'get': 'pipeline_ramas'}), name='matching-pipeline-ramas'),
    path('api/matching/<int:pk>/pipeline-matches/', views.MatchingViewSet.as_view({'get': 'pipeline_matches'}), name='matching-pipeline-matches'),
    path('api/matching/historial/<int:requerimiento_id>/', views.MatchingViewSet.as_view({'get': 'historial'}), name='matching-historial'),
    
    # Incluir router para resultados
    path('api/matching/', include(router.urls)),
    
    # API de propuestas WhatsApp
    path('api/propuesta/guardar/', views.PropuestaWhatsAppViewSet.as_view({'post': 'guardar'}), name='propuesta-guardar'),
    path('api/propuesta/<int:pk>/actualizar-status/', views.PropuestaWhatsAppViewSet.as_view({'post': 'actualizar_status'}), name='propuesta-actualizar-status'),
    path('api/propuesta/<int:pk>/actualizar-mensaje/', views.PropuestaWhatsAppViewSet.as_view({'post': 'actualizar_mensaje'}), name='propuesta-actualizar-mensaje'),
    path('api/propuesta/<int:pk>/pipeline/', views.PropuestaWhatsAppViewSet.as_view({'get': 'pipeline'}), name='propuesta-pipeline'),
    path('api/propuesta/verificar-enviado/', views.PropuestaWhatsAppViewSet.as_view({'get': 'verificar_enviado'}), name='propuesta-verificar-enviado'),
    path('api/propuesta/listar/', views.PropuestaWhatsAppViewSet.as_view({'get': 'listar'}), name='propuesta-listar'),
    path('api/propuesta/', include(router.urls)),

    # Dashboard visual
    path('dashboard/', views.MatchingDashboardView.as_view(), name='dashboard'),
    path('', views.MatchingDashboardView.as_view(), name='home'),
    
    # Matching masivo
    path('masivo/', views.MatchingMasivoView.as_view(), name='masivo'),
    path('ejecutar-masivo/', views.EjecutarMatchingMasivoView.as_view(), name='ejecutar_masivo'),
    
    # Vista calendario
    path('calendar/', views.MatchingCalendarView.as_view(), name='calendar'),

    # Tracking de respuestas WhatsApp
    path('propuesta/<int:pk>/responder/', views.responder_propuesta, name='propuesta-responder'),
    path('propuesta/respuesta/', views.pagina_respuesta, name='propuesta-respuesta'),

    # Dashboard de propuestas
    path('propuestas/dashboard/', views.PropuestasDashboardView.as_view(), name='propuestas-dashboard'),

    # Matches de Propify (CRM)
    path('matches/', views.MatchesDashboardView.as_view(), name='matches-dashboard'),

    # Matches por Propiedad (Property-Centric CRM)
    path('matches-por-propiedad/', views.PropiedadesMatchesDashboardView.as_view(), name='matches-por-propiedad'),
    path('api/matching/<int:pk>/pipeline-requerimientos/',
         views.MatchingViewSet.as_view({'get': 'pipeline_requerimientos'}),
         name='matching-pipeline-requerimientos'),
]
