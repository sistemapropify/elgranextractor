from django.urls import path
from . import views
from . import worker_api
from . import planos_views
from . import master_views
from . import registry_views
from . import source_manager_views

app_name = 'catastro'
urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('registros/', registry_views.table, name='registry'),
    path('registros/exportar/', registry_views.export, name='registry_export'),
    path('registros/archivo/<str:lot_id>/<str:filename>/', registry_views.asset, name='registry_asset'),
    path('api/registros/', registry_views.records, name='registry_records'),
    path('api/registros/actualizar/', registry_views.synchronize, name='registry_synchronize'),
    path('maestro/', master_views.viewer, name='maestro'),
    path('maestro/fuentes/', source_manager_views.viewer, name='master_sources'),
    path('maestro/planos/', source_manager_views.plans_dashboard, name='plans_dashboard'),
    path('api/maestro/composicion/', source_manager_views.workspace, name='master_composition'),
    path('api/planos/inventario/', planos_views.inventory, name='planos_inventory'),
    path('api/datos/geollaqta/', planos_views.geollaqta_inventory, name='geollaqta_data_inventory'),
    path('api/maestro/planos/', source_manager_views.plans_portfolio, name='plans_portfolio'),
    path('api/maestro/pdf/', source_manager_views.register_pdf, name='master_pdf'),
    path('api/maestro/pdf/<str:version_id>/vectorizar/', source_manager_views.vectorize_pdf, name='master_pdf_vectorize'),
    path('api/maestro/pdf/<str:version_id>/pagina/', source_manager_views.pdf_page, name='master_pdf_page'),
    path('api/maestro/pdf/<str:version_id>/original/', source_manager_views.original_pdf, name='master_pdf_original'),
    path('api/maestro/planes/<str:version_id>/miniatura/', planos_views.source_thumbnail, name='master_source_thumbnail'),
    path('api/maestro/pdf/<str:version_id>/vectores/<str:filename>', source_manager_views.vector_asset, name='master_pdf_vector'),
    path('api/maestro/medios/<str:media_id>/', source_manager_views.medium, name='master_medium'),
    path('api/maestro/catalogo/', master_views.catalogue, name='maestro_catalogue'),
    path('api/maestro/fuentes/<slug:source_id>/posicion/', master_views.placement, name='maestro_placement'),
    path('api/maestro/fuentes/<slug:source_id>/<slug:layer_key>/', master_views.layer, name='maestro_layer'),
    path('visor-planos/', planos_views.viewer, name='visor_planos'),
    path('api/planos/importar/', planos_views.upload, name='planos_upload'),
    path('api/planos/<str:job_id>/', planos_views.import_status, name='planos_status'),
    path('api/planos/<str:job_id>/capa/', planos_views.layer_features, name='planos_layer'),
    path('api/planos/<str:job_id>/ajustes/', planos_views.adjustments, name='planos_adjustments'),
    path('api/status/', views.status, name='status'),
    path('api/start/', views.start, name='start'),
    path('api/worker/claim/', worker_api.claim, name='worker_claim'),
    path('api/worker/<slug:job_id>/<slug:action>/', worker_api.job_action, name='worker_job'),
    path('api/jobs/<slug:job_id>/stop/', views.stop, name='stop'),
    path('lotes/<str:lot_id>/', views.lot, name='lot'),
    path('archivos/<str:lot_id>/<str:filename>/', views.asset, name='asset'),
    path('paginas/<str:lot_id>/<str:filename>/<int:page_number>/', views.document_page, name='document_page'),
]
