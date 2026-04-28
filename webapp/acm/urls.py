from django.urls import path
from . import views

app_name = 'acm'

urlpatterns = [
    path('', views.acm_dashboard, name='acm_dashboard'),
    path('analisis/', views.acm_view, name='acm_analisis'),
    path('buscar-comparables/', views.buscar_comparables, name='buscar_comparables'),
    path('generar-enlace/', views.generar_enlace_acm, name='generar_enlace_acm'),
    path('ver-pdf/<uuid:uuid>/', views.ver_pdf_acm, name='ver_pdf_acm'),
]