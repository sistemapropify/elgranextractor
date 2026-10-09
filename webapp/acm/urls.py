from django.urls import path
from . import views
from . import outlier_views
from .components_routes import urlpatterns as component_routes

app_name = 'acm'

from ingestas.ml_candidate_views import dashboard as ml_control
from ingestas import ml_model_views

urlpatterns = [
    path('control/', ml_control, name='control_datos'),
    path('modelos/', ml_model_views.dashboard, name='modelos_dashboard'),
    path('modelos/entrenar/', ml_model_views.queue_training, name='modelos_entrenar'),
    path('modelos/reevaluar/', ml_model_views.request_reconciliation, name='modelos_reevaluar'),
    path('modelos/<int:pk>/publicar/', ml_model_views.publish_run, name='modelos_publicar'),
    path('modelos/estimar/', ml_model_views.estimate, name='modelo_estimacion'),
    path('', views.acm_dashboard, name='acm_dashboard'),
    path('analisis-clasico/', views.acm_view, name='acm_analisis_clasico'),
    path('analisis-pruebas-clasico/', views.acm_pruebas_view, name='acm_analisis_pruebas_clasico'),
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
    path('atipicos-3d/', outlier_views.outliers_3d, name='atipicos_3d'),
] + component_routes
