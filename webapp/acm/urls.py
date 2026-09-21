from django.urls import path
from . import views

app_name = 'acm'

urlpatterns = [
    path('', views.acm_dashboard, name='acm_dashboard'),
    path('analisis/', views.acm_view, name='acm_analisis'),
    path('analisis-pruebas/', views.acm_pruebas_view, name='acm_analisis_pruebas'),
    path('buscar-comparables/', views.buscar_comparables, name='buscar_comparables'),
    path('pruebas/buscar-comparables/', views.buscar_comparables_pruebas, name='buscar_comparables_pruebas'),
    path('pruebas/generar-enlace/', views.endpoint_prueba_no_persistente, name='generar_enlace_pruebas'),
    path('pruebas/guardar-acm/', views.endpoint_prueba_no_persistente, name='guardar_acm_pruebas'),
    path('pruebas/analisis-espacial/png/', views.analisis_espacial_png, name='analisis_espacial_pruebas'),
    path('generar-enlace/', views.generar_enlace_acm, name='generar_enlace_acm'),
    path('guardar-acm/', views.guardar_acm, name='guardar_acm'),
    path('historial/', views.historial_acm, name='historial_acm'),
    path('ver-pdf/<uuid:uuid>/', views.ver_pdf_acm, name='ver_pdf_acm'),
    path('analisis-espacial/png/', views.analisis_espacial_png, name='analisis_espacial_png'),
    path('analisis-espacial/test/', views.analisis_espacial_test, name='analisis_espacial_test'),
]
