from django.urls import path
from . import views

app_name = 'propifai'

urlpatterns = [
    # Vista para mostrar solo propiedades Propify
    path('propiedades/', views.ListaPropiedadesPropifyView.as_view(), name='lista_propiedades_propify'),
    
    # Vista simple alternativa
    path('propiedades-simple/', views.lista_propiedades_propify_simple, name='lista_propiedades_propify_simple'),
    
    # Vista simple HTML
    path('propiedades-simple-html/', views.vista_propiedades_simple_html, name='vista_propiedades_simple_html'),
    
    # API JSON
    path('api/propiedades-json/', views.api_propiedades_json, name='api_propiedades_json'),
    
    # Dashboard de calidad de cartera
    path('dashboard/calidad/', views.dashboard_calidad_cartera, name='dashboard_calidad_cartera'),
    
    # Dashboard de visitas y actividad por propiedad
    path('dashboard/visitas/', views.property_visits_dashboard, name='property_visits_dashboard'),
    
    # API de eventos por propiedad
    path('api/property/<int:property_id>/events/', views.property_events_api, name='property_events_api'),
    
    # API de línea de tiempo por propiedad (para el drawer)
    path('api/property/<int:property_id>/timeline/', views.property_timeline_api, name='property_timeline_api'),
]