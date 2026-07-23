from django.urls import path, re_path
from django.views.decorators.csrf import csrf_exempt
from . import views
from . import learning_views
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
    path('rag/tables/<str:table_name>/foreign-keys/', views.rag_discovery_foreign_keys, name='rag_discovery_foreign_keys'),
    path('rag/tables/<str:table_name>/preview/', views.rag_discovery_table_preview, name='rag_discovery_table_preview'),
    path('rag/collections/', views.rag_create_collection_dynamic, name='rag_create_collection_dynamic'),
    path('rag/search/', views.rag_search_dynamic, name='rag_search_dynamic'),
    path('rag/collections/<str:collection_name>/ingest-pdf/', views.rag_ingest_pdf, name='rag_ingest_pdf'),
    path('pdf-upload/', views.pdf_upload_view, name='pdf_upload'),
    
    # Vistas para gestión de roles (SPEC-005 - 5.2)
    path('roles/', views.role_list, name='role_list'),
    path('roles/create/', views.role_create, name='role_create'),
    path('roles/<uuid:role_id>/edit/', views.role_edit, name='role_edit'),
    path('roles/<uuid:role_id>/delete/', views.role_delete, name='role_delete'),
    
    # Vistas para gestión de colecciones RAG (SPEC-005 - 5.3)
    path('collections/', views.collection_list, name='collections_dashboard'),
    path('collections/create/', views.collection_create, name='collection_create'),
    path('collections/<uuid:collection_id>/edit/', views.collection_edit, name='collection_edit'),
    path('collections/<uuid:collection_id>/delete/', views.collection_delete, name='collection_delete'),
    path('collections/<uuid:collection_id>/sync/', views.collection_sync, name='collection_sync'),
    path('collections/<uuid:collection_id>/sync/api/', views.collection_sync_api, name='collection_sync_api'),
    path('collections/sync-all/', views.collection_sync_all, name='collection_sync_all'),
    path('collections/sync-status/<str:task_id>/', views.collection_sync_status, name='collection_sync_status'),
    path('collections/sync-revoke/<str:task_id>/', views.collection_sync_revoke, name='collection_sync_revoke'),
    path('collections/<uuid:collection_id>/stats/', views.collection_stats, name='collection_stats'),
    path('collections/<uuid:collection_id>/detail/', views.collection_detail, name='collection_detail'),
    
    # Simulador de usuario (SPEC-005 - 5.4)
    path('simulator/', views.user_simulator, name='user_simulator'),
    
    # Dashboard y vistas adicionales (SPEC-005 - 5.5)
    path('', views.intelligence_dashboard, name='intelligence_dashboard'),
    path('dashboard/', views.intelligence_dashboard, name='dashboard'),
    path('intent-evaluation/', views.intent_evaluation_dashboard, name='intent_evaluation'),
    path('config/', views.intelligence_config, name='intelligence_config'),
    path('errors/', views.intelligence_errors, name='intelligence_errors'),
    path('tests/', views.intelligence_tests, name='intelligence_tests'),
    path('evaluation/', views.pil_evaluation, name='pil_evaluation'),
    path('evaluation/api/', views.pil_evaluation_api, name='pil_evaluation_api'),
    path('stats/', views.system_stats, name='system_stats'),
    path('logs/', views.activity_logs, name='activity_logs'),

    # Aprendizaje operativo PIL (Nivel 1: observabilidad solamente)
    path('learning/', learning_views.learning_dashboard, name='learning_dashboard'),
    path('learning/traces/', learning_views.learning_traces, name='learning_traces'),
    path('learning/traces/<str:trace_id>/', learning_views.learning_trace_detail, name='learning_trace_detail'),
    
    # Chat Web Interactivo (SPEC-007)
    path('chat-web/', views.chat_web, name='chat_web'),
    path('chat-web/api/', csrf_exempt(views.chat_web_api), name='chat_web_api'),
    path('chat-web/stream/', csrf_exempt(views.chat_web_stream), name='chat_web_stream'),
    path('chat-web/upload/', csrf_exempt(views.chat_web_upload), name='chat_web_upload'),
    
    # Conversation Flows (Sistema de flujos conversacionales)
    path('chat-workflows/manage/', views.conversation_flows_page, name='conversation_flows_page'),
    path('chat-workflows/create/', views.conversation_flow_create, name='conversation_flow_create'),
    path('chat-workflows/<uuid:flow_id>/edit/', views.conversation_flow_edit, name='conversation_flow_edit'),
    path('chat-workflows/', views.conversation_flows_list, name='chat_workflows_list'),
    path('chat-workflows/<uuid:flow_id>/', views.conversation_flow_detail, name='conversation_flow_detail'),
    path('chat-workflows/<uuid:flow_id>/toggle/', views.conversation_flow_toggle, name='conversation_flow_toggle'),
    # Skills Dashboard (SPEC-011) — ANTES de skills/<str:skill_name>/ para evitar captura genérica
    path('skills/dashboard/', views.skills_dashboard_view, name='skills_dashboard'),
    path('skills/create/', views.skill_create_view, name='skill_create'),
    path('skills/metrics/global/', views.skill_metrics_view, name='skill_metrics_global'),
    path('skills/metrics/', views.skill_metrics, name='skill_metrics'),
    path('skills/logs/', views.skill_logs_view, name='skill_logs'),
    path('skills/api/logs/', views.skill_logs_api, name='skill_logs_api'),
    path('skills/api/stats/', views.skill_stats_api, name='skill_stats_api'),
    path('skills/', views.skills_list, name='skills_list'),
    path('skills/execute/', csrf_exempt(views.skill_execute), name='skill_execute'),
    re_path(r'^skills/execution/(?P<execution_id>[0-9a-f]{32}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}|[0-9a-f]{32})/$', views.skill_execution_detail_view, name='skill_execution_detail'),
    path('skills/<str:skill_name>/detail/', views.skill_detail_view, name='skill_detail'),
    path('skills/<str:skill_name>/edit/', views.skill_edit_view, name='skill_edit'),
    path('skills/<str:skill_name>/clear-cache/', views.skill_clear_cache, name='skill_clear_cache'),
    path('skills/<str:skill_name>/toggle/', views.skill_toggle_active, name='skill_toggle_active'),
    path('skills/<str:skill_name>/', views.skill_info, name='skill_info'),

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

    # Perfiles de Inteligencia (Niveles v2)
    path('profiles/', views.profile_list, name='profile_list'),
    path('profiles/<uuid:profile_id>/', views.profile_detail, name='profile_detail'),
    path('profiles/<uuid:profile_id>/edit/', views.profile_edit, name='profile_edit'),
    path('profiles/<uuid:profile_id>/reset/', views.profile_reset, name='profile_reset'),

    # API de Perfiles de Inteligencia
    path('api/profiles/', views.api_profile_list, name='api_profile_list'),
    path('api/profiles/me/', views.api_my_profile, name='api_my_profile'),
    path('api/profiles/<uuid:profile_id>/', views.api_profile_detail, name='api_profile_detail'),
    path('api/profiles/<uuid:profile_id>/update/', views.api_profile_update, name='api_profile_update'),
    path('api/collections/<str:collection_name>/check-access/', views.api_check_collection_access, name='api_check_collection_access'),

    # Dashboard de Consumo de IA
    path('consumo-ia/', views.ai_consumption_dashboard, name='ai_consumption_dashboard'),
]
