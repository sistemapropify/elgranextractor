from django.urls import path, re_path
from . import views
import uuid

app_name = 'intelligence'

urlpatterns = [
    path('chat/', views.chat_endpoint, name='chat'),
    path('health/', views.health_check, name='health_check'),
    # Endpoints RAG (SPEC-003)
    path('rag/test/', views.rag_test_endpoint, name='rag_test'),
    path('rag/status/', views.rag_system_status, name='rag_status'),
    
    # API endpoints para descubrimiento de tablas y esquemas
    path('rag/tables/', views.rag_discovery_tables, name='rag_discovery_tables'),
    path('rag/tables/<str:table_name>/schema/', views.rag_discovery_table_schema, name='rag_discovery_table_schema'),
    path('rag/tables/<str:table_name>/preview/', views.rag_discovery_table_preview, name='rag_discovery_table_preview'),
    path('rag/collections/', views.rag_create_collection_dynamic, name='rag_create_collection_dynamic'),
    path('rag/search/', views.rag_search_dynamic, name='rag_search_dynamic'),
    
    # Vistas para gestión de roles (SPEC-005 - 5.2)
    path('roles/', views.role_list, name='role_list'),
    path('roles/create/', views.role_create, name='role_create'),
    path('roles/<uuid:role_id>/edit/', views.role_edit, name='role_edit'),
    path('roles/<uuid:role_id>/delete/', views.role_delete, name='role_delete'),
    
    # Vistas para gestión de colecciones RAG (SPEC-005 - 5.3)
    path('collections/', views.collection_list, name='collection_list'),
    path('collections/create/', views.collection_create, name='collection_create'),
    path('collections/<uuid:collection_id>/edit/', views.collection_edit, name='collection_edit'),
    path('collections/<uuid:collection_id>/delete/', views.collection_delete, name='collection_delete'),
    path('collections/<uuid:collection_id>/sync/', views.collection_sync, name='collection_sync'),
    path('collections/<uuid:collection_id>/stats/', views.collection_stats, name='collection_stats'),
    
    # Simulador de usuario (SPEC-005 - 5.4)
    path('simulator/', views.user_simulator, name='user_simulator'),
    
    # Dashboard y vistas adicionales (SPEC-005 - 5.5)
    path('dashboard/', views.dashboard, name='dashboard'),
    path('stats/', views.system_stats, name='system_stats'),
    path('logs/', views.activity_logs, name='activity_logs'),
    
    # Chat Web Interactivo (SPEC-007)
    path('chat-web/', views.chat_web, name='chat_web'),
    path('chat-web/api/', views.chat_web_api, name='chat_web_api'),
    path('chat-web/stream/', views.chat_web_stream, name='chat_web_stream'),
    path('chat-web/upload/', views.chat_web_upload, name='chat_web_upload'),
]