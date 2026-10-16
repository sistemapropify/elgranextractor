from django.urls import path
from . import views
from . import portal_views
from . import cadastral_views
from .access import legacy_admin
from . import outlier_views
from .components_routes import urlpatterns as component_routes

app_name = 'acm'

from ingestas.ml_candidate_views import dashboard as ml_control
from ingestas import ml_model_views

urlpatterns = [
    path('catastro/configuracion/', cadastral_views.configuration, name='cadastral_config'),
    path('catastro/lotes/<str:lot_id>/', cadastral_views.lot, name='cadastral_lot'),
    path('catastro/lotes/<str:lot_id>/fachada/', cadastral_views.facade, name='cadastral_facade'),
    path('login/', portal_views.login, name='login'),
    path('logout/', portal_views.logout, name='logout'),
    path('vista-por-rol/', portal_views.perspective, name='perspective'),
    path('configuracion/', portal_views.role_settings, name='role_settings'),
    path('configuracion/roles/<int:role_id>/', portal_views.role_policy, name='role_policy'),
    path('historial/<uuid:uuid>/eliminar/', portal_views.delete_analysis, name='delete_analysis'),
    path('pdm/', portal_views.pdm_query, name='pdm_query'),
    path('capas-mapa/', portal_views.map_layers, name='map_layers'),
    path('fotos/revisar/', portal_views.review_photo, name='review_photo'),
    path('fotos/<str:ticket>/', portal_views.photo, name='photo'),
    path('control/', legacy_admin(ml_control), name='control_datos'),
    path('modelos/', legacy_admin(ml_model_views.dashboard), name='modelos_dashboard'),
    path('modelos/entrenar/', legacy_admin(ml_model_views.queue_training), name='modelos_entrenar'),
    path('modelos/reevaluar/', legacy_admin(ml_model_views.request_reconciliation), name='modelos_reevaluar'),
    path('modelos/<int:pk>/publicar/', legacy_admin(ml_model_views.publish_run), name='modelos_publicar'),
    path('modelos/estimar/', portal_views.model_estimate, name='modelo_estimacion'),
    path('', portal_views.dashboard, name='acm_dashboard'),
    path('analisis-clasico/', legacy_admin(views.acm_view), name='acm_analisis_clasico'),
    path('analisis-pruebas-clasico/', legacy_admin(views.acm_pruebas_view), name='acm_analisis_pruebas_clasico'),
    path('buscar-comparables/', legacy_admin(views.buscar_comparables), name='buscar_comparables'),
    path('pruebas/buscar-comparables/', legacy_admin(views.buscar_comparables_pruebas), name='buscar_comparables_pruebas'),
    path('pruebas/generar-enlace/', legacy_admin(views.endpoint_prueba_no_persistente), name='generar_enlace_pruebas'),
    path('pruebas/guardar-acm/', legacy_admin(views.endpoint_prueba_no_persistente), name='guardar_acm_pruebas'),
    path('pruebas/analisis-espacial/png/', legacy_admin(views.analisis_espacial_png), name='analisis_espacial_pruebas'),
    path('generar-enlace/', legacy_admin(views.generar_enlace_acm), name='generar_enlace_acm'),
    path('guardar-acm/', legacy_admin(views.guardar_acm), name='guardar_acm'),
    path('historial/', portal_views.history, name='historial_acm'),
    path('ver-pdf/<uuid:uuid>/', views.ver_pdf_acm, name='ver_pdf_acm'),
    path('analisis-espacial/png/', legacy_admin(views.analisis_espacial_png), name='analisis_espacial_png'),
    path('analisis-espacial/test/', legacy_admin(views.analisis_espacial_test), name='analisis_espacial_test'),
    path('atipicos-3d/', outlier_views.outliers_3d, name='atipicos_3d'),
] + component_routes
