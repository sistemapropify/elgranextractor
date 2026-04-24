from django.urls import path, re_path
from django.views.decorators.csrf import csrf_exempt
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
    path('chat-web/api/', csrf_exempt(views.chat_web_api), name='chat_web_api'),
    path('chat-web/stream/', csrf_exempt(views.chat_web_stream), name='chat_web_stream'),
    path('chat-web/upload/', csrf_exempt(views.chat_web_upload), name='chat_web_upload'),
    # Episodic Memory API (SPEC-008 - Fase 4.4)
    path('episodic-memory/', views.episodic_memory_list, name='episodic_memory_list'),
    path('episodic-memory/stats/', views.episodic_memory_stats, name='episodic_memory_stats'),
    path('episodic-memory/<uuid:episode_id>/', views.episodic_memory_detail, name='episodic_memory_detail'),
    path('episodic-memory/<uuid:episode_id>/feedback/', views.episodic_memory_feedback, name='episodic_memory_feedback'),

    # Autenticación (SPEC-009)
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # CRUD de usuarios (SPEC-009 - Fase 7)
    path('users/', views.user_list, name='user_list'),
    path('users/create/', views.user_create, name='user_create'),
    path('users/<uuid:user_id>/edit/', views.user_edit, name='user_edit'),
    path('users/<uuid:user_id>/toggle-active/', views.user_toggle_active, name='user_toggle_active'),
]