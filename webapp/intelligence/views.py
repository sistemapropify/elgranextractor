from django.shortcuts import render
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.utils import timezone
import uuid
import json
import os

from .models import Role, User, AppConfig, Conversation, Fact
from .serializers import (
    ChatRequestSerializer, ChatResponseSerializer,
    ChatMessageSerializer, UserSerializer
)
from .services.memory import MemoryService


def get_or_create_user(phone=None, email=None, user_id=None, app_id='web-clientes'):
    """
    Obtiene o crea un usuario basado en phone, email o user_id.
    Si no existe, crea un usuario con rol por defecto (nivel 1).
    """
    user = None
    
    if user_id:
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            pass
    
    if not user and phone:
        try:
            user = User.objects.get(phone=phone)
        except User.DoesNotExist:
            pass
    
    if not user and email:
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            pass
    
    if not user:
        # Crear nuevo usuario con rol por defecto (nivel 1)
        try:
            default_role = Role.objects.filter(level=1).first()
            if not default_role:
                # Crear rol por defecto si no existe
                default_role = Role.objects.create(
                    name='Usuario Básico',
                    level=1,
                    capabilities={'memory': True, 'knowledge_base': False, 'metrics': False, 'projects': False},
                    description='Rol por defecto para usuarios nuevos'
                )
        except Exception as e:
            # Si hay error, crear rol mínimo
            default_role = Role.objects.create(
                name='Usuario Básico',
                level=1,
                capabilities={'memory': True},
                description='Rol por defecto'
            )
        
        # Crear usuario
        user_data = {
            'role': default_role,
            'is_active': True,
            'metadata': {}
        }
        
        if phone:
            user_data['phone'] = phone
        elif email:
            user_data['email'] = email
        else:
            # Si no hay phone ni email, generar un identificador temporal
            user_data['phone'] = f'temp_{uuid.uuid4().hex[:10]}'
        
        user = User.objects.create(**user_data)
    
    return user


def get_or_create_conversation(user, app_id, session_id=None):
    """
    Obtiene o crea una conversación para el usuario y app.
    Si no se proporciona session_id, se genera uno nuevo.
    """
    if not session_id:
        session_id = f'sess_{uuid.uuid4().hex[:16]}'
    
    try:
        app = AppConfig.objects.get(id=app_id, is_active=True)
    except AppConfig.DoesNotExist:
        # Si la app no existe, usar configuración por defecto
        app, created = AppConfig.objects.get_or_create(
            id=app_id,
            defaults={
                'name': f'App {app_id}',
                'level': 1,
                'capabilities': {'memory': True},
                'is_active': True,
                'config': {}
            }
        )
    
    # Buscar conversación activa para este usuario y app
    conversation = Conversation.objects.filter(
        user=user, 
        app=app, 
        session_id=session_id,
        is_active=True
    ).first()
    
    if not conversation:
        conversation = Conversation.objects.create(
            user=user,
            app=app,
            session_id=session_id,
            messages=[],
            metadata={'app_id': app_id},
            is_active=True
        )
    
    return conversation, session_id


def add_message_to_conversation(conversation, role, content):
    """
    Agrega un mensaje a la conversación.
    Mantiene solo los últimos 50 mensajes.
    """
    message = {
        'role': role,
        'content': content,
        'timestamp': timezone.now().isoformat()
    }
    
    messages = conversation.messages
    messages.append(message)
    
    # Limitar a 50 mensajes
    if len(messages) > 50:
        messages = messages[-50:]
    
    conversation.messages = messages
    conversation.last_message_at = timezone.now()
    conversation.save()
    
    return message


def generate_response_based_on_level(user, app, message):
    """
    Genera una respuesta básica basada en el nivel de la app.
    En esta fase 1, solo devuelve respuestas estáticas.
    En fases futuras, se integrará con DeepSeek y búsqueda semántica.
    """
    level = app.level
    capabilities = app.capabilities
    
    # Respuesta básica según nivel
    if level == 1:
        response = f"Hola, soy PIL (Nivel 1). Recibí tu mensaje: '{message}'. " \
                   f"Tengo memoria de conversación pero no acceso a bases de datos externas."
    elif level == 2:
        response = f"Hola, soy PIL (Nivel 2). Recibí: '{message}'. " \
                   f"Tengo memoria y acceso a conocimiento (propiedades, noticias). " \
                   f"En futuras versiones buscaré información relevante para ti."
    elif level == 3:
        response = f"Hola, soy PIL (Nivel 3). Mensaje: '{message}'. " \
                   f"Tengo memoria, conocimiento y métricas de negocio. " \
                   f"Como gerente, podrás acceder a datos estratégicos en próximas versiones."
    else:
        response = f"Recibí tu mensaje: '{message}'. Sistema PIL en desarrollo."
    
    # Personalizar con nombre si está en metadata
    user_name = user.metadata.get('name')
    if user_name:
        response = f"Hola {user_name}, " + response[5:]  # Remover "Hola, " inicial
    
    return response


