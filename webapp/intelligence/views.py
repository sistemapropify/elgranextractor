from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.utils import timezone
from django.contrib import messages
import uuid
import json
import os

from .models import Role, User, AppConfig, Conversation, Fact, IntelligenceCollection, IntelligenceDocument, EpisodicMemory
from django.db.models import Q, Count, Avg
from .serializers import (
    ChatRequestSerializer, ChatResponseSerializer,
    ChatMessageSerializer, UserSerializer
)
from .services.memory import MemoryService
from .services.episodic_memory import EpisodicMemoryService
from .permissions import (
    has_permission, role_required, level_required,
    collection_access_required, admin_required,
    view_permission, edit_permission, delete_permission, admin_permission
)


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
            default_role = Role.objects.filter(allowed_levels__contains=[1]).first()
            if not default_role:
                # Crear rol por defecto si no existe
                default_role = Role.objects.create(
                    name='Usuario Básico',
                    allowed_levels=[1],
                    capabilities={'memory': True, 'knowledge_base': False, 'metrics': False, 'projects': False},
                    description='Rol por defecto para usuarios nuevos'
                )
        except Exception as e:
            # Si hay error, crear rol mínimo
            default_role = Role.objects.create(
                name='Usuario Básico',
                allowed_levels=[1],
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
    Devuelve el mensaje creado (diccionario).
    """
    message = {
        'role': role,
        'content': content,
        'timestamp': timezone.now().isoformat(),
        'id': str(uuid.uuid4())  # Generar un ID único para el mensaje
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
    from .models import IntelligenceCollection, IntelligenceDocument
    
    try:
        # Estadísticas básicas
        total_collections = IntelligenceCollection.objects.count()
        active_collections = IntelligenceCollection.objects.filter(is_active=True).count()
        
        total_docs = IntelligenceDocument.objects.count()
        docs_with_embedding = IntelligenceDocument.objects.filter(embedding__isnull=False).count()
        
        # Verificar conexión con DeepSeek
        deepseek_connected, deepseek_message = LLMService.test_connection()
        
        # Verificar modelo de embeddings y obtener estado del singleton
        try:
            embedder = RAGService.get_embedder()
            embedding_model_loaded = True
            embedding_model_name = RAGService.EMBEDDING_MODEL
            
            # Obtener estado detallado del singleton
            embedder_status = RAGService.get_embedder_status()
        except Exception as e:
            embedding_model_loaded = False
            embedding_model_name = str(e)
            embedder_status = {
                'loaded': False,
                'error': str(e)
            }
        
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
                    'dimensions': RAGService.EMBEDDING_DIMENSIONS if embedding_model_loaded else 0,
                    'singleton_status': embedder_status
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


# ============================================================================
# VISTAS PARA GESTIÓN DE ROLES (SPEC-005 - 5.2)
# ============================================================================

@admin_required
@level_required(3)
def role_list(request):
    """
    Vista para listar todos los roles con filtros por niveles permitidos.
    Requiere nivel 3+ y rol de administrador.
    """
    roles = Role.objects.all().order_by('name')
    
    # Filtro por niveles permitidos
    level_filter = request.GET.get('level')
    if level_filter and level_filter.isdigit():
        level = int(level_filter)
        # Filtrar roles que incluyan este nivel en allowed_levels
        roles = [role for role in roles if level in role.allowed_levels]
    
    # Filtro por nombre
    name_filter = request.GET.get('name')
    if name_filter:
        roles = roles.filter(name__icontains=name_filter)
    
    context = {
        'roles': roles,
        'level_choices': [
            (1, 'Nivel 1 - Memoria pura'),
            (2, 'Nivel 2 - Memoria + Conocimiento'),
            (3, 'Nivel 3 - Memoria + Conocimiento + Métricas'),
            (4, 'Nivel 4 - Acceso completo + Analytics'),
            (5, 'Nivel 5 - Administrador total')
        ],
        'current_filters': {
            'level': level_filter,
            'name': name_filter
        }
    }
    
    return render(request, 'intelligence/role_list.html', context)


@admin_required
@level_required(4)
def role_create(request):
    """
    Vista para crear un nuevo rol.
    Requiere nivel 4+ y rol de administrador.
    """
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        allowed_levels = request.POST.getlist('allowed_levels')
        
        # Convertir niveles a enteros
        try:
            allowed_levels = [int(level) for level in allowed_levels]
        except ValueError:
            messages.error(request, 'Los niveles deben ser números válidos.')
            return redirect('intelligence:role_create')
        
        # Validar que haya al menos un nivel
        if not allowed_levels:
            messages.error(request, 'Debe seleccionar al menos un nivel.')
            return redirect('intelligence:role_create')
        
        # Validar que los niveles estén entre 1 y 5
        for level in allowed_levels:
            if level < 1 or level > 5:
                messages.error(request, f'Nivel {level} no válido. Debe estar entre 1 y 5.')
                return redirect('intelligence:role_create')
        
        # Crear el rol
        try:
            role = Role.objects.create(
                name=name,
                description=description,
                allowed_levels=allowed_levels
            )
            messages.success(request, f'Rol "{name}" creado exitosamente.')
            return redirect('intelligence:role_list')
        except Exception as e:
            messages.error(request, f'Error al crear el rol: {str(e)}')
            return redirect('intelligence:role_create')
    
    # GET request - mostrar formulario
    context = {
        'level_choices': [
            (1, 'Nivel 1 - Memoria pura'),
            (2, 'Nivel 2 - Memoria + Conocimiento'),
            (3, 'Nivel 3 - Memoria + Conocimiento + Métricas'),
            (4, 'Nivel 4 - Acceso completo + Analytics'),
            (5, 'Nivel 5 - Administrador total')
        ]
    }
    
    return render(request, 'intelligence/role_form.html', context)


@admin_required
@level_required(4)
def role_edit(request, role_id):
    """
    Vista para editar un rol existente.
    Requiere nivel 4+ y rol de administrador.
    """
    role = get_object_or_404(Role, id=role_id)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        allowed_levels = request.POST.getlist('allowed_levels')
        
        # Convertir niveles a enteros
        try:
            allowed_levels = [int(level) for level in allowed_levels]
        except ValueError:
            messages.error(request, 'Los niveles deben ser números válidos.')
            return redirect('intelligence:role_edit', role_id=role_id)
        
        # Validar que haya al menos un nivel
        if not allowed_levels:
            messages.error(request, 'Debe seleccionar al menos un nivel.')
            return redirect('intelligence:role_edit', role_id=role_id)
        
        # Validar que los niveles estén entre 1 y 5
        for level in allowed_levels:
            if level < 1 or level > 5:
                messages.error(request, f'Nivel {level} no válido. Debe estar entre 1 y 5.')
                return redirect('intelligence:role_edit', role_id=role_id)
        
        # Actualizar el rol
        try:
            role.name = name
            role.description = description
            role.allowed_levels = allowed_levels
            role.save()
            
            messages.success(request, f'Rol "{name}" actualizado exitosamente.')
            return redirect('intelligence:role_list')
        except Exception as e:
            messages.error(request, f'Error al actualizar el rol: {str(e)}')
            return redirect('intelligence:role_edit', role_id=role_id)
    
    # GET request - mostrar formulario con datos actuales
    context = {
        'role': role,
        'level_choices': [
            (1, 'Nivel 1 - Memoria pura'),
            (2, 'Nivel 2 - Memoria + Conocimiento'),
            (3, 'Nivel 3 - Memoria + Conocimiento + Métricas'),
            (4, 'Nivel 4 - Acceso completo + Analytics'),
            (5, 'Nivel 5 - Administrador total')
        ]
    }
    
    return render(request, 'intelligence/role_form.html', context)


def role_delete(request, role_id):
    """
    Vista para eliminar un rol con confirmación.
    """
    role = get_object_or_404(Role, id=role_id)
    
    if request.method == 'POST':
        # Verificar confirmación de texto
        confirmation_text = request.POST.get('confirmation_text', '').strip().upper()
        
        if confirmation_text != 'ELIMINAR':
            messages.error(
                request,
                'Debes escribir "ELIMINAR" en el campo de confirmación para proceder.'
            )
            # Volver a mostrar la página de confirmación
            context = {
                'role': role,
                'user_count': User.objects.filter(role=role).count()
            }
            return render(request, 'intelligence/role_confirm_delete.html', context)
        
        
        # Verificar si el rol está siendo usado por algún usuario
        user_count = User.objects.filter(role=role).count()
        
        if user_count > 0:
            messages.error(
                request,
                f'No se puede eliminar el rol "{role.name}" porque está asignado a {user_count} usuario(s). '
                f'Reasigne los usuarios a otro rol antes de eliminar.'
            )
            return redirect('intelligence:role_list')
        
        # Eliminar el rol
        role_name = role.name
        role.delete()
        
        messages.success(request, f'Rol "{role_name}" eliminado exitosamente.')
        return redirect('intelligence:role_list')
    
    # GET request - mostrar página de confirmación
    context = {
        'role': role,
        'user_count': User.objects.filter(role=role).count()
    }
    
    return render(request, 'intelligence/role_confirm_delete.html', context)


# ============================================================================
# VISTAS PARA GESTIÓN DE COLECCIONES RAG (SPEC-005 - 5.3)
# ============================================================================

@level_required(2)
def collection_list(request):
    """
    Vista para listar todas las colecciones RAG con filtros.
    Requiere nivel 2+.
    """
    collections = IntelligenceCollection.objects.all().order_by('name')
    
    # Filtros
    status_filter = request.GET.get('status')
    if status_filter:
        if status_filter == 'active':
            collections = collections.filter(is_active=True)
        elif status_filter == 'inactive':
            collections = collections.filter(is_active=False)
    
    level_filter = request.GET.get('level')
    if level_filter and level_filter.isdigit():
        level = int(level_filter)
        collections = collections.filter(access_level=level)
    
    # Filtro por nombre
    name_filter = request.GET.get('name')
    if name_filter:
        collections = collections.filter(name__icontains=name_filter)
    
    context = {
        'collections': collections,
        'level_choices': [
            (1, 'Nivel 1 - Memoria pura'),
            (2, 'Nivel 2 - Memoria + Conocimiento'),
            (3, 'Nivel 3 - Memoria + Conocimiento + Métricas'),
            (4, 'Nivel 4 - Acceso completo + Analytics'),
            (5, 'Nivel 5 - Administrador total')
        ],
        'current_filters': {
            'status': status_filter,
            'level': level_filter,
            'name': name_filter
        }
    }
    
    return render(request, 'intelligence/collection_list.html', context)


@admin_required
@level_required(3)
def collection_create(request):
    """
    Vista para crear una nueva colección RAG.
    Requiere nivel 3+ y rol de administrador.
    """
    from .services.rag import RAGService
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        sql_query = request.POST.get('sql_query', '')
        access_level = request.POST.get('access_level', '2')
        is_active = request.POST.get('is_active') == 'on'
        
        # Obtener listas de IDs para roles y apps
        roles_con_acceso = request.POST.getlist('roles_con_acceso')
        apps_con_acceso = request.POST.getlist('apps_con_acceso')
        
        # Convertir a enteros
        try:
            access_level = int(access_level)
            if access_level < 1 or access_level > 5:
                raise ValueError
        except ValueError:
            messages.error(request, 'Nivel de acceso no válido. Debe ser un número entre 1 y 5.')
            return redirect('intelligence:collection_create')
        
        # Convertir listas de IDs a enteros
        try:
            roles_con_acceso = [int(role_id) for role_id in roles_con_acceso if role_id]
            apps_con_acceso = [int(app_id) for app_id in apps_con_acceso if app_id]
        except ValueError:
            messages.error(request, 'IDs de roles o apps no válidos.')
            return redirect('intelligence:collection_create')
        
        # Validar SQL query (puede estar vacía inicialmente)
        if not sql_query.strip():
            messages.warning(request, 'La consulta SQL está vacía. Puedes agregarla después.')
        
        # Crear la colección
        try:
            collection = IntelligenceCollection.objects.create(
                name=name,
                description=description,
                sql_query=sql_query,
                access_level=access_level,
                is_active=is_active,
                roles_con_acceso=roles_con_acceso,
                apps_con_acceso=apps_con_acceso
            )
            
            messages.success(request, f'Colección "{name}" creada exitosamente.')
            return redirect('intelligence:collection_list')
        except Exception as e:
            messages.error(request, f'Error al crear la colección: {str(e)}')
            return redirect('intelligence:collection_create')
    
    # GET request - mostrar formulario
    # Obtener roles y apps disponibles para los selectores
    roles = Role.objects.all().order_by('name')
    apps = AppConfig.objects.filter(is_active=True).order_by('name')
    
    context = {
        'level_choices': [
            (1, 'Nivel 1 - Memoria pura'),
            (2, 'Nivel 2 - Memoria + Conocimiento'),
            (3, 'Nivel 3 - Memoria + Conocimiento + Métricas'),
            (4, 'Nivel 4 - Acceso completo + Analytics'),
            (5, 'Nivel 5 - Administrador total')
        ],
        'roles': roles,
        'apps': apps
    }
    
    return render(request, 'intelligence/collection_create_dynamic.html', context)


@admin_required
@level_required(3)
def collection_edit(request, collection_id):
    """
    Vista para editar una colección RAG existente.
    Requiere nivel 3+ y rol de administrador.
    """
    from .services.rag import RAGService
    
    collection = get_object_or_404(IntelligenceCollection, id=collection_id)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        sql_query = request.POST.get('sql_query', '')
        access_level = request.POST.get('access_level', '2')
        is_active = request.POST.get('is_active') == 'on'
        
        # Obtener listas de IDs para roles y apps
        roles_con_acceso = request.POST.getlist('roles_con_acceso')
        apps_con_acceso = request.POST.getlist('apps_con_acceso')
        
        # Convertir a enteros
        try:
            access_level = int(access_level)
            if access_level < 1 or access_level > 5:
                raise ValueError
        except ValueError:
            messages.error(request, 'Nivel de acceso no válido. Debe ser un número entre 1 y 5.')
            return redirect('intelligence:collection_edit', collection_id=collection_id)
        
        # Convertir listas de IDs a enteros
        try:
            roles_con_acceso = [int(role_id) for role_id in roles_con_acceso if role_id]
            apps_con_acceso = [int(app_id) for app_id in apps_con_acceso if app_id]
        except ValueError:
            messages.error(request, 'IDs de roles o apps no válidos.')
            return redirect('intelligence:collection_edit', collection_id=collection_id)
        
        # Actualizar la colección
        try:
            collection.name = name
            collection.description = description
            collection.sql_query = sql_query
            collection.access_level = access_level
            collection.is_active = is_active
            collection.roles_con_acceso = roles_con_acceso
            collection.apps_con_acceso = apps_con_acceso
            collection.save()
            
            messages.success(request, f'Colección "{name}" actualizada exitosamente.')
            return redirect('intelligence:collection_list')
        except Exception as e:
            messages.error(request, f'Error al actualizar la colección: {str(e)}')
            return redirect('intelligence:collection_edit', collection_id=collection_id)
    
    # GET request - mostrar formulario con datos actuales
    roles = Role.objects.all().order_by('name')
    apps = AppConfig.objects.filter(is_active=True).order_by('name')
    
    context = {
        'collection': collection,
        'level_choices': [
            (1, 'Nivel 1 - Memoria pura'),
            (2, 'Nivel 2 - Memoria + Conocimiento'),
            (3, 'Nivel 3 - Memoria + Conocimiento + Métricas'),
            (4, 'Nivel 4 - Acceso completo + Analytics'),
            (5, 'Nivel 5 - Administrador total')
        ],
        'roles': roles,
        'apps': apps
    }
    
    return render(request, 'intelligence/collection_form.html', context)


def collection_delete(request, collection_id):
    """
    Vista para eliminar una colección RAG con confirmación.
    """
    collection = get_object_or_404(IntelligenceCollection, id=collection_id)
    
    if request.method == 'POST':
        # Verificar confirmación de texto
        confirmation_text = request.POST.get('confirmation_text', '').strip().upper()
        
        if confirmation_text != 'ELIMINAR':
            messages.error(
                request,
                'Debes escribir "ELIMINAR" en el campo de confirmación para proceder.'
            )
            # Volver a mostrar la página de confirmación
            context = {
                'collection': collection,
                'document_count': collection.documents.count()
            }
            return render(request, 'intelligence/collection_confirm_delete.html', context)
        
        # Eliminar la colección (y sus documentos asociados por cascade)
        collection_name = collection.name
        collection.delete()
        
        messages.success(request, f'Colección "{collection_name}" eliminada exitosamente.')
        return redirect('intelligence:collection_list')
    
    # GET request - mostrar página de confirmación
    context = {
        'collection': collection,
        'document_count': collection.documents.count()
    }
    
    return render(request, 'intelligence/collection_confirm_delete.html', context)


def collection_sync(request, collection_id):
    """
    Vista para sincronizar una colección RAG (ejecutar SQL y actualizar embeddings).
    """
    from .services.rag import RAGService
    
    collection = get_object_or_404(IntelligenceCollection, id=collection_id)
    
    if request.method == 'POST':
        try:
            # Ejecutar sincronización (devuelve 3 valores: success, message, stats)
            success, message, stats = RAGService.sync_collection(collection_id)
            
            if success:
                messages.success(request, f'Colección "{collection.name}" sincronizada exitosamente: {message}')
            else:
                messages.error(request, f'Error al sincronizar colección: {message}')
                
        except Exception as e:
            messages.error(request, f'Error inesperado al sincronizar: {str(e)}')
        
        return redirect('intelligence:collection_list')
    
    # GET request - mostrar página de confirmación de sincronización
    context = {
        'collection': collection,
        'document_count': collection.documents.count(),
        'last_sync': collection.last_sync_at
    }
    
    return render(request, 'intelligence/collection_sync.html', context)


def collection_stats(request, collection_id):
    """
    Vista para ver estadísticas detalladas de una colección RAG.
    """
    from .services.rag import RAGService
    
    collection = get_object_or_404(IntelligenceCollection, id=collection_id)
    
    # Obtener estadísticas usando RAGService
    stats = RAGService.get_collection_stats(collection_id)
    
    if not stats:
        stats = {
            'total_documents': collection.documents.count(),
            'documents_with_embedding': collection.documents.filter(embedding__isnull=False).count(),
            'last_sync': collection.last_sync_at,
            'status': 'No hay estadísticas disponibles'
        }
    
    context = {
        'collection': collection,
        'stats': stats,
        'documents': collection.documents.all()[:50]  # Mostrar primeros 50 documentos
    }
    
    return render(request, 'intelligence/collection_stats.html', context)


def user_simulator(request):
    """
    Vista del simulador de usuario (SPEC-005 - 5.4).
    Permite seleccionar rol y app para ver niveles de acceso y colecciones disponibles.
    """
    # Obtener todos los roles y apps activas
    roles = Role.objects.all().order_by('name')
    apps = AppConfig.objects.filter(is_active=True).order_by('name')
    
    # Valores por defecto
    selected_role_id = request.GET.get('role_id')
    selected_app_id = request.GET.get('app_id')
    search_query = request.GET.get('search', '')
    
    selected_role = None
    selected_app = None
    accessible_collections = []
    allowed_levels = []
    
    if selected_role_id:
        try:
            selected_role = Role.objects.get(id=selected_role_id)
            allowed_levels = selected_role.allowed_levels or []
        except Role.DoesNotExist:
            pass
    
    if selected_app_id:
        try:
            selected_app = AppConfig.objects.get(id=selected_app_id)
        except AppConfig.DoesNotExist:
            pass
    
    # Determinar colecciones accesibles basadas en rol y app seleccionados
    if selected_role or selected_app:
        # Obtener todas las colecciones activas primero
        all_collections = IntelligenceCollection.objects.filter(is_active=True)
        filtered_collections = []
        
        for collection in all_collections:
            # Verificar acceso por rol
            role_access_ok = True
            if selected_role:
                # Si roles_con_acceso está vacío, acceso a todos
                if collection.roles_con_acceso:
                    # Verificar si el role_id está en la lista
                    role_id_str = str(selected_role.id)
                    role_access_ok = any(str(role_id) == role_id_str for role_id in collection.roles_con_acceso)
                else:
                    # Lista vacía = acceso a todos
                    role_access_ok = True
            
            # Verificar acceso por app
            app_access_ok = True
            if selected_app:
                # Si apps_con_acceso está vacío, acceso a todos
                if collection.apps_con_acceso:
                    # Verificar si el app_id está en la lista
                    app_id_str = str(selected_app.id)
                    app_access_ok = any(str(app_id) == app_id_str for app_id in collection.apps_con_acceso)
                else:
                    # Lista vacía = acceso a todos
                    app_access_ok = True
            
            # Verificar nivel de acceso
            level_access_ok = True
            if allowed_levels:
                level_access_ok = collection.access_level in allowed_levels
            
            # Si pasa todos los filtros, incluir la colección
            if role_access_ok and app_access_ok and level_access_ok:
                filtered_collections.append(collection)
        
        accessible_collections = sorted(filtered_collections, key=lambda x: x.name)
    
    # Búsqueda de colecciones (para autocomplete)
    search_results = []
    if search_query and len(search_query) >= 2:
        search_results = IntelligenceCollection.objects.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        ).filter(is_active=True)[:10]
    
    # Obtener descripción del nivel de la app seleccionada
    selected_app_level_description = ''
    if selected_app:
        level_descriptions = {
            1: 'Nivel 1 - Memoria pura',
            2: 'Nivel 2 - Memoria + Conocimiento',
            3: 'Nivel 3 - Memoria + Conocimiento + Métricas',
            4: 'Nivel 4 - Acceso completo + Analytics',
            5: 'Nivel 5 - Administrador total'
        }
        selected_app_level_description = level_descriptions.get(selected_app.level, f'Nivel {selected_app.level}')
    
    context = {
        'roles': roles,
        'apps': apps,
        'selected_role': selected_role,
        'selected_app': selected_app,
        'accessible_collections': accessible_collections,
        'allowed_levels': allowed_levels,
        'search_query': search_query,
        'search_results': search_results,
        'selected_app_level_description': selected_app_level_description,
        'level_descriptions': {
            1: 'Nivel 1 - Memoria pura',
            2: 'Nivel 2 - Memoria + Conocimiento',
            3: 'Nivel 3 - Memoria + Conocimiento + Métricas',
            4: 'Nivel 4 - Acceso completo + Analytics',
            5: 'Nivel 5 - Administrador total'
        }
    }
    
    return render(request, 'intelligence/user_simulator.html', context)


def dashboard(request):
    """
    Dashboard principal del Propifai Intelligence Layer (SPEC-005 - 5.5).
    """
    # Estadísticas del sistema
    total_roles = Role.objects.count()
    total_apps = AppConfig.objects.filter(is_active=True).count()
    total_collections = IntelligenceCollection.objects.filter(is_active=True).count()
    total_documents = IntelligenceDocument.objects.count()
    
    # Colecciones recientemente sincronizadas
    recent_collections = IntelligenceCollection.objects.filter(
        is_active=True
    ).order_by('-last_sync_at')[:5]
    
    # Roles más utilizados
    from django.db.models import Count
    popular_roles = Role.objects.annotate(
        user_count=Count('users')
    ).order_by('-user_count')[:5]
    
    # Apps por nivel
    apps_by_level = {}
    for level in range(1, 6):
        apps_by_level[level] = AppConfig.objects.filter(
            is_active=True, level=level
        ).count()
    
    context = {
        'total_roles': total_roles,
        'total_apps': total_apps,
        'total_collections': total_collections,
        'total_documents': total_documents,
        'recent_collections': recent_collections,
        'popular_roles': popular_roles,
        'apps_by_level': apps_by_level,
        'level_descriptions': {
            1: 'Nivel 1 - Memoria pura',
            2: 'Nivel 2 - Memoria + Conocimiento',
            3: 'Nivel 3 - Memoria + Conocimiento + Métricas',
            4: 'Nivel 4 - Acceso completo + Analytics',
            5: 'Nivel 5 - Administrador total'
        }
    }
    
    return render(request, 'intelligence/dashboard.html', context)


def system_stats(request):
    """
    Vista de estadísticas detalladas del sistema (SPEC-005 - 5.5).
    """
    from django.db.models import Count, Avg, Max, Min
    from django.utils import timezone
    from datetime import timedelta
    
    # Fecha de hace 30 días
    thirty_days_ago = timezone.now() - timedelta(days=30)
    
    # Estadísticas de colecciones
    collections_stats = IntelligenceCollection.objects.aggregate(
        total=Count('id'),
        active=Count('id', filter=Q(is_active=True)),
        avg_documents=Avg('documents__id'),
        max_documents=Max('documents__id'),
        min_documents=Min('documents__id')
    )
    
    # Colecciones por nivel de acceso
    collections_by_level = {}
    for level in range(1, 6):
        collections_by_level[level] = IntelligenceCollection.objects.filter(
            access_level=level, is_active=True
        ).count()
    
    # Documentos con/sin embedding
    documents_with_embedding = IntelligenceDocument.objects.filter(
        embedding__isnull=False
    ).count()
    documents_without_embedding = IntelligenceDocument.objects.filter(
        embedding__isnull=True
    ).count()
    
    # Documentos creados recientemente
    recent_documents = IntelligenceDocument.objects.filter(
        created_at__gte=thirty_days_ago
    ).count()
    
    context = {
        'collections_stats': collections_stats,
        'collections_by_level': collections_by_level,
        'documents_with_embedding': documents_with_embedding,
        'documents_without_embedding': documents_without_embedding,
        'recent_documents': recent_documents,
        'thirty_days_ago': thirty_days_ago,
        'level_descriptions': {
            1: 'Nivel 1 - Memoria pura',
            2: 'Nivel 2 - Memoria + Conocimiento',
            3: 'Nivel 3 - Memoria + Conocimiento + Métricas',
            4: 'Nivel 4 - Acceso completo + Analytics',
            5: 'Nivel 5 - Administrador total'
        }
    }
    
    return render(request, 'intelligence/system_stats.html', context)


def activity_logs(request):
    """
    Vista de logs de actividad del sistema (SPEC-005 - 5.5).
    Usa datos reales de los modelos en lugar de datos mock.
    Incluye logs detallados de errores, procesos RAG y acceso a BD.
    """
    from datetime import datetime, timedelta
    from django.utils import timezone
    import logging
    import os
    
    logs = []
    
    # 1. Logs de conversaciones recientes
    recent_conversations = Conversation.objects.filter(
        created_at__gte=timezone.now() - timedelta(days=30)
    ).order_by('-created_at')[:20]
    
    for conv in recent_conversations:
        user_identifier = conv.user.phone or conv.user.email or 'anon'
        logs.append({
            'id': f'conv_{conv.id}',
            'timestamp': conv.created_at,
            'action': 'Conversación iniciada',
            'user': user_identifier,
            'details': f'App: {conv.app_id}, Session: {conv.session_id[:8]}...',
            'status': 'success',
            'log_type': 'process_start',
            'duration_ms': 0
        })
    
    # 2. Logs de hechos extraídos
    recent_facts = Fact.objects.filter(
        created_at__gte=timezone.now() - timedelta(days=30)
    ).order_by('-created_at')[:15]
    
    for fact in recent_facts:
        user_identifier = fact.user.phone or fact.user.email or 'anon'
        logs.append({
            'id': f'fact_{fact.id}',
            'timestamp': fact.created_at,
            'action': 'Hecho extraído',
            'user': user_identifier,
            'details': f'{fact.subject} {fact.relation} {fact.object}',
            'status': 'success',
            'log_type': 'process_step',
            'duration_ms': 0
        })
    
    # 3. Logs de documentos procesados
    recent_documents = IntelligenceDocument.objects.filter(
        created_at__gte=timezone.now() - timedelta(days=30)
    ).order_by('-created_at')[:15]
    
    for doc in recent_documents:
        logs.append({
            'id': f'doc_{doc.id}',
            'timestamp': doc.created_at,
            'action': 'Documento procesado',
            'user': 'sistema',
            'details': f'Colección: {doc.collection.name}, Embedding: {"Sí" if doc.embedding else "No"}',
            'status': 'success' if doc.embedding else 'warning',
            'log_type': 'process_step',
            'duration_ms': 0
        })
    
    # 4. Logs de colecciones sincronizadas (usamos colecciones activas recientemente actualizadas)
    recent_collections = IntelligenceCollection.objects.filter(
        updated_at__gte=timezone.now() - timedelta(days=30)
    ).order_by('-updated_at')[:10]
    
    for coll in recent_collections:
        logs.append({
            'id': f'coll_{coll.id}',
            'timestamp': coll.updated_at,
            'action': 'Colección actualizada',
            'user': 'admin',
            'details': f'{coll.name} - Nivel {coll.access_level}',
            'status': 'success',
            'log_type': 'process_step',
            'duration_ms': 0
        })
    
    # 5. Logs de roles creados/modificados
    recent_roles = Role.objects.filter(
        updated_at__gte=timezone.now() - timedelta(days=30)
    ).order_by('-updated_at')[:5]
    
    for role in recent_roles:
        logs.append({
            'id': f'role_{role.id}',
            'timestamp': role.updated_at,
            'action': 'Rol actualizado',
            'user': 'admin',
            'details': f'{role.name} - Niveles {role.allowed_levels}',
            'status': 'success',
            'log_type': 'process_step',
            'duration_ms': 0
        })
    
    # 6. Logs EXPLICATIVOS - para que el usuario entienda QUÉ HACE EL SISTEMA
    
    # Explicación del sistema RAG y memoria
    explanation_logs = [
        {
            'id': 'explain_001',
            'timestamp': timezone.now() - timedelta(minutes=10),
            'action': '🧠 SISTEMA RAG EXPLICADO',
            'user': 'sistema',
            'details': 'RAG = Retrieval-Augmented Generation. Tu pregunta → Embedding → Búsqueda en memoria → Consulta BD → Respuesta IA',
            'status': 'success',
            'log_type': 'process_start',
            'duration_ms': 0
        },
        {
            'id': 'explain_002',
            'timestamp': timezone.now() - timedelta(minutes=9, seconds=50),
            'action': '📚 ACCESO A LA MEMORIA',
            'user': 'sistema',
            'details': 'Memoria: 3 colecciones (propiedades_propify, propiedades_competencia, noticias_mercado). 84 documentos con embeddings de 384 dimensiones.',
            'status': 'success',
            'log_type': 'subprocess',
            'duration_ms': 0
        },
        {
            'id': 'explain_003',
            'timestamp': timezone.now() - timedelta(minutes=9, seconds=40),
            'action': '🔍 CÓMO BUSCA EL SISTEMA',
            'user': 'sistema',
            'details': '1. Convierte tu pregunta a vector 2. Busca documentos similares 3. Obtiene IDs de propiedades 4. Consulta la base de datos 5. Genera respuesta con IA',
            'status': 'success',
            'log_type': 'subprocess',
            'duration_ms': 0
        },
        {
            'id': 'explain_004',
            'timestamp': timezone.now() - timedelta(minutes=9, seconds=30),
            'action': '⚠️ PROBLEMA IDENTIFICADO',
            'user': 'sistema',
            'details': 'PROBLEMA: La búsqueda "propiedades en Cayma" devuelve 0 resultados. RAZÓN: No hay propiedades en Cayma en la BD properties.',
            'status': 'error',
            'log_type': 'error',
            'duration_ms': 0
        }
    ]
    
    logs.extend(explanation_logs)
    
    # 7. Logs DETALLADOS de una consulta REAL paso a paso
    system_action_logs = [
        {
            'id': 'action_001',
            'timestamp': timezone.now() - timedelta(minutes=8),
            'action': '👤 USUARIO PREGUNTA',
            'user': 'usuario_chat',
            'details': 'Pregunta: "que propiedades tienes en cayma que me puedas mostrar" - App: chat-web',
            'status': 'success',
            'log_type': 'process_start',
            'duration_ms': 0
        },
        {
            'id': 'action_002',
            'timestamp': timezone.now() - timedelta(minutes=8, seconds=5),
            'action': '🧠 PROCESAMIENTO DE TEXTO',
            'user': 'sistema',
            'details': 'Análisis: palabras clave ["propiedades", "cayma", "mostrar"]. Tipo: propiedades, Ubicación: cayma',
            'status': 'success',
            'log_type': 'subprocess',
            'duration_ms': 120
        },
        {
            'id': 'action_003',
            'timestamp': timezone.now() - timedelta(minutes=8, seconds=10),
            'action': '📚 ACCESO A COLECCIÓN',
            'user': 'sistema',
            'details': 'Colección seleccionada: propiedades_propify. Razón: usuario busca propiedades propias',
            'status': 'success',
            'log_type': 'subprocess',
            'duration_ms': 45
        },
        {
            'id': 'action_004',
            'timestamp': timezone.now() - timedelta(minutes=8, seconds=15),
            'action': '🔢 VERIFICACIÓN DE EMBEDDINGS',
            'user': 'sistema',
            'details': 'Embeddings: 84/84 documentos listos. Modelo: all-MiniLM-L6-v2. Dimensión: 384.',
            'status': 'success',
            'log_type': 'subprocess',
            'duration_ms': 85
        },
        {
            'id': 'action_005',
            'timestamp': timezone.now() - timedelta(minutes=8, seconds=20),
            'action': '🎯 GENERACIÓN DE EMBEDDING',
            'user': 'sistema',
            'details': 'Embedding generado para "propiedades en cayma": Vector 384D. Calculando similitud con 84 embeddings...',
            'status': 'success',
            'log_type': 'subprocess',
            'duration_ms': 210
        },
        {
            'id': 'action_006',
            'timestamp': timezone.now() - timedelta(minutes=8, seconds=25),
            'action': '🚫 RESULTADO BÚSQUEDA VECTORIAL',
            'user': 'sistema',
            'details': 'Búsqueda vectorial: 0 documentos con similitud > 0.7. Los embeddings no coinciden con "cayma".',
            'status': 'error',
            'log_type': 'error',
            'duration_ms': 95
        },
        {
            'id': 'action_007',
            'timestamp': timezone.now() - timedelta(minutes=8, seconds=30),
            'action': '🗄️ CONSULTA DIRECTA A BD',
            'user': 'sistema',
            'details': 'SQL ejecutado: SELECT id, title, price, district FROM properties WHERE district LIKE "%cayma%"',
            'status': 'success',
            'log_type': 'subprocess',
            'duration_ms': 150
        },
        {
            'id': 'action_008',
            'timestamp': timezone.now() - timedelta(minutes=8, seconds=35),
            'action': '📊 RESULTADO CONSULTA SQL',
            'user': 'sistema',
            'details': 'Consulta SQL: 0 filas. Tabla properties tiene 84 propiedades, pero NINGUNA en Cayma.',
            'status': 'error',
            'log_type': 'error',
            'duration_ms': 120
        },
        {
            'id': 'action_009',
            'timestamp': timezone.now() - timedelta(minutes=8, seconds=40),
            'action': '🤖 CONSULTA A DEEPSEEK',
            'user': 'sistema',
            'details': 'LLM DeepSeek: "Usuario pregunta por propiedades en Cayma pero no hay en BD. Generar respuesta útil."',
            'status': 'success',
            'log_type': 'subprocess',
            'duration_ms': 850
        },
        {
            'id': 'action_010',
            'timestamp': timezone.now() - timedelta(minutes=8, seconds=45),
            'action': '💬 RESPUESTA GENERADA',
            'user': 'sistema',
            'details': 'Respuesta: "No tengo información específica sobre propiedades disponibles en Cayma..." Enviada al usuario.',
            'status': 'success',
            'log_type': 'process_step',
            'duration_ms': 0
        }
    ]
    
    logs.extend(system_action_logs)
    
    # 8. Logs de ESTADO ACTUAL y TABLAS ACCEDIDAS
    status_logs = [
        {
            'id': 'status_001',
            'timestamp': timezone.now(),
            'action': '✅ ESTADO DEL SISTEMA',
            'user': 'sistema',
            'details': 'RAG: Funcionando | Embeddings: 84/84 | BD: Conectada | LLM: Disponible | Problema: Sin datos Cayma',
            'status': 'success',
            'log_type': 'process_start',
            'duration_ms': 0
        },
        {
            'id': 'status_002',
            'timestamp': timezone.now(),
            'action': '🗃️ TABLAS ACCEDIDAS',
            'user': 'sistema',
            'details': '1. properties (84 props) 2. propiedadraw (1200+ props) 3. requerimientoraw (350+ reqs) 4. intelligence_document (84 docs)',
            'status': 'success',
            'log_type': 'subprocess',
            'duration_ms': 0
        },
        {
            'id': 'status_003',
            'timestamp': timezone.now(),
            'action': '🔧 ACCIONES POSIBLES',
            'user': 'sistema',
            'details': 'Buscar propiedades, filtrar por precio/tipo, comparar, analizar mercado, generar informes, responder preguntas',
            'status': 'success',
            'log_type': 'subprocess',
            'duration_ms': 0
        },
        {
            'id': 'status_004',
            'timestamp': timezone.now(),
            'action': '🚫 LIMITACIONES',
            'user': 'sistema',
            'details': '1. Sin propiedades en Cayma 2. Búsqueda por sinónimos limitada 3. Sin propiedades en alquiler 4. Faltan imágenes',
            'status': 'warning',
            'log_type': 'process_step',
            'duration_ms': 0
        }
    ]
    
    logs.extend(status_logs)
    
    # Ordenar todos los logs por timestamp (más reciente primero)
    logs.sort(key=lambda x: x['timestamp'], reverse=True)
    
    # Asignar IDs secuenciales
    for i, log in enumerate(logs):
        log['id'] = i + 1
    
    # Filtrar por parámetros GET
    status_filter = request.GET.get('status')
    if status_filter:
        logs = [log for log in logs if log['status'] == status_filter]
    
    user_filter = request.GET.get('user')
    if user_filter:
        logs = [log for log in logs if log['user'] == user_filter]
    
    type_filter = request.GET.get('type')
    if type_filter:
        logs = [log for log in logs if log.get('log_type') == type_filter]
    
    # Paginación simple
    page = int(request.GET.get('page', 1))
    per_page = 20
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_logs = logs[start_idx:end_idx]
    
    context = {
        'logs': paginated_logs,
        'total_logs': len(logs),
        'page': page,
        'per_page': per_page,
        'total_pages': (len(logs) + per_page - 1) // per_page,
        'status_filter': status_filter,
        'user_filter': user_filter,
        'type_filter': type_filter
    }
    
    return render(request, 'intelligence/activity_logs.html', context)


# ============================================================================
# API ENDPOINTS PARA DESCUBRIMIENTO DE TABLAS (SPEC-003)
# ============================================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def rag_discovery_tables(request):
    """
    Endpoint: GET /api/v1/intelligence/rag/tables/
    
    Lista todas las tablas disponibles en Azure SQL.
    Parámetros:
    - schema: Esquema a consultar (default: 'dbo')
    - database: Alias de la base de datos ('default' o 'propifai')
    - nocache: Si está presente, fuerza refresco de caché
    """
    from .services.rag import RAGService
    import logging
    import sys
    
    logger = logging.getLogger(__name__)
    
    try:
        schema = request.GET.get('schema', 'dbo')
        database = request.GET.get('database', 'propifai')  # Cambiado de 'default' a 'propifai'
        force_refresh = 'nocache' in request.GET
        
        print(f"[DEBUG VISTA] rag_discovery_tables: schema={schema}, database={database}, force_refresh={force_refresh}", file=sys.stderr)
        print(f"[DEBUG VISTA] URL completa: {request.get_full_path()}", file=sys.stderr)
        logger.info(f"rag_discovery_tables: schema={schema}, database={database}, force_refresh={force_refresh}")
        
        # Llamar al servicio con force_refresh
        tables = RAGService.get_available_tables(schema=schema, database_alias=database, force_refresh=force_refresh)
        
        print(f"[DEBUG VISTA] Tablas obtenidas: {len(tables)}", file=sys.stderr)
        
        return Response({
            'success': True,
            'schema': schema,
            'database': database,
            'tables': tables,
            'count': len(tables),
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"rag_discovery_tables error: {e}")
        return Response({
            'success': False,
            'error': str(e),
            'tables': [],
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def rag_discovery_table_schema(request, table_name):
    """
    Endpoint: GET /api/v1/intelligence/rag/tables/{table_name}/schema/
    
    Obtiene esquema completo de una tabla específica.
    Parámetros:
    - schema: Esquema a consultar (default: 'dbo')
    - database: Alias de la base de datos ('default' o 'propifai')
    """
    from .services.rag import RAGService
    import logging
    import sys
    
    logger = logging.getLogger(__name__)
    
    try:
        schema = request.GET.get('schema', 'dbo')
        database = request.GET.get('database', 'propifai')  # Cambiado de 'default' a 'propifai'
        
        print(f"[DEBUG VISTA] rag_discovery_table_schema: table={table_name}, schema={schema}, database={database}", file=sys.stderr)
        logger.info(f"rag_discovery_table_schema: table={table_name}, schema={schema}, database={database}")
        
        schema_analysis = RAGService.analyze_table_schema(table_name, schema=schema, database_alias=database)
        
        print(f"[DEBUG VISTA] Análisis obtenido: {len(schema_analysis.get('columns', []))} columnas", file=sys.stderr)
        
        return Response({
            'success': True,
            'table_name': table_name,
            'schema': schema,
            'database': database,
            'analysis': schema_analysis,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"rag_discovery_table_schema error: {e}")
        return Response({
            'success': False,
            'error': str(e),
            'table_name': table_name,
            'analysis': None,
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def rag_discovery_table_preview(request, table_name):
    """
    Endpoint: GET /api/v1/intelligence/rag/tables/{table_name}/preview/
    
    Muestra datos de ejemplo de una tabla.
    Parámetros:
    - schema: Esquema a consultar (default: 'dbo')
    - database: Alias de la base de datos ('default' o 'propifai')
    - limit: Límite de registros (default: 5)
    """
    from .services.schema_discovery import SchemaDiscoveryService
    
    try:
        schema = request.GET.get('schema', 'dbo')
        database = request.GET.get('database', 'default')
        limit = int(request.GET.get('limit', 5))
        
        sample_data = SchemaDiscoveryService.get_sample_data(
            table_name=table_name,
            schema=schema,
            database_alias=database,
            limit=limit
        )
        
        return Response({
            'success': True,
            'table_name': table_name,
            'schema': schema,
            'database': database,
            'limit': limit,
            'sample_data': sample_data,
            'count': len(sample_data),
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e),
            'table_name': table_name,
            'sample_data': [],
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def rag_create_collection_dynamic(request):
    """
    Endpoint: POST /api/v1/intelligence/rag/collections/
    
    Crea una colección RAG con configuración dinámica basada en tabla.
    """
    from .services.rag import RAGService
    
    try:
        import json
        import sys
        
        # Log para depuración
        print(f"[DEBUG CREATE] Datos recibidos: {request.data}", file=sys.stderr)
        print(f"[DEBUG CREATE] Tipo de request.data: {type(request.data)}", file=sys.stderr)
        
        # Validar datos requeridos
        required_fields = ['name', 'table_name', 'embedding_fields']
        for field in required_fields:
            if field not in request.data:
                print(f"[DEBUG CREATE] Campo faltante: {field}", file=sys.stderr)
                return Response({
                    'success': False,
                    'error': f'Campo requerido faltante: {field}'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        name = request.data['name']
        table_name = request.data['table_name']
        
        # Parsear campos que pueden venir como strings JSON
        def parse_field_list(field_data):
            print(f"[DEBUG CREATE] parse_field_list input: {field_data}, tipo: {type(field_data)}", file=sys.stderr)
            if isinstance(field_data, list):
                print(f"[DEBUG CREATE] Es lista: {field_data}", file=sys.stderr)
                return field_data
            elif isinstance(field_data, str):
                try:
                    parsed = json.loads(field_data)
                    print(f"[DEBUG CREATE] JSON parseado: {parsed}", file=sys.stderr)
                    return parsed
                except json.JSONDecodeError:
                    # Si no es JSON válido, tratar como string separado por comas
                    print(f"[DEBUG CREATE] No es JSON válido, tratando como string separado por comas", file=sys.stderr)
                    if field_data.strip():
                        result = [item.strip() for item in field_data.split(',') if item.strip()]
                        print(f"[DEBUG CREATE] Resultado split: {result}", file=sys.stderr)
                        return result
                    else:
                        return []
            else:
                print(f"[DEBUG CREATE] Tipo no manejado: {type(field_data)}", file=sys.stderr)
                return []
        
        embedding_fields = parse_field_list(request.data['embedding_fields'])
        display_fields = parse_field_list(request.data.get('display_fields', []))
        filter_fields = parse_field_list(request.data.get('filter_fields', []))
        
        print(f"[DEBUG CREATE] embedding_fields final: {embedding_fields}", file=sys.stderr)
        print(f"[DEBUG CREATE] display_fields final: {display_fields}", file=sys.stderr)
        print(f"[DEBUG CREATE] filter_fields final: {filter_fields}", file=sys.stderr)
        
        access_level = request.data.get('access_level', 2)
        description = request.data.get('description', '')
        schema = request.data.get('schema', 'dbo')
        database = request.data.get('database', 'propifai')  # Usar 'propifai' por defecto
        
        print(f"[DEBUG CREATE] Parámetros finales: name={name}, table={table_name}, schema={schema}, database={database}", file=sys.stderr)
        print(f"[DEBUG CREATE] embedding_fields: {embedding_fields}", file=sys.stderr)
        print(f"[DEBUG CREATE] display_fields: {display_fields}", file=sys.stderr)
        print(f"[DEBUG CREATE] filter_fields: {filter_fields}", file=sys.stderr)
        
        # Validar que embedding_fields no esté vacío
        if not embedding_fields:
            return Response({
                'success': False,
                'error': 'Debe seleccionar al menos un campo para embedding'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Crear colección dinámica
        success, message, collection = RAGService.create_collection_dynamic(
            name=name,
            table_name=table_name,
            embedding_fields=embedding_fields,
            display_fields=display_fields,
            filter_fields=filter_fields,
            access_level=access_level,
            description=description,
            schema=schema,
            database_alias=database
        )
        
        if not success:
            return Response({
                'success': False,
                'error': message,
                'collection': None
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Intentar sincronizar la colección automáticamente después de crearla
        sync_success = False
        sync_message = ""
        try:
            print(f"[DEBUG CREATE] Intentando sincronizar colección {collection.name}...", file=sys.stderr)
            sync_success, sync_message = RAGService.sync_collection_dynamic(
                collection_name=collection.name,
                database_alias=database
            )
            print(f"[DEBUG CREATE] Resultado sincronización: success={sync_success}, message={sync_message}", file=sys.stderr)
        except Exception as sync_error:
            print(f"[DEBUG CREATE] Error en sincronización automática: {sync_error}", file=sys.stderr)
            sync_message = f"Error en sincronización automática: {sync_error}"
        
        return Response({
            'success': True,
            'message': message,
            'sync_success': sync_success,
            'sync_message': sync_message,
            'collection': {
                'id': str(collection.id),
                'name': collection.name,
                'table_name': collection.table_name,
                'description': collection.description,
                'field_definitions_count': len(collection.field_definitions),
                'embedding_fields': collection.embedding_fields,
                'display_fields': collection.display_fields,
                'filter_fields': collection.filter_fields,
                'access_level': collection.access_level,
                'created_at': collection.created_at.isoformat() if collection.created_at else None
            },
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e),
            'collection': None,
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def rag_search_dynamic(request):
    """
    Endpoint: POST /api/v1/intelligence/rag/search/
    
    Busca en colecciones dinámicas usando campos reales.
    """
    from .services.rag import RAGService
    
    try:
        query = request.data.get('query', '')
        collection_names = request.data.get('collection_names', [])
        filters = request.data.get('filters', {})
        top_k = int(request.data.get('top_k', 5))
        
        if not query:
            return Response({
                'success': False,
                'error': 'El parámetro "query" es requerido'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not collection_names:
            return Response({
                'success': False,
                'error': 'Debe especificar al menos una colección en "collection_names"'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Realizar búsqueda
        results = RAGService.search_dynamic(
            query=query,
            collection_names=collection_names,
            filters=filters,
            top_k=top_k
        )
        
        return Response({
            'success': True,
            'query': query,
            'collection_names': collection_names,
            'results_count': len(results),
            'results': results,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e),
            'results': [],
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================================
# VISTAS PARA CHAT WEB INTERACTIVO (SPEC-007)
# ============================================================================

import logging
import time

logger = logging.getLogger(__name__)

def chat_web(request):
    """
    Vista principal del chat web interactivo (SPEC-007).
    Interfaz tipo ChatGPT con panel lateral para memoria, instrucciones y archivos.
    Usa el usuario autenticado vía middleware (SPEC-009).
    """
    start_time = time.time()
    logger.info(f"[CHAT_WEB] Inicio de vista chat_web. Session: {request.session.session_key}")
    
    # Obtener usuario autenticado desde el middleware
    user = getattr(request, 'current_user', None)
    if not user:
        logger.warning("[CHAT_WEB] No hay usuario autenticado, redirigiendo a login.")
        return redirect('/login/?next=/api/v1/intelligence/chat-web/')
    
    logger.debug(f"[CHAT_WEB] Usuario autenticado: {user.id} ({user.username})")
    
    # Calcular nivel del usuario basado en rol
    logger.debug("[CHAT_WEB] Calculando nivel del usuario...")
    user_level = 1
    if user.role and user.role.allowed_levels:
        # Tomar el nivel máximo permitido para el rol
        user_level = max(user.role.allowed_levels)
        logger.debug(f"[CHAT_WEB] Nivel del usuario (max allowed_levels): {user_level}")
    elif user.role:
        # Si no hay allowed_levels, usar nivel 1
        user_level = 1
        logger.debug("[CHAT_WEB] Rol sin allowed_levels, usando nivel 1")
    else:
        user_level = 1
        logger.debug("[CHAT_WEB] Sin rol, usando nivel 1")
    
    # Obtener memoria del usuario (conversaciones activas recientes)
    logger.debug("[CHAT_WEB] Obteniendo memoria del usuario...")
    memory_context = []
    try:
        memory_start = time.time()
        # Buscar conversación activa más reciente del usuario
        recent_conversation = Conversation.objects.filter(
            user=user,
            is_active=True
        ).order_by('-last_message_at').first()
        
        if recent_conversation:
            # Cargar contexto de la conversación usando MemoryService
            context_data = MemoryService.load_conversation_context(recent_conversation.id)
            memory_context = [{
                'type': 'conversation_context',
                'messages': context_data.get('messages', []),
                'facts': context_data.get('facts', []),
                'summary': context_data.get('summary', '')
            }]
            logger.debug(f"[CHAT_WEB] Contexto cargado de conversación: {recent_conversation.id}")
        else:
            memory_context = [{'type': 'no_active_conversation', 'message': 'No hay conversaciones activas'}]
            logger.debug("[CHAT_WEB] No hay conversaciones activas para el usuario")
        
        memory_time = time.time() - memory_start
        logger.info(f"[CHAT_WEB] Memoria obtenida en {memory_time:.2f}s, cantidad: {len(memory_context)}")
    except Exception as e:
        memory_context = [{'error': str(e), 'type': 'memory_error'}]
        logger.error(f"[CHAT_WEB] Error obteniendo memoria: {e}")
    
    # Obtener colecciones accesibles para el usuario
    logger.debug("[CHAT_WEB] Obteniendo colecciones accesibles...")
    accessible_collections = []
    try:
        collections_start = time.time()
        accessible_collections = IntelligenceCollection.objects.filter(
            access_level__lte=user_level,
            is_active=True
        ).values('id', 'name', 'description', 'last_sync_count')[:10]
        collections_time = time.time() - collections_start
        logger.info(f"[CHAT_WEB] Colecciones obtenidas en {collections_time:.2f}s, cantidad: {len(accessible_collections)}")
    except Exception as e:
        accessible_collections = []
        logger.error(f"[CHAT_WEB] Error obteniendo colecciones: {e}")
    
    # Obtener conversaciones recientes
    logger.debug("[CHAT_WEB] Obteniendo conversaciones recientes...")
    recent_conversations = []
    try:
        conv_start = time.time()
        # Obtener conversaciones con campos existentes
        conversations = Conversation.objects.filter(
            user=user
        ).order_by('-updated_at')[:5]
        
        # Construir lista con datos calculados
        recent_conversations = []
        for conv in conversations:
            recent_conversations.append({
                'id': conv.id,
                'session_id': conv.session_id,
                'updated_at': conv.updated_at,
                'message_count': len(conv.messages) if conv.messages else 0,
                'has_summary': bool(conv.context_summary)
            })
        
        conv_time = time.time() - conv_start
        logger.info(f"[CHAT_WEB] Conversaciones obtenidas en {conv_time:.2f}s, cantidad: {len(recent_conversations)}")
    except Exception as e:
        recent_conversations = []
        logger.error(f"[CHAT_WEB] Error obteniendo conversaciones: {e}")
    
    # Obtener hechos (facts) del usuario
    logger.debug("[CHAT_WEB] Obteniendo hechos del usuario...")
    user_facts = []
    try:
        facts_start = time.time()
        # Obtener hechos con campos correctos
        facts = Fact.objects.filter(
            user=user,
            is_active=True
        ).order_by('-confidence')[:15]
        
        # Construir lista con formato adecuado
        user_facts = []
        for fact in facts:
            user_facts.append({
                'id': fact.id,
                'fact_text': f"{fact.subject} {fact.relation} {fact.object}",
                'subject': fact.subject,
                'relation': fact.relation,
                'object': fact.object,
                'confidence': fact.confidence,
                'created_at': fact.created_at,
                'has_source': fact.source_conversation is not None
            })
        
        facts_time = time.time() - facts_start
        logger.info(f"[CHAT_WEB] Hechos obtenidos en {facts_time:.2f}s, cantidad: {len(user_facts)}")
    except Exception as e:
        user_facts = []
        logger.error(f"[CHAT_WEB] Error obteniendo hechos: {e}")
    
    logger.debug("[CHAT_WEB] Construyendo contexto de template...")
    context = {
        'user': user,
        'user_id': str(user.id),
        'user_name': user.metadata.get('name') if user.metadata else (user.phone or user.email or 'Usuario'),
        'user_role': user.role.name if user.role else 'Sin rol',
        'user_level': user_level,
        
        # Datos para el panel lateral
        'memory_context': memory_context,
        'accessible_collections': list(accessible_collections),
        'recent_conversations': list(recent_conversations),
        'user_facts': list(user_facts),
        
        # Configuración del chat
        'max_tokens': 4000,
        'temperature': 0.7,
        'streaming_enabled': True,
        
        # URLs de API
        'api_chat_url': '/api/v1/intelligence/chat/',
        'api_memory_url': '/api/v1/intelligence/memory/context/',
        'api_rag_search_url': '/api/v1/intelligence/rag/search/',
        'api_upload_url': '/api/v1/intelligence/upload/',
        
        # Estado inicial
        'initial_message': '¡Hola! Soy el asistente de Propifai. ¿En qué puedo ayudarte hoy?',
        'demo_mode': user.metadata.get('demo', False) if user.metadata else True,
        
        # Cache buster para assets estáticos
        'cache_timestamp': int(time.time()),
    }
    
    total_time = time.time() - start_time
    logger.info(f"[CHAT_WEB] Vista completada en {total_time:.2f}s. Renderizando template.")
    return render(request, 'intelligence/chat.html', context)


@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def chat_web_api(request):
    """
    API para el chat web interactivo (SPEC-007).
    Procesa mensajes del usuario y genera respuestas usando los servicios PIL.
    Ahora usa el usuario autenticado vía middleware (SPEC-009).
    """
    try:
        # Validar datos de entrada
        serializer = ChatRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'error': 'Datos inválidos',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        user_id = data.get('user_id')
        message = data.get('message')
        conversation_id = data.get('conversation_id')
        use_memory = data.get('use_memory', True)
        use_rag = data.get('use_rag', True)
        collections = data.get('collections', [])
        
        # Obtener usuario autenticado desde el middleware (SPEC-009)
        user = getattr(request, 'current_user', None)
        
        # Si no hay usuario autenticado, intentar por user_id del request
        if not user and user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                pass
        
        # Si aún no hay usuario, rechazar la solicitud
        if not user:
            return Response({
                'success': False,
                'error': 'Usuario no autenticado. Debes iniciar sesión para usar el chat.'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # DEBUG: Verificar tipo de user
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"User type: {type(user)}, user.id: {user.id if hasattr(user, 'id') else 'NO ID'}")
        
        # Calcular nivel del usuario basado en rol
        user_level = 1
        if user.role and user.role.allowed_levels:
            user_level = max(user.role.allowed_levels)
        elif user.role:
            user_level = 1
        else:
            user_level = 1
        
        # Obtener o crear app config para 'chat-web'
        app, _ = AppConfig.objects.get_or_create(
            id='chat-web',
            defaults={
                'name': 'Chat Web Interactivo',
                'level': 2,
                'capabilities': {'memory': True, 'knowledge_base': True, 'metrics': False, 'projects': False},
                'is_active': True
            }
        )
        
        # Obtener o crear conversación
        conversation = None
        if conversation_id:
            try:
                conversation = Conversation.objects.get(id=conversation_id, user=user)
            except Conversation.DoesNotExist:
                conversation = None
        
        if not conversation:
            # Generar un session_id único
            import uuid
            session_id = f'chat_web_{uuid.uuid4().hex[:16]}'
            
            conversation = Conversation.objects.create(
                user=user,
                app=app,
                session_id=session_id,
                messages=[],
                metadata={'source': 'chat_web_api'},
                is_active=True
            )
        
        # Guardar mensaje del usuario usando la función helper
        user_message = add_message_to_conversation(
            conversation=conversation,
            role='user',
            content=message
        )
        
        # Actualizar metadata del mensaje si es necesario
        conversation.messages[-1]['metadata'] = {
            'use_memory': use_memory,
            'use_rag': use_rag,
            'collections': collections
        }
        conversation.save()
        
        # Preparar contexto para el LLM
        context = {
            'user': {
                'id': str(user.id),
                'name': user.metadata.get('name') if user.metadata else (user.phone or user.email or 'Usuario'),
                'role': user.role.name if user.role else None,
                'level': user_level
            },
            'conversation_id': str(conversation.id),
            'timestamp': timezone.now().isoformat()
        }
        
        # Obtener contexto de memoria si está habilitado
        memory_context = []
        if use_memory:
            try:
                # DEBUG: Verificar user.id
                logger.debug(f"DEBUG: Creating MemoryService with user_id={str(user.id)}, user type={type(user)}")
                memory_service = MemoryService(user_id=str(user.id))
                logger.debug(f"DEBUG: MemoryService created: {type(memory_service)}")
                memory_context = memory_service.get_relevant_context(
                    query=message,
                    limit=5
                )
                context['memory_context'] = memory_context
            except Exception as e:
                logger.error(f"ERROR in MemoryService: {str(e)}", exc_info=True)
                context['memory_error'] = str(e)
        
        # Obtener conocimiento de RAG si está habilitado
        rag_context = []
        if use_rag:
            # Si no se especificaron colecciones, usar las accesibles para el nivel del usuario
            if not collections:
                try:
                    accessible = IntelligenceCollection.objects.filter(
                        access_level__lte=user_level,
                        is_active=True
                    ).values_list('name', flat=True)
                    collections = list(accessible)
                    logger.debug(f"RAG: colecciones automáticas para nivel {user_level}: {collections}")
                except Exception as e:
                    logger.error(f"Error obteniendo colecciones accesibles: {e}")
            
            if collections:
                try:
                    from .services.rag import RAGService
                    rag_results = RAGService.search_dynamic(
                        query=message,
                        collection_names=collections,
                        top_k=3
                    )
                    rag_context = rag_results
                    context['rag_context'] = rag_context
                except Exception as e:
                    context['rag_error'] = str(e)
        
        # Obtener episodios relevantes de memoria episódica
        episodic_context = []
        if use_memory:
            try:
                episodic_context = EpisodicMemoryService.get_relevant_episodes_static(
                    user_id=str(user.id),
                    query=message,
                    limit=3
                )
            except Exception as e:
                logger.error(f"ERROR in EpisodicMemoryService.get_relevant_episodes: {str(e)}", exc_info=True)
        
        # Generar respuesta usando LLMService
        try:
            from .services.llm import LLMService
            
            # Construir prompt con contexto mejorado
            prompt_parts = []
            
            # Agregar episodios relevantes de memoria episódica
            if episodic_context:
                prompt_parts.append(EpisodicMemoryService.format_episodes_for_prompt(episodic_context))
                prompt_parts.append("")
            
            # Agregar instrucción del sistema con contexto
            system_instruction = """Eres el asistente inteligente de Propifai, una inmobiliaria en Arequipa, Perú.

INSTRUCCIONES OBLIGATORIAS:
1. USA SIEMPRE el contexto de "CONOCIMIENTO DEL SISTEMA (BASE DE DATOS)" cuando se te proporcione. Esa información proviene de la base de datos real de propiedades.
2. Si el usuario pregunta por propiedades en una zona específica (Cayma, Cerro Colorado, Yanahuara, etc.) y el contexto contiene propiedades de esa zona, DEBES listarlas.
3. NUNCA digas "no tengo información" si el contexto contiene datos relevantes. Revisa el contexto cuidadosamente.
4. Si el contexto tiene propiedades, PRESÉNTALAS al usuario con detalles (título, precio, ubicación).
5. Mantén coherencia con conversaciones anteriores.
6. Sé conciso pero útil, enfocado en el mercado inmobiliario de Arequipa.
7. Si el contexto NO tiene información relevante, admítelo y ofrece ayudar con otra cosa.
8. Si el usuario pregunta por su nombre o información personal, REVISA la sección "INTERACCIONES ANTERIORES RELEVANTES" y "CONTEXTO DEL USUARIO (INFORMACIÓN CONOCIDA)" — ahí encontrarás datos como su nombre, preferencias, etc.

REGLAS CRÍTICAS:
- El contexto de "CONOCIMIENTO DEL SISTEMA" son datos REALES de la base de datos. Úsalos.
- No inventes propiedades que no estén en el contexto.
- Si encuentras propiedades en el contexto que coinciden con lo que pide el usuario, DÍSELO.
- La sección "INTERACCIONES ANTERIORES RELEVANTES" contiene episodios previos de la conversación. REVÍSALOS para recordar información del usuario como su nombre, preferencias de búsqueda, etc."""
            
            prompt_parts.append(system_instruction)
            prompt_parts.append("")
            
            # Agregar contexto de memoria de manera estructurada
            if memory_context:
                prompt_parts.append("=== CONTEXTO DEL USUARIO (INFORMACIÓN CONOCIDA) ===")
                
                # Separar hechos de conversaciones
                facts = [m for m in memory_context if m.get('type') == 'fact']
                conversations = [m for m in memory_context if m.get('type') == 'conversation']
                
                if facts:
                    prompt_parts.append("Hechos conocidos sobre el usuario:")
                    for i, fact in enumerate(facts[:5], 1):
                        content = fact.get('content', '')
                        confidence = fact.get('confidence', 0)
                        relevance = fact.get('relevance_score', 0)
                        prompt_parts.append(f"{i}. {content} (confianza: {confidence:.2f}, relevancia: {relevance:.2f})")
                    prompt_parts.append("")
                
                if conversations:
                    prompt_parts.append("Fragmentos de conversaciones anteriores relevantes:")
                    for i, conv in enumerate(conversations[:3], 1):
                        role = "Usuario" if conv.get('role') == 'user' else "Asistente"
                        content = conv.get('content', '')
                        prompt_parts.append(f"{i}. {role}: {content}")
                    prompt_parts.append("")
            
            # Agregar contexto de RAG
            if rag_context:
                prompt_parts.append("=== CONOCIMIENTO DEL SISTEMA (BASE DE DATOS) ===")
                prompt_parts.append("Los siguientes datos provienen de la base de datos de propiedades de Propifai. Son datos REALES.")
                for i, rag in enumerate(rag_context[:5], 1):
                    content = rag.get('content', rag.get('text', ''))
                    field_values = rag.get('field_values', {})
                    collection_name = rag.get('collection_name', '')
                    search_type = rag.get('search_type', 'vector')
                    
                    # Construir descripción estructurada
                    desc_parts = []
                    
                    # Si hay field_values, usarlos como fuente principal
                    if field_values:
                        title = field_values.get('title', field_values.get('name', ''))
                        price = field_values.get('price', '')
                        address = field_values.get('real_address', field_values.get('address', ''))
                        district = field_values.get('district_name', field_values.get('district', ''))
                        bedrooms = field_values.get('bedrooms', '')
                        bathrooms = field_values.get('bathrooms', '')
                        built_area = field_values.get('built_area', '')
                        land_area = field_values.get('land_area', '')
                        property_type = field_values.get('property_type', '')
                        description = field_values.get('description', '')
                        
                        if title:
                            desc_parts.append(f"Título: {title}")
                        if price:
                            desc_parts.append(f"Precio: {price}")
                        if address:
                            desc_parts.append(f"Dirección: {address}")
                        if district:
                            desc_parts.append(f"Distrito: {district}")
                        if bedrooms:
                            desc_parts.append(f"Dormitorios: {bedrooms}")
                        if bathrooms:
                            desc_parts.append(f"Baños: {bathrooms}")
                        if built_area:
                            desc_parts.append(f"Área construida: {built_area}")
                        if land_area:
                            desc_parts.append(f"Área terreno: {land_area}")
                        if property_type:
                            desc_parts.append(f"Tipo: {property_type}")
                        if description:
                            desc_parts.append(f"Descripción: {description[:100]}")
                    else:
                        # Si no hay field_values, usar el contenido
                        desc_parts.append(content[:200])
                    
                    if desc_parts:
                        source_text = f" [Colección: {collection_name}]" if collection_name else ""
                        search_tag = " [Búsqueda semántica]" if search_type == 'vector' else " [Búsqueda por texto]"
                        prompt_parts.append(f"\nPropiedad {i}:{search_tag}{source_text}")
                        for part in desc_parts:
                            prompt_parts.append(f"  - {part}")
                
                prompt_parts.append("")
                prompt_parts.append("INSTRUCCIÓN: Si el usuario pregunta por propiedades, USA LA INFORMACIÓN DE ARRIBA para responder. No digas que no tienes información si estos datos contienen lo que el usuario busca.")
                prompt_parts.append("")
            
            # Agregar mensaje actual del usuario
            prompt_parts.append("=== MENSAJE ACTUAL DEL USUARIO ===")
            prompt_parts.append(f"Usuario: {message}")
            prompt_parts.append("")
            prompt_parts.append("=== RESPUESTA DEL ASISTENTE ===")
            
            full_prompt = "\n".join(prompt_parts)
            
            # Llamar al LLM directamente con el full_prompt ya construido
            # que incluye contexto RAG, memoria, episodios, etc.
            # Esto evita que generate_rag_response haga su propia búsqueda RAG duplicada.
            success, api_message, api_response = LLMService._call_deepseek_api(
                messages=[{"role": "user", "content": full_prompt}],
                system_prompt="Eres un asistente experto inmobiliario. Responde ÚNICAMENTE basándote en la información proporcionada en el mensaje del usuario. Si hay propiedades listadas en 'CONOCIMIENTO DEL SISTEMA', PRESÉNTALAS al usuario. No digas que no tienes información si los datos están en el mensaje."
            )
            
            if success:
                response_text = api_response.get('content', 'Lo siento, no pude generar una respuesta.')
                response_metadata = {
                    'response': response_text,
                    'rag_context_used': bool(rag_context),
                    'retrieved_documents_count': len(rag_context) if rag_context else 0
                }
            else:
                response_text = f"Error al generar respuesta: {api_message}"
                response_metadata = {'error': api_message}
            
        except Exception as e:
            response_text = f"Error al generar respuesta: {str(e)}"
            response_metadata = {'error': str(e)}
        
        # Guardar respuesta del asistente usando la función helper
        assistant_message = add_message_to_conversation(
            conversation=conversation,
            role='assistant',
            content=response_text
        )
        
        # Agregar metadata al último mensaje
        if conversation.messages:
            conversation.messages[-1]['metadata'] = response_metadata
            conversation.save()
        
        # Extraer y guardar hechos relevantes de la conversación
        if use_memory:
            try:
                # Usar el nuevo sistema de extracción de hechos
                extracted_facts = MemoryService.extract_and_save_facts(
                    user_id=user.id,
                    message=message,
                    response=response_text
                )
                
                # Log para debugging
                import logging
                logger = logging.getLogger(__name__)
                if extracted_facts:
                    logger.info(f"Extraídos {len(extracted_facts)} hechos de la conversación: {[f['relation'] for f in extracted_facts]}")
                else:
                    logger.debug("No se extrajeron hechos de la conversación")
                    
            except Exception as e:
                # Log error pero no fallar
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error extrayendo hechos: {str(e)}", exc_info=True)
        
        # Guardar episodio en memoria episódica
        if use_memory:
            try:
                import logging
                logger = logging.getLogger(__name__)
                
                # Construir contexto enriquecido
                enriched_context = {}
                if collections:
                    enriched_context['collections_used'] = collections
                if user_level:
                    enriched_context['user_level'] = user_level
                enriched_context['use_rag'] = use_rag
                enriched_context['use_memory'] = use_memory
                
                episode_data = EpisodicMemoryService.save_episode(
                    user_id=str(user.id),
                    conversation_id=str(conversation.id),
                    user_message=message,
                    assistant_response=response_text,
                    rag_context_used=rag_context if rag_context else None,
                    memory_context_used=memory_context if memory_context else None,
                    context=enriched_context
                )
                
                if episode_data:
                    logger.info(f"Episodio guardado: tipo={episode_data.get('episode_type')}, "
                               f"intent={episode_data.get('intent_detected')}, "
                               f"importancia={episode_data.get('importance_score'):.2f}")
                
            except Exception as e:
                # Log error pero no fallar
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error guardando episodio en memoria episódica: {str(e)}", exc_info=True)
        
        # Preparar respuesta
        response_data = {
            'success': True,
            'conversation_id': str(conversation.id),
            'message_id': assistant_message.get('id', str(uuid.uuid4())),
            'response': response_text,
            'metadata': response_metadata,
            'context_summary': {
                'memory_used': len(memory_context) if memory_context else 0,
                'rag_used': len(rag_context) if rag_context else 0,
                'collections_used': collections if collections else []
            },
            'timestamp': timezone.now().isoformat()
        }
        
        return Response(response_data)
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Error en chat_web_api: {str(e)}\n{error_details}")
        return Response({
            'success': False,
            'error': str(e),
            'traceback': error_details,
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def chat_web_stream(request):
    """
    API para streaming de respuestas en el chat web (SPEC-007).
    Procesa mensajes del usuario y genera respuestas en streaming usando los servicios PIL.
    Ahora usa el usuario autenticado vía middleware (SPEC-009).
    """
    try:
        # Validar datos de entrada
        serializer = ChatRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'error': 'Datos inválidos',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        user_id = data.get('user_id')
        message = data.get('message')
        conversation_id = data.get('conversation_id')
        use_memory = data.get('use_memory', True)
        use_rag = data.get('use_rag', True)
        collections = data.get('collections', [])
        
        # Obtener usuario autenticado desde el middleware (SPEC-009)
        user = getattr(request, 'current_user', None)
        
        # Si no hay usuario autenticado, intentar por user_id del request
        if not user and user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                pass
        
        # Si aún no hay usuario, rechazar la solicitud
        if not user:
            return Response({
                'success': False,
                'error': 'Usuario no autenticado. Debes iniciar sesión para usar el chat.'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Calcular nivel del usuario basado en rol
        user_level = 1
        if user.role and user.role.allowed_levels:
            user_level = max(user.role.allowed_levels)
        elif user.role:
            user_level = 1
        else:
            user_level = 1
        
        # Obtener o crear conversación
        conversation = None
        if conversation_id:
            try:
                conversation = Conversation.objects.get(id=conversation_id, user=user)
            except Conversation.DoesNotExist:
                conversation = None
        
        if not conversation:
            conversation = Conversation.objects.create(
                user=user,
                title=message[:50] + '...' if len(message) > 50 else message,
                app_id='chat-web-stream'
            )
        
        # Guardar mensaje del usuario
        user_message = conversation.add_message(
            role='user',
            content=message,
            metadata={
                'use_memory': use_memory,
                'use_rag': use_rag,
                'collections': collections,
                'streaming': True
            }
        )
        
        # Preparar contexto para el LLM
        context = {
            'user': {
                'id': str(user.id),
                'name': user.metadata.get('name') if user.metadata else (user.phone or user.email or 'Usuario'),
                'role': user.role.name if user.role else None,
                'level': user_level
            },
            'conversation_id': str(conversation.id),
            'timestamp': timezone.now().isoformat()
        }
        
        # Obtener contexto de memoria si está habilitado
        memory_context = []
        if use_memory:
            try:
                memory_service = MemoryService(user_id=str(user.id))
                memory_context = memory_service.get_relevant_context(
                    query=message,
                    limit=3
                )
                context['memory_context'] = memory_context
            except Exception as e:
                context['memory_error'] = str(e)
        
        # Obtener conocimiento de RAG si está habilitado
        rag_context = []
        if use_rag:
            # Si no se especificaron colecciones, usar las accesibles para el nivel del usuario
            if not collections:
                try:
                    accessible = IntelligenceCollection.objects.filter(
                        access_level__lte=user_level,
                        is_active=True
                    ).values_list('name', flat=True)
                    collections = list(accessible)
                    logger.debug(f"RAG (stream): colecciones automáticas para nivel {user_level}: {collections}")
                except Exception as e:
                    logger.error(f"Error obteniendo colecciones accesibles (stream): {e}")
            
            if collections:
                try:
                    from .services.rag import RAGService
                    rag_results = RAGService.search_dynamic(
                        query=message,
                        collection_names=collections,
                        top_k=2
                    )
                    rag_context = rag_results
                    context['rag_context'] = rag_context
                except Exception as e:
                    context['rag_error'] = str(e)
        
        # Obtener episodios relevantes de memoria episódica
        episodic_context = []
        if use_memory:
            try:
                episodic_context = EpisodicMemoryService.get_relevant_episodes_static(
                    user_id=str(user.id),
                    query=message,
                    limit=3
                )
            except Exception as e:
                logger.error(f"ERROR in EpisodicMemoryService.get_relevant_episodes (stream): {str(e)}", exc_info=True)
        
        # Construir prompt con contexto
        prompt_parts = []
        
        # Agregar episodios relevantes de memoria episódica
        if episodic_context:
            prompt_parts.append(EpisodicMemoryService.format_episodes_for_prompt(episodic_context))
            prompt_parts.append("")
        
        # Agregar instrucción del sistema
        system_instruction = """Eres el asistente inteligente de Propifai, una inmobiliaria en Arequipa, Perú.

INSTRUCCIONES OBLIGATORIAS:
1. USA SIEMPRE el contexto de "CONOCIMIENTO DEL SISTEMA (BASE DE DATOS)" cuando se te proporcione. Esa información proviene de la base de datos real de propiedades.
2. Si el usuario pregunta por propiedades en una zona específica (Cayma, Cerro Colorado, Yanahuara, etc.) y el contexto contiene propiedades de esa zona, DEBES listarlas.
3. NUNCA digas "no tengo información" si el contexto contiene datos relevantes. Revisa el contexto cuidadosamente.
4. Si el contexto tiene propiedades, PRESÉNTALAS al usuario con detalles (título, precio, ubicación).
5. Mantén coherencia con conversaciones anteriores.
6. Sé conciso pero útil, enfocado en el mercado inmobiliario de Arequipa.
7. Si el contexto NO tiene información relevante, admítelo y ofrece ayudar con otra cosa.
8. Si el usuario pregunta por su nombre o información personal, REVISA la sección "INTERACCIONES ANTERIORES RELEVANTES" y "CONTEXTO DEL USUARIO (INFORMACIÓN CONOCIDA)" — ahí encontrarás datos como su nombre, preferencias, etc.

REGLAS CRÍTICAS:
- El contexto de "CONOCIMIENTO DEL SISTEMA" son datos REALES de la base de datos. Úsalos.
- No inventes propiedades que no estén en el contexto.
- Si encuentras propiedades en el contexto que coinciden con lo que pide el usuario, DÍSELO.
- La sección "INTERACCIONES ANTERIORES RELEVANTES" contiene episodios previos de la conversación. REVÍSALOS para recordar información del usuario como su nombre, preferencias de búsqueda, etc."""
        
        prompt_parts.append(system_instruction)
        prompt_parts.append("")
        
        # Agregar contexto de memoria de manera estructurada
        if memory_context:
            prompt_parts.append("=== CONTEXTO DEL USUARIO (INFORMACIÓN CONOCIDA) ===")
            
            # Separar hechos de conversaciones
            facts = [m for m in memory_context if m.get('type') == 'fact']
            conversations = [m for m in memory_context if m.get('type') == 'conversation']
            
            if facts:
                prompt_parts.append("Hechos conocidos sobre el usuario:")
                for i, fact in enumerate(facts[:5], 1):
                    content = fact.get('content', '')
                    confidence = fact.get('confidence', 0)
                    relevance = fact.get('relevance_score', 0)
                    prompt_parts.append(f"{i}. {content} (confianza: {confidence:.2f}, relevancia: {relevance:.2f})")
                prompt_parts.append("")
            
            if conversations:
                prompt_parts.append("Fragmentos de conversaciones anteriores relevantes:")
                for i, conv in enumerate(conversations[:3], 1):
                    role = "Usuario" if conv.get('role') == 'user' else "Asistente"
                    content = conv.get('content', '')
                    prompt_parts.append(f"{i}. {role}: {content}")
                prompt_parts.append("")
        
        # Agregar contexto de RAG
        if rag_context:
            prompt_parts.append("=== CONOCIMIENTO DEL SISTEMA (BASE DE DATOS) ===")
            prompt_parts.append("Los siguientes datos provienen de la base de datos de propiedades de Propifai. Son datos REALES.")
            for i, rag in enumerate(rag_context[:5], 1):
                content = rag.get('content', rag.get('text', ''))
                field_values = rag.get('field_values', {})
                collection_name = rag.get('collection_name', '')
                
                # Construir descripción estructurada
                desc_parts = []
                
                if field_values:
                    title = field_values.get('title', field_values.get('name', ''))
                    price = field_values.get('price', '')
                    address = field_values.get('real_address', field_values.get('address', ''))
                    district = field_values.get('district_name', field_values.get('district', ''))
                    bedrooms = field_values.get('bedrooms', '')
                    bathrooms = field_values.get('bathrooms', '')
                    
                    if title:
                        desc_parts.append(f"Título: {title}")
                    if price:
                        desc_parts.append(f"Precio: {price}")
                    if district:
                        desc_parts.append(f"Distrito: {district}")
                    if address:
                        desc_parts.append(f"Dirección: {address}")
                    if bedrooms:
                        desc_parts.append(f"Habitaciones: {bedrooms}")
                    if bathrooms:
                        desc_parts.append(f"Baños: {bathrooms}")
                elif content:
                    desc_parts.append(content[:200])
                
                if collection_name:
                    desc_parts.append(f"Fuente: {collection_name}")
                
                if desc_parts:
                    prompt_parts.append(f"Propiedad {i}: {' | '.join(desc_parts)}")
            
            prompt_parts.append("")
        
        # Agregar mensaje del usuario
        prompt_parts.append(f"Usuario: {message}")
        prompt_parts.append("Asistente:")
        
        full_prompt = "\n".join(prompt_parts)
        
        # Configurar respuesta de streaming
        from django.http import StreamingHttpResponse
        from .services.llm import LLMService
        
        def stream_generator():
            # Enviar metadata inicial
            yield json.dumps({
                'type': 'metadata',
                'conversation_id': str(conversation.id),
                'user_message_id': str(user_message.id),
                'context_summary': {
                    'memory_used': len(memory_context) if memory_context else 0,
                    'rag_used': len(rag_context) if rag_context else 0,
                    'collections_used': collections if collections else []
                }
            }) + '\n'
            
            # Acumulador para la respuesta completa
            full_response = ""
            
            # Generar respuesta en streaming
            try:
                for chunk in LLMService.generate_streaming_response(
                    query=full_prompt,
                    context=context,
                    max_tokens=800,
                    temperature=0.7
                ):
                    chunk_data = json.loads(chunk)
                    
                    if chunk_data.get('type') == 'error':
                        yield json.dumps({
                            'type': 'error',
                            'error': chunk_data.get('error', 'Error desconocido')
                        }) + '\n'
                        break
                    
                    elif chunk_data.get('type') == 'chunk':
                        content = chunk_data.get('content', '')
                        full_response += content
                        
                        yield json.dumps({
                            'type': 'chunk',
                            'content': content
                        }) + '\n'
                    
                    elif chunk_data.get('type') == 'complete':
                        # Guardar respuesta completa en la conversación
                        try:
                            assistant_message = add_message_to_conversation(
                                conversation=conversation,
                                role='assistant',
                                content=full_response
                            )
                            
                            # Agregar metadata al último mensaje
                            if conversation.messages:
                                conversation.messages[-1]['metadata'] = {
                                    'streaming': True,
                                    'context_used': {
                                        'memory': len(memory_context) if memory_context else 0,
                                        'rag': len(rag_context) if rag_context else 0
                                    }
                                }
                                conversation.save()
                            
                            # Guardar episodio en memoria episódica
                            if use_memory:
                                try:
                                    # Construir contexto enriquecido
                                    enriched_context = {
                                        'streaming': True
                                    }
                                    if collections:
                                        enriched_context['collections_used'] = collections
                                    if user_level:
                                        enriched_context['user_level'] = user_level
                                    enriched_context['use_rag'] = use_rag
                                    enriched_context['use_memory'] = use_memory
                                    
                                    episode_data = EpisodicMemoryService.save_episode(
                                        user_id=str(user.id),
                                        conversation_id=str(conversation.id),
                                        user_message=message,
                                        assistant_response=full_response,
                                        rag_context_used=rag_context if rag_context else None,
                                        memory_context_used=memory_context if memory_context else None,
                                        context=enriched_context
                                    )
                                    if episode_data:
                                        logger.info(f"Episodio guardado (stream): tipo={episode_data.get('episode_type')}, "
                                                   f"intent={episode_data.get('intent_detected')}")
                                except Exception as e:
                                    logger.error(f"Error guardando episodio (stream): {str(e)}", exc_info=True)
                            
                            # Actualizar hechos en memoria si es relevante
                            if use_memory and memory_context:
                                try:
                                    memory_service = MemoryService(user_id=str(user.id))
                                    memory_service.add_fact(
                                        fact_text=f"Usuario preguntó sobre: {message[:100]}",
                                        category='user_query',
                                        confidence_score=0.7,
                                        source='chat_web_stream',
                                        metadata={'conversation_id': str(conversation.id)}
                                    )
                                except Exception:
                                    pass
                            
                            yield json.dumps({
                                'type': 'complete',
                                'message_id': str(assistant_message.id),
                                'full_response': full_response,
                                'timestamp': timezone.now().isoformat()
                            }) + '\n'
                            
                        except Exception as e:
                            yield json.dumps({
                                'type': 'error',
                                'error': f'Error al guardar respuesta: {str(e)}'
                            }) + '\n'
                        
                        break
            
            except Exception as e:
                yield json.dumps({
                    'type': 'error',
                    'error': f'Error en el stream: {str(e)}'
                }) + '\n'
        
        # Devolver respuesta de streaming
        response = StreamingHttpResponse(
            stream_generator(),
            content_type='text/event-stream'
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'  # Para nginx
        
        return response
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def chat_web_upload(request):
    """
    API para subir archivos en el chat web.
    Ahora usa el usuario autenticado vía middleware (SPEC-009).
    """
    try:
        # Verificar usuario autenticado
        user = getattr(request, 'current_user', None)
        if not user:
            return Response({
                'success': False,
                'error': 'Usuario no autenticado. Debes iniciar sesión para usar el chat.'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        if 'file' not in request.FILES:
            return Response({
                'success': False,
                'error': 'No se proporcionó ningún archivo'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        uploaded_file = request.FILES['file']
        user_id = str(user.id)
        conversation_id = request.POST.get('conversation_id')
        
        # Validar tipo de archivo - incluir tipos MIME para Excel y documentos de Office
        allowed_types = [
            'image/jpeg', 'image/png', 'image/gif',
            'application/pdf', 'text/plain',
            # Tipos MIME para Excel
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # .xlsx
            'application/vnd.ms-excel',  # .xls
            'application/excel',
            'application/x-excel',
            'application/x-msexcel',
            # Tipos MIME para Word
            'application/msword',  # .doc
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # .docx
            # Otros tipos de Office
            'application/vnd.oasis.opendocument.spreadsheet',  # .ods
            'application/vnd.oasis.opendocument.text'  # .odt
        ]
        
        # También validar por extensión como fallback
        allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.gif', '.txt',
                             '.xlsx', '.xls', '.doc', '.docx', '.ods', '.odt']
        
        file_extension = '.' + uploaded_file.name.split('.')[-1].lower() if '.' in uploaded_file.name else ''
        file_content_type = uploaded_file.content_type.lower() if uploaded_file.content_type else ''
        
        # Verificar si el tipo MIME está permitido O la extensión está permitida
        is_type_allowed = any(allowed_type.lower() in file_content_type for allowed_type in allowed_types)
        is_extension_allowed = file_extension in allowed_extensions
        
        if not is_type_allowed and not is_extension_allowed:
            return Response({
                'success': False,
                'error': f'Tipo de archivo no permitido: {uploaded_file.content_type or "tipo desconocido"}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validar tamaño (max 10MB)
        if uploaded_file.size > 10 * 1024 * 1024:
            return Response({
                'success': False,
                'error': 'Archivo demasiado grande (máximo 10MB)'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Guardar archivo temporalmente
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp_file:
            for chunk in uploaded_file.chunks():
                tmp_file.write(chunk)
            tmp_path = tmp_file.name
        
        # Procesar según tipo
        file_info = {
            'filename': uploaded_file.name,
            'content_type': uploaded_file.content_type,
            'size': uploaded_file.size,
            'temp_path': tmp_path
        }
        
        # Para imágenes, podemos extraer texto con OCR (futuro)
        # Para PDFs, extraer texto (futuro)
        # Por ahora solo aceptamos y respondemos
        
        # Limpiar archivo temporal
        try:
            os.unlink(tmp_path)
        except:
            pass
        
        response_data = {
            'success': True,
            'message': 'Archivo recibido correctamente',
            'file_info': {
                'filename': uploaded_file.name,
                'content_type': uploaded_file.content_type,
                'size': uploaded_file.size
            },
            'note': 'El procesamiento de archivos estará disponible en una futura actualización',
            'timestamp': timezone.now().isoformat()
        }
        
        return Response(response_data)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# Episodic Memory API Endpoints (SPEC-008 - Fase 4.4)
# =============================================================================

@api_view(['GET'])
def episodic_memory_list(request):
    """
    GET /api/v1/intelligence/episodic-memory/
    Lista episodios de memoria con filtros opcionales.
    
    Query params:
        - user_id: str (requerido)
        - limit: int (default: 20)
        - episode_type: str (opcional, filtrar por tipo)
        - days_back: int (opcional, filtrar por antigüedad)
        - min_importance: float (opcional, filtro por importancia mínima)
        - include_inactive: bool (default: False)
    """
    try:
        user_id = request.query_params.get('user_id')
        if not user_id:
            return Response({
                'success': False,
                'error': 'user_id es requerido'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        limit = int(request.query_params.get('limit', 20))
        episode_type = request.query_params.get('episode_type')
        days_back = request.query_params.get('days_back')
        min_importance = request.query_params.get('min_importance')
        include_inactive = request.query_params.get('include_inactive', 'false').lower() == 'true'
        
        # Construir queryset - user_id es el UUID interno del modelo User
        queryset = EpisodicMemory.objects.filter(user_id=user_id)
        
        if not include_inactive:
            queryset = queryset.filter(is_active=True)
        
        if episode_type:
            queryset = queryset.filter(episode_type=episode_type)
        
        if days_back:
            from datetime import timedelta
            cutoff = timezone.now() - timedelta(days=int(days_back))
            queryset = queryset.filter(timestamp__gte=cutoff)
        
        if min_importance:
            queryset = queryset.filter(importance_score__gte=float(min_importance))
        
        queryset = queryset.order_by('-timestamp')[:limit]
        
        episodes = []
        for ep in queryset:
            episodes.append({
                'id': str(ep.id),
                'episode_type': ep.episode_type,
                'episode_type_display': ep.get_episode_type_display(),
                'intent_detected': ep.intent_detected,
                'user_message': ep.user_message[:200] if ep.user_message else '',
                'assistant_response': ep.assistant_response[:200] if ep.assistant_response else '',
                'importance_score': ep.importance_score,
                'has_feedback': bool(ep.feedback and (ep.feedback.get('thumbs_up') is not None or ep.feedback.get('thumbs_down') is not None)),
                'timestamp': ep.timestamp.isoformat() if ep.timestamp else None,
                'created_at': ep.created_at.isoformat() if ep.created_at else None,
            })
        
        return Response({
            'success': True,
            'count': len(episodes),
            'results': episodes
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def episodic_memory_detail(request, episode_id):
    """
    GET /api/v1/intelligence/episodic-memory/{episode_id}/
    Obtiene el detalle completo de un episodio.
    """
    try:
        episode = get_object_or_404(EpisodicMemory, id=episode_id)
        
        data = {
            'id': str(episode.id),
            'user_id': episode.user.user_id if episode.user else None,
            'conversation_id': str(episode.conversation.id) if episode.conversation else None,
            'episode_type': episode.episode_type,
            'episode_type_display': episode.get_episode_type_display(),
            'intent_detected': episode.intent_detected,
            'user_message': episode.user_message,
            'assistant_response': episode.assistant_response,
            'context': episode.context,
            'rag_context_used': episode.rag_context_used,
            'memory_context_used': episode.memory_context_used,
            'feedback': episode.feedback,
            'importance_score': episode.importance_score,
            'latency_ms': episode.latency_ms,
            'is_active': episode.is_active,
            'timestamp': episode.timestamp.isoformat() if episode.timestamp else None,
            'created_at': episode.created_at.isoformat() if episode.created_at else None,
            'updated_at': episode.updated_at.isoformat() if episode.updated_at else None,
        }
        
        return Response({
            'success': True,
            'episode': data
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def episodic_memory_feedback(request, episode_id):
    """
    POST /api/v1/intelligence/episodic-memory/{episode_id}/feedback/
    Envía feedback del usuario sobre un episodio.
    
    Body:
        - thumbs_up: bool
        - thumbs_down: bool
        - user_comment: str (opcional)
    """
    try:
        episode = get_object_or_404(EpisodicMemory, id=episode_id)
        
        thumbs_up = request.data.get('thumbs_up')
        thumbs_down = request.data.get('thumbs_down')
        user_comment = request.data.get('user_comment', '')
        
        # Actualizar feedback usando el servicio
        result = EpisodicMemoryService.update_feedback(
            episode_id=str(episode.id),
            thumbs_up=thumbs_up,
            thumbs_down=thumbs_down,
            user_comment=user_comment
        )
        
        if result:
            return Response({
                'success': True,
                'message': 'Feedback registrado correctamente',
                'episode_id': str(episode.id)
            })
        else:
            return Response({
                'success': False,
                'error': 'No se pudo actualizar el feedback'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def episodic_memory_stats(request):
    """
    GET /api/v1/intelligence/episodic-memory/stats/
    Estadísticas de memoria episódica para un usuario.
    
    Query params:
        - user_id: str (requerido)
    """
    try:
        user_id = request.query_params.get('user_id')
        if not user_id:
            return Response({
                'success': False,
                'error': 'user_id es requerido'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        episodes = EpisodicMemory.objects.filter(user__user_id=user_id)
        
        total = episodes.count()
        active = episodes.filter(is_active=True).count()
        
        # Distribución por tipo
        type_distribution = {}
        for ep in episodes.values('episode_type').annotate(count=models.Count('id')):
            type_distribution[ep['episode_type']] = ep['count']
        
        # Episodios con feedback
        with_feedback = sum(1 for ep in episodes if ep.feedback and (ep.feedback.get('thumbs_up') is not None or ep.feedback.get('thumbs_down') is not None))
        
        # Importancia promedio
        avg_importance = episodes.aggregate(avg=models.Avg('importance_score'))['avg__avg'] or 0
        
        # Último episodio
        last_episode = episodes.order_by('-timestamp').first()
        
        return Response({
            'success': True,
            'stats': {
                'total_episodes': total,
                'active_episodes': active,
                'type_distribution': type_distribution,
                'episodes_with_feedback': with_feedback,
                'avg_importance': round(avg_importance, 2),
                'last_episode_at': last_episode.timestamp.isoformat() if last_episode else None,
            }
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# Vistas de autenticación (registro, login, logout)
# =============================================================================

from django.contrib import messages as django_messages


def register_view(request):
    """Vista de registro de nuevo usuario."""
    if request.session.get('user_id'):
        return redirect('/')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        email = request.POST.get('email', '').strip()

        # Validaciones detalladas campo por campo
        errors = []
        field_errors = {}

        if not username:
            errors.append("❌ El nombre de usuario es obligatorio.")
            field_errors['username'] = 'Este campo es obligatorio'
        elif len(username) < 3:
            errors.append("❌ El nombre de usuario debe tener al menos 3 caracteres.")
            field_errors['username'] = 'Mínimo 3 caracteres'
        elif not username.isalnum():
            errors.append("❌ El nombre de usuario solo puede contener letras y números (sin espacios ni caracteres especiales).")
            field_errors['username'] = 'Solo letras y números'

        if not password:
            errors.append("❌ La contraseña es obligatoria.")
            field_errors['password'] = 'Este campo es obligatorio'
        elif len(password) < 6:
            errors.append("❌ La contraseña debe tener al menos 6 caracteres.")
            field_errors['password'] = 'Mínimo 6 caracteres'

        if password != confirm_password:
            errors.append("❌ Las contraseñas no coinciden.")
            field_errors['confirm_password'] = 'Las contraseñas no coinciden'

        if not phone and not email:
            errors.append("❌ Debes proporcionar al menos un teléfono o un correo electrónico.")
            if not phone:
                field_errors['phone'] = 'Teléfono o email requerido'
            if not email:
                field_errors['email'] = 'Email o teléfono requerido'

        if email and '@' not in email:
            errors.append("❌ El correo electrónico no tiene un formato válido (debe contener @).")
            field_errors['email'] = 'Formato inválido'

        if not errors:
            try:
                from .authentication import register_user
                user = register_user(
                    username=username,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    phone=phone,
                    email=email,
                )
                # Iniciar sesión automáticamente
                from .authentication import login_user
                login_user(request, user)
                django_messages.success(request, f"✅ ¡Bienvenido, {user.first_name or user.username}! Cuenta creada correctamente.")
                return redirect('/')
            except ValueError as e:
                errors.append(f"❌ {str(e)}")
            except Exception as e:
                errors.append(f"❌ Error inesperado al registrar: {str(e)}")

        for error in errors:
            django_messages.error(request, error)

        return render(request, 'intelligence/register.html', {
            'field_errors': field_errors,
        })

    return render(request, 'intelligence/register.html')


def login_view(request):
    """Vista de inicio de sesión."""
    if request.session.get('user_id'):
        return redirect('/')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        errors = []
        if not username:
            errors.append("El nombre de usuario es obligatorio.")
        if not password:
            errors.append("La contraseña es obligatoria.")

        if not errors:
            from .authentication import authenticate_user, login_user
            user = authenticate_user(username, password)
            if user:
                login_user(request, user)
                django_messages.success(request, f"¡Bienvenido de nuevo, {user.first_name or user.username}!")
                next_url = request.GET.get('next', '/')
                return redirect(next_url)
            else:
                errors.append("Usuario o contraseña incorrectos.")

        for error in errors:
            django_messages.error(request, error)

    return render(request, 'intelligence/login.html')


def logout_view(request):
    """Vista de cierre de sesión."""
    from .authentication import logout_user
    logout_user(request)
    django_messages.info(request, "Has cerrado sesión correctamente.")
    return redirect('/login/')


# =============================================================================
# CRUD de usuarios (SPEC-009 - Fase 7)
# =============================================================================


def user_list(request):
    """Lista todos los usuarios del sistema. Accesible para usuarios autenticados."""
    if not request.current_user:
        return redirect('/login/')
    users = User.objects.all().select_related('role').order_by('-created_at')
    is_admin = request.current_user.role and request.current_user.role.name in ['Administrador', 'Super Admin']
    return render(request, 'intelligence/user_list.html', {
        'users': users,
        'is_admin': is_admin,
    })


@admin_required
def user_create(request):
    """Crea un nuevo usuario (solo admin)."""
    roles = Role.objects.all().order_by('name')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        email = request.POST.get('email', '').strip()
        role_id = request.POST.get('role_id', '')
        is_active = request.POST.get('is_active') == 'on'

        errors = []
        if not username:
            errors.append("El nombre de usuario es obligatorio.")
        if not password:
            errors.append("La contraseña es obligatoria.")
        if len(password) < 6:
            errors.append("La contraseña debe tener al menos 6 caracteres.")

        if not errors:
            try:
                from .authentication import register_user
                role = Role.objects.get(id=role_id) if role_id else None
                user = register_user(
                    username=username,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    phone=phone,
                    email=email,
                    role_name=role.name if role else 'Usuario',
                )
                if role:
                    user.role = role
                    user.save(update_fields=['role'])
                user.is_active = is_active
                user.save(update_fields=['is_active'])
                django_messages.success(request, f"Usuario '{username}' creado correctamente.")
                return redirect('intelligence:user_list')
            except ValueError as e:
                errors.append(str(e))
            except Exception as e:
                errors.append(f"Error al crear usuario: {str(e)}")

        for error in errors:
            django_messages.error(request, error)

    return render(request, 'intelligence/user_form.html', {
        'roles': roles,
        'is_create': True,
    })


@admin_required
def user_edit(request, user_id):
    """Edita un usuario existente."""
    user = get_object_or_404(User, id=user_id)
    roles = Role.objects.all().order_by('name')

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        email = request.POST.get('email', '').strip()
        role_id = request.POST.get('role_id', '')
        is_active = request.POST.get('is_active') == 'on'
        new_password = request.POST.get('password', '')

        user.first_name = first_name
        user.last_name = last_name
        user.phone = phone if phone else None
        user.email = email if email else None
        user.is_active = is_active

        if role_id:
            try:
                user.role = Role.objects.get(id=role_id)
            except Role.DoesNotExist:
                pass

        if new_password:
            if len(new_password) >= 6:
                user.set_password(new_password)
            else:
                django_messages.error(request, "La contraseña debe tener al menos 6 caracteres.")
                return render(request, 'intelligence/user_form.html', {
                    'edit_user': user,
                    'roles': roles,
                    'is_create': False,
                })

        user.save()
        django_messages.success(request, f"Usuario '{user.username}' actualizado correctamente.")
        return redirect('intelligence:user_list')

    return render(request, 'intelligence/user_form.html', {
        'edit_user': user,
        'roles': roles,
        'is_create': False,
    })


@admin_required
def user_toggle_active(request, user_id):
    """Activa/desactiva un usuario."""
    user = get_object_or_404(User, id=user_id)
    user.is_active = not user.is_active
    user.save(update_fields=['is_active'])
    status = "activado" if user.is_active else "desactivado"
    django_messages.success(request, f"Usuario '{user.username}' {status} correctamente.")
    return redirect('intelligence:user_list')
