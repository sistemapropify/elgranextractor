from django.shortcuts import render, redirect, get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.utils import timezone
from django.contrib import messages
import uuid
import json
import os

from .models import Role, User, AppConfig, Conversation, Fact, IntelligenceCollection, IntelligenceDocument
from django.db.models import Q
from .serializers import (
    ChatRequestSerializer, ChatResponseSerializer,
    ChatMessageSerializer, UserSerializer
)
from .services.memory import MemoryService
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
    
    return render(request, 'intelligence/collection_form.html', context)


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
    """
    from datetime import datetime, timedelta
    from django.utils import timezone
    
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
            'duration_ms': 0
        })
    
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
        'user_filter': user_filter
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
        database = request.GET.get('database', 'default')
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
    
    try:
        schema = request.GET.get('schema', 'dbo')
        database = request.GET.get('database', 'default')
        schema_analysis = RAGService.analyze_table_schema(table_name, schema=schema, database_alias=database)
        
        return Response({
            'success': True,
            'table_name': table_name,
            'schema': schema,
            'database': database,
            'analysis': schema_analysis,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
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
        # Validar datos requeridos
        required_fields = ['name', 'table_name', 'embedding_fields']
        for field in required_fields:
            if field not in request.data:
                return Response({
                    'success': False,
                    'error': f'Campo requerido faltante: {field}'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        name = request.data['name']
        table_name = request.data['table_name']
        embedding_fields = request.data['embedding_fields']
        display_fields = request.data.get('display_fields', [])
        filter_fields = request.data.get('filter_fields', [])
        access_level = request.data.get('access_level', 2)
        description = request.data.get('description', '')
        schema = request.data.get('schema', 'dbo')
        
        # Validar tipos
        if not isinstance(embedding_fields, list):
            return Response({
                'success': False,
                'error': 'embedding_fields debe ser una lista'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not isinstance(display_fields, list):
            return Response({
                'success': False,
                'error': 'display_fields debe ser una lista'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not isinstance(filter_fields, list):
            return Response({
                'success': False,
                'error': 'filter_fields debe ser una lista'
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
            schema=schema
        )
        
        if not success:
            return Response({
                'success': False,
                'error': message,
                'collection': None
            }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'success': True,
            'message': message,
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

@admin_required
@level_required(2)
def chat_web(request):
    """
    Vista principal del chat web interactivo (SPEC-007).
    Interfaz tipo ChatGPT con panel lateral para memoria, instrucciones y archivos.
    """
    start_time = time.time()
    logger.info(f"[CHAT_WEB] Inicio de vista chat_web. Session: {request.session.session_key}")
    
    # Obtener usuario actual (para desarrollo, usar usuario demo si no hay autenticación)
    user = None
    user_id = request.GET.get('user_id') or request.session.get('user_id')
    logger.debug(f"[CHAT_WEB] user_id obtenido: {user_id}")
    
    if user_id:
        try:
            user = User.objects.get(id=user_id)
            logger.debug(f"[CHAT_WEB] Usuario encontrado: {user.id}")
        except User.DoesNotExist:
            user = None
            logger.debug("[CHAT_WEB] Usuario no encontrado, se creará uno demo.")
    
    # Si no hay usuario, crear uno demo para testing
    if not user:
        logger.debug("[CHAT_WEB] Creando usuario demo...")
        user, created = User.objects.get_or_create(
            phone='51999999999',
            defaults={
                'email': 'demo@propifai.com',
                'role': Role.objects.filter(name='cliente_default').first() or Role.objects.first(),
                'metadata': {'demo': True, 'source': 'chat_web', 'name': 'Usuario Demo'}
            }
        )
        request.session['user_id'] = str(user.id)
        logger.info(f"[CHAT_WEB] Usuario demo creado: {user.id} (creado: {created})")
    
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
    }
    
    total_time = time.time() - start_time
    logger.info(f"[CHAT_WEB] Vista completada en {total_time:.2f}s. Renderizando template.")
    return render(request, 'intelligence/chat.html', context)


@api_view(['POST'])
@permission_classes([AllowAny])
def chat_web_api(request):
    """
    API para el chat web interactivo (SPEC-007).
    Procesa mensajes del usuario y genera respuestas usando los servicios PIL.
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
        
        # Obtener o crear usuario
        user = None
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Usuario no encontrado'
                }, status=status.HTTP_404_NOT_FOUND)
        
        # Si no hay usuario, crear uno temporal
        if not user:
            user, created = User.objects.get_or_create(
                phone='51999999999',
                defaults={
                    'role': Role.objects.filter(name='cliente_default').first() or Role.objects.first(),
                    'metadata': {'temporal': True, 'source': 'chat_web_api', 'name': 'Usuario Temporal'}
                }
            )
        
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
        if use_rag and collections:
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
        
        # Generar respuesta usando LLMService
        try:
            from .services.llm import LLMService
            
            # Construir prompt con contexto
            prompt_parts = []
            
            # Agregar contexto de memoria
            if memory_context:
                prompt_parts.append("Contexto de memoria del usuario:")
                for mem in memory_context[:3]:
                    prompt_parts.append(f"- {mem.get('content', '')}")
                prompt_parts.append("")
            
            # Agregar contexto de RAG
            if rag_context:
                prompt_parts.append("Conocimiento relevante del sistema:")
                for rag in rag_context[:3]:
                    content = rag.get('content', rag.get('text', ''))
                    if content:
                        prompt_parts.append(f"- {content[:200]}...")
                prompt_parts.append("")
            
            # Agregar mensaje del usuario
            prompt_parts.append(f"Usuario: {message}")
            prompt_parts.append("Asistente:")
            
            full_prompt = "\n".join(prompt_parts)
            
            # Llamar al LLM
            success, llm_message, llm_data = LLMService.generate_rag_response(
                query=full_prompt,
                conversation_history=conversation.messages,
                user_access_level=user_level,
                collection_names=collections if use_rag else None,
                include_sources=True
            )
            
            if success:
                response_text = llm_data.get('response', 'Lo siento, no pude generar una respuesta.')
                response_metadata = llm_data
            else:
                response_text = f"Error al generar respuesta: {llm_message}"
                response_metadata = {'error': llm_message}
            
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
        
        # Actualizar hechos en memoria si es relevante
        if use_memory and memory_context:
            try:
                memory_service = MemoryService(user_id=str(user.id))
                # Extraer posibles hechos de la conversación
                facts_to_add = [
                    {
                        'fact_text': f"Usuario preguntó sobre: {message[:100]}",
                        'category': 'user_query',
                        'confidence_score': 0.7
                    },
                    {
                        'fact_text': f"Asistente respondió sobre: {response_text[:100]}",
                        'category': 'assistant_response',
                        'confidence_score': 0.7
                    }
                ]
                
                for fact_data in facts_to_add:
                    memory_service.add_fact(
                        fact_text=fact_data['fact_text'],
                        category=fact_data['category'],
                        confidence_score=fact_data['confidence_score'],
                        source='chat_web',
                        metadata={'conversation_id': str(conversation.id)}
                    )
            except Exception as e:
                # No fallar si la memoria tiene error
                pass
        
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
def chat_web_stream(request):
    """
    API para streaming de respuestas en el chat web (SPEC-007).
    Procesa mensajes del usuario y genera respuestas en streaming usando los servicios PIL.
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
        
        # Obtener o crear usuario
        user = None
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Usuario no encontrado'
                }, status=status.HTTP_404_NOT_FOUND)
        
        # Si no hay usuario, crear uno temporal
        if not user:
            user, created = User.objects.get_or_create(
                phone='51999999999',
                defaults={
                    'role': Role.objects.filter(name='cliente_default').first() or Role.objects.first(),
                    'metadata': {'temporal': True, 'source': 'chat_web_stream', 'name': 'Usuario Temporal'}
                }
            )
        
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
        if use_rag and collections:
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
        
        # Construir prompt con contexto
        prompt_parts = []
        
        # Agregar contexto de memoria
        if memory_context:
            prompt_parts.append("Contexto de memoria del usuario:")
            for mem in memory_context[:2]:
                prompt_parts.append(f"- {mem.get('content', '')}")
            prompt_parts.append("")
        
        # Agregar contexto de RAG
        if rag_context:
            prompt_parts.append("Conocimiento relevante del sistema:")
            for rag in rag_context[:2]:
                content = rag.get('content', rag.get('text', ''))
                if content:
                    prompt_parts.append(f"- {content[:150]}...")
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
def chat_web_upload(request):
    """
    API para subir archivos en el chat web.
    """
    try:
        if 'file' not in request.FILES:
            return Response({
                'success': False,
                'error': 'No se proporcionó ningún archivo'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        uploaded_file = request.FILES['file']
        user_id = request.POST.get('user_id')
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
