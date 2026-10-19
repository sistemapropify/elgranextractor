from django.urls import path
from . import views
from . import worker_api
from . import planos_views

app_name = 'catastro'
urlpatterns = [
    path('', views.dashboard, name='dashboard'),
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
