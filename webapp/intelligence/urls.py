from django.urls import path
from . import views

app_name = 'intelligence'

urlpatterns = [
    path('chat/', views.chat_endpoint, name='chat'),
    path('health/', views.health_check, name='health_check'),
    # Endpoints RAG (SPEC-003)
    path('rag/test/', views.rag_test_endpoint, name='rag_test'),
    path('rag/status/', views.rag_system_status, name='rag_status'),
]