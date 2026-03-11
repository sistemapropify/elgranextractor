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
]