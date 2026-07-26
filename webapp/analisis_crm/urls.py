from django.urls import path
from . import views
from lead_intelligence import views as intelligence_views

app_name = 'analisis_crm'

urlpatterns = [
    # La entrada histórica "Leads CRM" ahora sirve el dashboard gerencial de
    # Prometeo. Las vistas de detalle antiguas se conservan temporalmente.
    path('', intelligence_views.management_dashboard, name='dashboard'),
    path('cohortes/', intelligence_views.cohorts_dashboard, name='cohorts'),
    path('api/management/summary/', intelligence_views.management_summary_api, name='management_summary_api'),
    path('leads/', views.lead_list, name='lead_list'),
    path('leads/<int:pk>/', views.lead_detail, name='lead_detail'),
    path('analytics/', views.analytics, name='analytics'),
]
