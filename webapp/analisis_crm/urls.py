from django.urls import path
from . import views
from lead_intelligence import views as intelligence_views

app_name = 'analisis_crm'

urlpatterns = [
    # La entrada histórica "Leads CRM" ahora sirve el dashboard gerencial de
    # Prometeo. Las vistas de detalle antiguas se conservan temporalmente.
    path('', intelligence_views.management_dashboard, name='dashboard'),
    path('cohortes/', intelligence_views.cohorts_dashboard, name='cohorts'),
    path(
        'calidad-atencion/',
        intelligence_views.attention_quality_dashboard,
        name='attention_quality',
    ),
    path(
        'calidad-motor/',
        intelligence_views.analysis_quality_dashboard,
        name='analysis_quality',
    ),
    path(
        'propiedades/',
        intelligence_views.property_performance_dashboard,
        name='property_performance',
    ),
    path(
        'calidad-motor/revisar/',
        intelligence_views.conversation_review,
        name='conversation_review',
    ),
    path(
        'calidad-motor/ejecutar/',
        intelligence_views.run_analysis,
        name='run_analysis',
    ),
    path(
        'calidad-motor/detener/',
        intelligence_views.cancel_analysis,
        name='cancel_analysis',
    ),
    path('resultados/', intelligence_views.lead_results, name='lead_results'),
    path('resultados/<int:lead_id>/', intelligence_views.lead_conversation, name='lead_conversation'),
    path('api/management/summary/', intelligence_views.management_summary_api, name='management_summary_api'),
    path('leads/', views.lead_list, name='lead_list'),
    path('leads/<int:pk>/', views.lead_detail, name='lead_detail'),
    path('analytics/', views.analytics, name='analytics'),
]