@api_view(['POST'])
@permission_classes([AllowAny])
def chat_endpoint(request):
    """
    Endpoint único: /api/v1/intelligence/chat
    Headers: X-App-ID, X-User-ID (opcional)
    
    Nuevo flujo con MemoryService (SPEC-002):
    1. Obtener o crear usuario usando MemoryService.get_or_create_user
    2. Obtener sesión activa usando MemoryService.get_active_session
    3. Guardar mensaje del usuario con MemoryService.save_message
    4. Cargar contexto de conversación con MemoryService.load_conversation_context
    5. Extraer hechos con MemoryService.extract_and_save_facts (si está habilitado)
    6. Construir prompt con memoria usando MemoryService.build_prompt_with_memory
    7. Generar respuesta (simulada por ahora)
    8. Guardar respuesta del asistente con MemoryService.save_message
    9. Retornar respuesta con session_id y metadata
    """
    # Obtener app_id de headers o parámetros
    app_id = request.headers.get('X-App-ID', 'web-clientes')
    
    # Validar request
    serializer = ChatRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    data = serializer.validated_data
    message = data['message']
    session_id = data.get('session_id')
    user_id = data.get('user_id')
    phone = data.get('phone')
    email = data.get('email')
    metadata = data.get('metadata', {})
    
    # Determinar identificador del usuario
    identifier = None
    channel = 'web'  # canal por defecto
    
    if phone:
        identifier = phone
        channel = 'whatsapp' if phone.startswith('+') else 'web'
    elif email:
        identifier = email
        channel = 'email'
    elif user_id:
        identifier = user_id
        channel = 'api'
    else:
        # Si no hay identificador, crear uno temporal
        identifier = f"temp_{uuid.uuid4().hex[:8]}"
        channel = 'anonymous'
    
    # 1. Obtener o crear usuario usando MemoryService
    try:
        user = MemoryService.get_or_create_user(
            identifier=identifier,
            channel=channel,
            metadata=metadata
        )
    except Exception as e:
        return Response(
            {'error': f'Error al obtener/crear usuario: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    # 2. Obtener sesión activa
    try:
        conversation = MemoryService.get_active_session(
            user_id=user.id,
            app_id=app_id,
            session_id=session_id
        )
    except Exception as e:
        return Response(
            {'error': f'Error al obtener sesión activa: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    # 3. Guardar mensaje del usuario
    try:
        MemoryService.save_message(conversation.id, 'user', message)
    except Exception as e:
        return Response(
            {'error': f'Error al guardar mensaje del usuario: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    # 4. Cargar contexto de conversación
    try:
        context = MemoryService.load_conversation_context(conversation.id)
    except Exception as e:
        return Response(
            {'error': f'Error al cargar contexto: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    # 5. Extraer hechos (si está habilitado)
    extracted_facts = []
    if MemoryService.EXTRACT_FACTS_ENABLED:
        try:
            extracted_facts = MemoryService.extract_and_save_facts(
                user_id=user.id,
                message=message,
                response=''  # respuesta vacía por ahora
            )
        except Exception as e:
            # No fallar si la extracción de hechos falla
            print(f"Advertencia: Error en extracción de hechos: {e}")
    
    # 6. Obtener instrucciones de capacidades según app
    try:
        app = AppConfig.objects.get(id=app_id)
        capability_instructions = app.capabilities.get('instructions', '')
    except AppConfig.DoesNotExist:
        # App por defecto
        capability_instructions = 'Puedes acceder a la base de datos de propiedades, realizar matching con requerimientos, y proporcionar análisis de mercado.'
    
    # 7. Construir prompt con memoria
    prompt = MemoryService.build_prompt_with_memory(
        context=context,
        capability_instructions=capability_instructions
    )
    
    # 8. Generar respuesta (simulada - en producción se integraría con DeepSeek)
    # Por ahora, usamos una respuesta simple basada en el mensaje
    response_text = generate_response_based_on_level(user, app, message)
    
    # 9. Guardar respuesta del asistente
    try:
        MemoryService.save_message(conversation.id, 'assistant', response_text)
    except Exception as e:
        return Response(
            {'error': f'Error al guardar respuesta del asistente: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    # 10. Preparar respuesta
    response_data = {
        'response': response_text,
        'session_id': conversation.session_id,
        'user_id': str(user.id),
        'conversation_id': str(conversation.id),
        'context_summary': conversation.context_summary,
        'extracted_facts_count': len(extracted_facts),
        'timestamp': timezone.now()
    }
    
    response_serializer = ChatResponseSerializer(response_data)
    return Response(response_serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Endpoint de salud para verificar que la API está funcionando."""
    return Response({
        'status': 'ok',
        'service': 'Propifai Intelligence Layer (PIL) v1.0',
        'phase': 'SPEC-001 - Estructura básica',
        'timestamp': timezone.now().isoformat()
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def rag_test_endpoint(request):
    """
    Endpoint de prueba para el sistema RAG (SPEC-003).
    
    Permite probar la búsqueda semántica y generación de respuestas
    enriquecidas con contexto RAG.
    """
    from .services.rag import RAGService
    from .services.llm import LLMService
    
    # Validar parámetros
    query = request.data.get('query', '')
    collection_id = request.data.get('collection_id')
    access_level = request.data.get('access_level', 1)
    include_sources = request.data.get('include_sources', True)
    
    if not query:
        return Response(
            {'error': 'El parámetro "query" es requerido'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Opción 1: Solo búsqueda RAG (sin LLM)
        if request.data.get('search_only', False):
            collection_ids = [int(collection_id)] if collection_id else None
            
            success, message, results = RAGService.search(
                query=query,
                collection_ids=collection_ids,
                access_level=access_level,
                limit=10
            )
            
            if not success:
                return Response(
                    {'error': message, 'results': []},
                    status=status.HTTP_200_OK
                )
            
            return Response({
                'query': query,
                'success': success,
                'message': message,
                'results_count': len(results),
                'results': results[:5],  # Limitar a 5 resultados para respuesta
                'timestamp': timezone.now().isoformat()
            })
        
        # Opción 2: Respuesta completa con LLM + RAG
        else:
            # Analizar intención de la consulta
            intent_success, intent_message, intent_data = LLMService.analyze_query_intent(query)
            
            # Determinar colecciones basadas en la intención
            collection_names = None
            if intent_success and intent_data.get('collections'):
                collection_names = intent_data['collections']
            
            # Generar respuesta RAG
            rag_success, rag_message, rag_response = LLMService.generate_rag_response(
                query=query,
                user_access_level=access_level,
                collection_names=collection_names,
                include_sources=include_sources
            )
            
            if not rag_success:
                return Response(
                    {'error': rag_message, 'response': ''},
                    status=status.HTTP_200_OK
                )
            
            # Preparar respuesta
            response_data = {
                'query': query,
                'success': rag_success,
                'message': rag_message,
                'response': rag_response.get('response', ''),
                'rag_context_used': rag_response.get('rag_context_used', False),
                'retrieved_documents_count': rag_response.get('retrieved_documents_count', 0),
                'intent_analysis': intent_data if intent_success else None,
                'timestamp': timezone.now().isoformat()
            }
            
            if include_sources and rag_response.get('sources'):
                response_data['sources'] = rag_response['sources'][:3]  # Limitar a 3 fuentes
            
            return Response(response_data, status=status.HTTP_200_OK)
            
    except Exception as e:
        return Response(
            {'error': f'Error en el endpoint RAG: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def rag_system_status(request):
    """
    Endpoint para verificar el estado del sistema RAG.
    
    Devuelve estadísticas y estado de salud del sistema RAG.
    """
    from .services.rag import RAGService
    from .services.llm import LLMService
    from ..models import IntelligenceCollection, IntelligenceDocument
    
    try:
        # Estadísticas básicas
        total_collections = IntelligenceCollection.objects.count()
        active_collections = IntelligenceCollection.objects.filter(is_active=True).count()
        
        total_docs = IntelligenceDocument.objects.count()
        docs_with_embedding = IntelligenceDocument.objects.filter(embedding__isnull=False).count()
        
        # Verificar conexión con DeepSeek
        deepseek_connected, deepseek_message = LLMService.test_connection()
        
        # Verificar modelo de embeddings
        try:
            embedder = RAGService.get_embedder()
            embedding_model_loaded = True
            embedding_model_name = RAGService.EMBEDDING_MODEL
        except Exception as e:
            embedding_model_loaded = False
            embedding_model_name = str(e)
        
        # Colecciones que necesitan sincronización
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=1)
        collections_needing_sync = IntelligenceCollection.objects.filter(
            is_active=True,
            last_sync_at__lt=cutoff_date
        ).count()
        
        return Response({
            'status': 'ok',
            'system': 'Propifai RAG System (SPEC-003)',
            'timestamp': timezone.now().isoformat(),
            'statistics': {
                'collections': {
                    'total': total_collections,
                    'active': active_collections,
                    'needing_sync': collections_needing_sync
                },
                'documents': {
                    'total': total_docs,
                    'with_embedding': docs_with_embedding,
                    'without_embedding': total_docs - docs_with_embedding,
                    'embedding_coverage': (docs_with_embedding / total_docs * 100) if total_docs > 0 else 0
                }
            },
            'services': {
                'deepseek_api': {
                    'connected': deepseek_connected,
                    'message': deepseek_message
                },
                'embedding_model': {
                    'loaded': embedding_model_loaded,
                    'model_name': embedding_model_name,
                    'dimensions': RAGService.EMBEDDING_DIMENSIONS if embedding_model_loaded else 0
                }
            },
            'health': {
                'overall': deepseek_connected and embedding_model_loaded,
                'issues': [] if (deepseek_connected and embedding_model_loaded) else [
                    'DeepSeek API no conectada' if not deepseek_connected else '',
                    'Modelo de embeddings no cargado' if not embedding_model_loaded else ''
                ]
            }
        })
        
    except Exception as e:
        return Response(
            {'error': f'Error obteniendo estado del sistema RAG: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
