from django.urls import path

from . import views

app_name = 'external_agents'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('nuevo/', views.agent_create, name='agent_create'),
    path('configuracion/', views.configuration, name='configuration'),
    path(
        'configuracion/tipos/crear/',
        views.document_type_create,
        name='document_type_create',
    ),
    path(
        'configuracion/tipos/<int:pk>/editar/',
        views.document_type_update,
        name='document_type_update',
    ),
    path(
        'configuracion/tipos/<int:pk>/activar/',
        views.document_type_toggle,
        name='document_type_toggle',
    ),
    path('<int:pk>/', views.agent_detail, name='agent_detail'),
    path('<int:pk>/editar/', views.agent_edit, name='agent_edit'),
    path(
        '<int:pk>/adjuntos/',
        views.attachment_upload,
        name='attachment_upload',
    ),
    path(
        '<int:pk>/adjuntos/<int:attachment_pk>/descargar/',
        views.attachment_download,
        name='attachment_download',
    ),
    path(
        '<int:pk>/adjuntos/<int:attachment_pk>/eliminar/',
        views.attachment_delete,
        name='attachment_delete',
    ),
]
