from django.urls import path
from . import views

app_name = 'acm'

urlpatterns = [
    path('', views.acm_dashboard, name='acm_dashboard'),
    path('analisis/', views.acm_view, name='acm_analisis'),
    path('buscar-comparables/', views.buscar_comparables, name='buscar_comparables'),
]