from django.urls import path
from . import views

app_name = 'canvas'

urlpatterns = [
    # Vistas principales
    path('',                          views.lienzo_list,       name='list'),
    path('nuevo/',                    views.lienzo_nuevo,      name='nuevo'),
    path('<int:pk>/',                 views.lienzo_editor,     name='editor'),

    # API JSON (llamadas desde JS)
    path('api/lienzo/<int:pk>/save/', views.api_lienzo_save,   name='api_save'),
    path('api/lienzo/<int:pk>/load/', views.api_lienzo_load,   name='api_load'),
    path('api/propiedades/',          views.api_propiedades,   name='api_props'),
    path('api/agentes/',              views.api_agentes,       name='api_agentes'),
    path('api/reqs/<int:prop_id>/',   views.api_reqs_match,    name='api_reqs'),
    path('api/match-detail/<int:match_id>/', views.api_match_detail, name='api_match_detail'),
    path('api/template/save/',        views.api_template_save, name='api_tpl_save'),
    path('api/template/list/',        views.api_template_list, name='api_tpl_list'),

    # API archivos y enlaces
    path('api/upload/',               views.api_upload,        name='api_upload'),
    path('api/link/',                 views.api_link,          name='api_link'),
    path('api/archivos/<int:lienzo_pk>/', views.api_archivos_list, name='api_archivos'),
    path('api/media/<int:archivo_id>/',   views.api_lienzo_media,  name='api_media'),
    path('api/eliminar/<int:pk>/',        views.api_lienzo_eliminar, name='api_eliminar'),
    path('api/propiedad-imagenes/<int:prop_id>/', views.api_propiedad_imagenes, name='api_prop_imagenes'),
    path('api/lead-analysis/<int:prop_id>/',      views.api_lead_analysis,      name='api_lead_analysis'),
    path('api/lead-analysis/<int:prop_id>/leads/', views.api_lead_analysis_leads, name='api_lead_analysis_leads'),
    path('api/lead-analysis-global/',               views.api_lead_analysis_global, name='api_lead_analysis_global'),
    path('api/leads-by-date/',                      views.api_leads_by_date,        name='api_leads_by_date'),
    path('api/lead-matrix/',                        views.api_lead_matrix,          name='api_lead_matrix'),
]
