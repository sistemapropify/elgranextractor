"""
Vistas del sistema Intelligence (SPEC-007, SPEC-009).

Organización:
  1. Imports
  2. Endpoints API legacy (chat_endpoint, health_check, RAG test/status)
  3. Role CRUD (template views)
  4. Collection CRUD (template views)
  5. Dashboard / Stats / Simulator
  6. RAG Discovery & Dynamic (API)
  7. Chat Web (template view)
  8. Chat Web API (refactorizada -> ChatProcessor)
  9. Chat Web Stream (refactorizada -> ChatProcessor)
  10. Chat Web Upload
  11. Episodic Memory (API)
  12. Auth (register, login, logout)
  13. User CRUD (template views)
"""

import json
import os
import uuid
import logging
from datetime import datetime, date, timedelta

from django.contrib import messages
from django.db import connection
from django.db.models import Q, Count, Avg
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.http import StreamingHttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import (
    Role, User, AppConfig, Conversation, Fact,
    IntelligenceCollection, IntelligenceDocument, EpisodicMemory,
    SkillExecution, ConversationFlow, UserIntelligenceProfile,
)
from .serializers import (
    ChatRequestSerializer, ChatResponseSerializer,
    ChatMessageSerializer, UserSerializer,
    SkillExecuteRequestSerializer, SkillExecutionSerializer,
    ConversationFlowSerializer,
)
from .services.memory import MemoryService
from .services.episodic_memory import EpisodicMemoryService
from .services.chat_processor import ChatProcessor, ChatContext, SKILL_SYSTEM
from .services.intent_classifier import IntentClassifier, IntentType
from .intent_evaluation_data import INTENT_EVALUATION_SAMPLES
from .services.metrics import log
from .permissions import (
    has_permission, role_required, level_required,
    collection_access_required, admin_required,
    view_permission, edit_permission, delete_permission, admin_permission,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. ENDPOINTS API LEGACY
# ═══════════════════════════════════════════════════════════════════════════════


@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def chat_endpoint(request):
    """
    Endpoint legacy de chat (SPEC-007).
    Usa MemoryService directamente. Mantenido por compatibilidad.
    """
    try:
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

        # Obtener usuario
        user = getattr(request, 'current_user', None)
        if not user and user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                pass

        if not user:
            return Response({
                'success': False,
                'error': 'Usuario no autenticado'
            }, status=status.HTTP_401_UNAUTHORIZED)

        # Calcular nivel del usuario desde su perfil de inteligencia
        user_level = 1
        try:
            profile = UserIntelligenceProfile.objects.get(user=user)
            user_level = profile.level
        except UserIntelligenceProfile.DoesNotExist:
            if user.role:
                user_level = user.role.default_level

        # Obtener o crear app config
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
            session_id = f'chat_web_{uuid.uuid4().hex[:16]}'
            conversation = Conversation.objects.create(
                user=user,
                app=app,
                session_id=session_id,
                messages=[],
                metadata={'source': 'chat_endpoint'},
                is_active=True
            )

        # Guardar mensaje del usuario
        user_message = {
            'role': 'user',
            'content': message,
            'timestamp': timezone.now().isoformat(),
            'id': str(uuid.uuid4())
        }
        msgs = conversation.messages
        msgs.append(user_message)
        if len(msgs) > 50:
            msgs = msgs[-50:]
        conversation.messages = msgs
        conversation.last_message_at = timezone.now()
        conversation.save()

        # Obtener contexto de memoria
        memory_context = []
        try:
            memory_service = MemoryService(user_id=str(user.id))
            memory_context = memory_service.get_relevant_context(query=message, limit=5)
        except Exception as e:
            logger.error(f"Error en MemoryService: {str(e)}", exc_info=True)

        # Construir prompt con memoria
        context_data = {
            'user': {
                'id': str(user.id),
                'name': user.metadata.get('name') if user.metadata else (user.phone or user.email or 'Usuario'),
                'role': user.role.name if user.role else None,
                'level': user_level
            },
            'conversation_id': str(conversation.id),
            'timestamp': timezone.now().isoformat(),
            'memory_context': memory_context
        }

        from .services.llm import LLMService
        from .services.prompts import PromptManager

        full_prompt = PromptManager.build_full_prompt(
            message=message,
            memory_context=memory_context,
            rag_context=None,
            episodic_context=None,
            app_id='chat-web',
        )

        success, api_message, api_response = LLMService._call_deepseek_api(
            messages=[{"role": "user", "content": full_prompt}],
            system_prompt=PromptManager.get_deepseek_system_prompt('chat-web'),
        )

        if success:
            if isinstance(api_response, dict):
                response_text = api_response.get('content', 'Lo siento, no pude generar una respuesta.')
            else:
                response_text = 'Lo siento, no pude generar una respuesta.'
        else:
            response_text = f"Error al generar respuesta: {api_message}"

        # Guardar respuesta
        assistant_message = {
            'role': 'assistant',
            'content': response_text,
            'timestamp': timezone.now().isoformat(),
            'id': str(uuid.uuid4())
        }
        msgs = conversation.messages
        msgs.append(assistant_message)
        if len(msgs) > 50:
            msgs = msgs[-50:]
        conversation.messages = msgs
        conversation.last_message_at = timezone.now()
        conversation.save()

        return Response({
            'success': True,
            'conversation_id': str(conversation.id),
            'message_id': assistant_message['id'],
            'response': response_text,
            'metadata': {
                'response': response_text,
                'rag_context_used': False,
                'retrieved_documents_count': 0
            },
            'context_summary': {
                'memory_used': len(memory_context) if memory_context else 0,
                'rag_used': 0,
                'collections_used': []
            },
            'timestamp': timezone.now().isoformat()
        })

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Error en chat_endpoint: {str(e)}\n{error_details}")
        return Response({
            'success': False,
            'error': str(e),
            'traceback': error_details,
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
@authentication_classes([])
def health_check(request):
    """Health check del sistema Intelligence."""
    return Response({
        'status': 'ok',
        'service': 'intelligence',
        'version': '2.0.0',
        'timestamp': timezone.now().isoformat()
    })


@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def rag_test_endpoint(request):
    """Endpoint de prueba para RAG."""
    try:
        data = json.loads(request.body) if isinstance(request.body, bytes) else request.data
        query = data.get('query', '')
        collection_name = data.get('collection_name', '')

        if not query:
            return Response({
                'success': False,
                'error': 'Se requiere un query'
            }, status=status.HTTP_400_BAD_REQUEST)

        from .services.rag import RAGService

        if collection_name:
            results = RAGService.search_dynamic(
                query=query,
                collection_names=[collection_name],
                top_k=5
            )
        else:
            # Buscar en todas las colecciones activas
            collections = IntelligenceCollection.objects.filter(
                is_active=True
            ).values_list('name', flat=True)
            results = RAGService.search_dynamic(
                query=query,
                collection_names=list(collections),
                top_k=5
            )

        return Response({
            'success': True,
            'query': query,
            'collection_used': collection_name or 'all',
            'results_count': len(results),
            'results': results,
            'timestamp': timezone.now().isoformat()
        })

    except Exception as e:
        import traceback
        return Response({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc(),
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
@authentication_classes([])
def rag_system_status(request):
    """Estado del sistema RAG."""
    try:
        from .services.rag import RAGService

        embedder_status = RAGService.get_embedder_status()
        total_collections = IntelligenceCollection.objects.count()
        active_collections = IntelligenceCollection.objects.filter(is_active=True).count()
        total_documents = IntelligenceDocument.objects.count()

        collections_info = []
        for col in IntelligenceCollection.objects.filter(is_active=True):
            doc_count = IntelligenceDocument.objects.filter(collection=col).count()
            collections_info.append({
                'id': col.id,
                'name': col.name,
                'table_name': col.table_name,
                'documents': doc_count,
                'min_level': col.min_level,
                'domain': col.domain,
                'is_public': col.is_public,
                'created_at': col.created_at.isoformat() if col.created_at else None,
            })

        return Response({
            'success': True,
            'status': 'operational' if embedder_status.get('loaded') else 'degraded',
            'embedder': embedder_status,
            'collections': {
                'total': total_collections,
                'active': active_collections,
                'list': collections_info
            },
            'documents': {
                'total': total_documents
            },
            'timestamp': timezone.now().isoformat()
        })

    except Exception as e:
        import traceback
        return Response({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc(),
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. ROLE CRUD (Template Views)
# ═══════════════════════════════════════════════════════════════════════════════


@admin_required
def role_list(request):
    """Lista de roles."""
    roles = Role.objects.all().order_by('name')
    return render(request, 'intelligence/roles/list.html', {
        'roles': roles,
        'active_section': 'roles'
    })


@admin_required
def role_create(request):
    """Crear nuevo rol."""
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        default_level = int(request.POST.get('default_level', 1))
        max_level = int(request.POST.get('max_level', 5))
        default_domains_raw = request.POST.get('default_domains', '')
        default_domains = [d.strip() for d in default_domains_raw.split(',') if d.strip()] if default_domains_raw else ['general']

        if name:
            try:
                capabilities = {
                    'memory': request.POST.get('cap_memory') == 'on',
                    'knowledge_base': request.POST.get('cap_knowledge_base') == 'on',
                    'metrics': request.POST.get('cap_metrics') == 'on',
                    'projects': request.POST.get('cap_projects') == 'on',
                }
                role = Role.objects.create(
                    name=name,
                    description=description,
                    default_level=default_level,
                    max_level=max_level,
                    default_domains=default_domains,
                    capabilities=capabilities
                )
                messages.success(request, f'Rol "{role.name}" creado exitosamente.')
                return redirect('role_list')
            except Exception as e:
                messages.error(request, f'Error al crear rol: {str(e)}')
        else:
            messages.error(request, 'El nombre del rol es obligatorio.')

    return render(request, 'intelligence/roles/create.html', {
        'active_section': 'roles'
    })


@admin_required
def role_edit(request, role_id):
    """Editar un rol existente."""
    role = get_object_or_404(Role, id=role_id)

    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        default_level = int(request.POST.get('default_level', 1))
        max_level = int(request.POST.get('max_level', 5))
        default_domains_raw = request.POST.get('default_domains', '')
        default_domains = [d.strip() for d in default_domains_raw.split(',') if d.strip()] if default_domains_raw else ['general']

        if name:
            try:
                role.name = name
                role.description = description
                role.default_level = default_level
                role.max_level = max_level
                role.default_domains = default_domains
                role.capabilities = {
                    'memory': request.POST.get('cap_memory') == 'on',
                    'knowledge_base': request.POST.get('cap_knowledge_base') == 'on',
                    'metrics': request.POST.get('cap_metrics') == 'on',
                    'projects': request.POST.get('cap_projects') == 'on',
                }
                role.save()
                messages.success(request, f'Rol "{role.name}" actualizado exitosamente.')
                return redirect('role_list')
            except Exception as e:
                messages.error(request, f'Error al actualizar rol: {str(e)}')
        else:
            messages.error(request, 'El nombre del rol es obligatorio.')

    return render(request, 'intelligence/roles/edit.html', {
        'role': role,
        'active_section': 'roles'
    })


def role_delete(request, role_id):
    """Eliminar un rol."""
    role = get_object_or_404(Role, id=role_id)
    if request.method == 'POST':
        try:
            role.delete()
            messages.success(request, 'Rol eliminado exitosamente.')
        except Exception as e:
            messages.error(request, f'Error al eliminar rol: {str(e)}')
    return redirect('role_list')


# ═══════════════════════════════════════════════════════════════════════════════
# 4. COLLECTION CRUD (Template Views)
# ═══════════════════════════════════════════════════════════════════════════════


@level_required(2)
def collection_list(request):
    """Lista de colecciones RAG."""
    from .models import DOMAIN_CHOICES
    collections = IntelligenceCollection.objects.all().order_by('-created_at')

    # Filtros desde query params
    current_filters = {}
    name_filter = request.GET.get('name', '').strip()
    status_filter = request.GET.get('status', '').strip()
    level_filter = request.GET.get('level', '').strip()
    domain_filter = request.GET.get('domain', '').strip()

    if name_filter:
        collections = collections.filter(name__icontains=name_filter)
        current_filters['name'] = name_filter
    if status_filter == 'active':
        collections = collections.filter(is_active=True)
        current_filters['status'] = 'active'
    elif status_filter == 'inactive':
        collections = collections.filter(is_active=False)
        current_filters['status'] = 'inactive'
    if level_filter and level_filter.isdigit():
        collections = collections.filter(min_level=int(level_filter))
        current_filters['level'] = level_filter
    if domain_filter:
        collections = collections.filter(domain=domain_filter)
        current_filters['domain'] = domain_filter

    level_choices = IntelligenceCollection._meta.get_field('min_level').choices

    return render(request, 'intelligence/collections/list.html', {
        'collections': collections,
        'current_filters': current_filters,
        'level_choices': level_choices,
        'domain_choices': DOMAIN_CHOICES,
        'active_section': 'collections'
    })


@admin_required
def collection_create(request):
    """Crear nueva colección RAG."""
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        table_name = request.POST.get('table_name', '')
        schema_name = request.POST.get('schema_name', 'dbo')
        database_alias = request.POST.get('database_alias', 'propifai')
        min_level = int(request.POST.get('min_level', 1))
        domain = request.POST.get('domain', 'general')
        is_public = request.POST.get('is_public') == 'on'
        key_field = request.POST.get('key_field', 'id')
        search_fields_raw = request.POST.get('search_fields', '')
        display_fields_raw = request.POST.get('display_fields', '')

        if name and table_name:
            try:
                display_fields = [f.strip() for f in display_fields_raw.split(',') if f.strip()]

                collection = IntelligenceCollection.objects.create(
                    name=name,
                    description=description,
                    table_name=table_name,
                    schema_name=schema_name,
                    database_alias=database_alias,
                    min_level=min_level,
                    domain=domain,
                    is_public=is_public,
                    display_fields=display_fields or ['title', 'price', 'district'],
                    is_active=True
                )
                messages.success(request, f'Colección "{collection.name}" creada exitosamente.')
                return redirect('intelligence:collections_dashboard')
            except Exception as e:
                messages.error(request, f'Error al crear colección: {str(e)}')
        else:
            messages.error(request, 'Nombre y tabla son obligatorios.')

    return render(request, 'intelligence/collections/create.html', {
        'active_section': 'collections'
    })


@admin_required
def collection_edit(request, collection_id):
    """Editar una colección existente."""
    collection = get_object_or_404(IntelligenceCollection, id=collection_id)

    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        table_name = request.POST.get('table_name', '')
        schema_name = request.POST.get('schema_name', 'dbo')
        min_level = int(request.POST.get('min_level', 1))
        domain = request.POST.get('domain', 'general')
        is_public = request.POST.get('is_public') == 'on'
        display_fields_raw = request.POST.get('display_fields', '')

        if name and table_name:
            try:
                collection.name = name
                collection.description = description
                collection.table_name = table_name
                collection.schema_name = schema_name
                collection.min_level = min_level
                collection.domain = domain
                collection.is_public = is_public
                collection.display_fields = [f.strip() for f in display_fields_raw.split(',') if f.strip()]
                collection.save()
                messages.success(request, f'Colección "{collection.name}" actualizada exitosamente.')
                return redirect('intelligence:collections_dashboard')
            except Exception as e:
                messages.error(request, f'Error al actualizar colección: {str(e)}')
        else:
            messages.error(request, 'Nombre y tabla son obligatorios.')

    from .models import DOMAIN_CHOICES
    return render(request, 'intelligence/collections/edit.html', {
        'collection': collection,
        'active_section': 'collections',
        'domain_choices': DOMAIN_CHOICES,
    })


def collection_delete(request, collection_id):
    """Eliminar una colección."""
    collection = get_object_or_404(IntelligenceCollection, id=collection_id)
    if request.method == 'POST':
        try:
            from .services.rag import RAGService
            success, msg = RAGService.delete_collection(collection_id)
            if success:
                messages.success(request, 'Colección eliminada exitosamente.')
            else:
                messages.error(request, f'Error al eliminar colección: {msg}')
        except Exception as e:
            messages.error(request, f'Error al eliminar colección: {str(e)}')
        return redirect('intelligence:collections_dashboard')
    return render(request, 'intelligence/collections/confirm_delete.html', {
        'collection': collection,
        'active_section': 'collections'
    })


def collection_sync(request, collection_id):
    """Sincronizar una colección con su tabla."""
    collection = get_object_or_404(IntelligenceCollection, id=collection_id)
    if request.method == 'POST':
        try:
            from .services.rag import RAGService
            # Detectar tipo de colección: dinámica (con table_name) vs legacy
            if collection.table_name:
                # Colección dinámica → usa sync_collection_dynamic que resuelve FK,
                # escribe en field_values y reconstruye FAISS
                success, message, stats = RAGService.sync_collection_dynamic(
                    collection_name=collection.name,
                    force_full_sync=True,
                )
            else:
                # Colección legacy → usa sync_collection original
                success, message, stats = RAGService.sync_collection(
                    collection_id=collection_id,
                    force_full_sync=True,
                )
            if success:
                # Reconstruir índice FAISS después de sync
                faiss_indexed = 0
                try:
                    from .services.faiss_index import FAISSIndexManager
                    from .services.rag import RAGService
                    faiss_indexed = FAISSIndexManager.rebuild_for_collection(
                        collection.name,
                        RAGService.EMBEDDING_DIMENSIONS
                    )
                except Exception as faiss_err:
                    logger.warning(f"No se pudo reconstruir FAISS: {faiss_err}")
                
                msg = (
                    f'Sync: {stats.get("total_processed", 0)} procesados, '
                    f'{stats.get("created", 0)} creados. '
                )
                if faiss_indexed > 0:
                    msg += f'FAISS: {faiss_indexed} vectores indexados.'
                
                messages.success(request, msg)
            else:
                messages.error(request, f'Error en sincronización: {message}')
        except Exception as e:
            messages.error(request, f'Error al sincronizar: {str(e)}')
    return redirect('intelligence:collections_dashboard')


def collection_sync_api(request, collection_id):
    """
    API endpoint para sincronizar una colección vía JSON.
    POST /api/v1/intelligence/collections/<uuid>/sync/api/
    
    Body (JSON):
        force_full_sync (bool, opcional): Si True, regenera embeddings de todos los docs
        database_alias (str, opcional): Alias de BD para la conexión
    
    Returns:
        JSON con {success, message, stats, collection_id, collection_name}
    """
    from rest_framework.decorators import api_view, permission_classes, authentication_classes
    from rest_framework.permissions import AllowAny
    from rest_framework.response import Response
    from rest_framework import status
    
    @api_view(['POST'])
    @permission_classes([AllowAny])
    @authentication_classes([])
    def _sync_api_view(request, collection_id):
        try:
            collection = get_object_or_404(IntelligenceCollection, id=collection_id)
            from .services.rag import RAGService
            
            force_full = request.data.get('force_full_sync', True)
            database_alias = request.data.get('database_alias')
            
            if collection.table_name:
                success, message, stats = RAGService.sync_collection_dynamic(
                    collection_name=collection.name,
                    force_full_sync=force_full,
                    database_alias=database_alias,
                )
            else:
                success, message, stats = RAGService.sync_collection(
                    collection_id=collection_id,
                    force_full_sync=force_full,
                )
            
            return Response({
                'success': success,
                'message': message,
                'stats': stats,
                'collection_id': str(collection.id),
                'collection_name': collection.name,
            })
        
        except IntelligenceCollection.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Colección no encontrada',
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            import traceback
            return Response({
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc(),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return _sync_api_view(request, collection_id)


def collection_stats(request, collection_id):
    """Estadísticas de una colección."""
    collection = get_object_or_404(IntelligenceCollection, id=collection_id)
    try:
        from .services.rag import RAGService
        stats = RAGService.get_collection_stats(collection_id)
    except Exception as e:
        stats = {'error': str(e)}

    return render(request, 'intelligence/collections/stats.html', {
        'collection': collection,
        'stats': stats,
        'active_section': 'collections'
    })


def collection_detail(request, collection_id):
    """Detalle completo de una colección: campos, embedding_fields, documentos y vector."""
    collection = get_object_or_404(IntelligenceCollection, id=collection_id)
    documents = IntelligenceDocument.objects.filter(collection=collection).order_by('-created_at')[:200]

    # Preparar datos de embedding_fields con info de field_definitions
    raw_field_defs = collection.field_definitions or {}
    # field_definitions puede ser dict ({"campo": {...}}) o lista ([{...}, {...}])
    if isinstance(raw_field_defs, list):
        field_defs = {}
        for item in raw_field_defs:
            if isinstance(item, dict) and 'name' in item:
                field_defs[item['name']] = item
    else:
        field_defs = raw_field_defs
    embedding_info = []
    for field_name in (collection.embedding_fields or []):
        info = field_defs.get(field_name, {})
        embedding_info.append({
            'name': field_name,
            'type': info.get('type', 'unknown'),
            'nullable': info.get('nullable', True),
            'description': info.get('description', ''),
        })

    # Preparar datos de display_fields
    display_info = []
    for field_name in (collection.display_fields or []):
        info = field_defs.get(field_name, {})
        display_info.append({
            'name': field_name,
            'type': info.get('type', 'unknown'),
            'nullable': info.get('nullable', True),
        })

    # Preparar datos de filter_fields
    filter_info = []
    for field_name in (collection.filter_fields or []):
        info = field_defs.get(field_name, {})
        filter_info.append({
            'name': field_name,
            'type': info.get('type', 'unknown'),
            'nullable': info.get('nullable', True),
        })

    # Estadísticas de documentos
    total_docs = IntelligenceDocument.objects.filter(collection=collection).count()
    docs_with_embedding = IntelligenceDocument.objects.filter(
        collection=collection, embedding__isnull=False
    ).count()

    # Recolectar TODOS los nombres de campos únicos de field_values de todos los documentos
    all_field_names = set()
    for doc in documents:
        if doc.field_values:
            all_field_names.update(doc.field_values.keys())
    # Ordenar: poner source_id primero si existe, luego los embedding_fields, luego el resto
    ordered_fields = []
    if 'source_id' in all_field_names:
        ordered_fields.append('source_id')
        all_field_names.discard('source_id')
    for ef in (collection.embedding_fields or []):
        if ef in all_field_names:
            ordered_fields.append(ef)
            all_field_names.discard(ef)
    for df in (collection.display_fields or []):
        if df in all_field_names:
            ordered_fields.append(df)
            all_field_names.discard(df)
    # El resto alfabéticamente
    ordered_fields.extend(sorted(all_field_names))

    # Preparar documentos para el template
    doc_list = []
    for doc in documents:
        embedding_size = len(doc.embedding) if doc.embedding else 0
        doc_list.append({
            'id': str(doc.id),
            'source_id': doc.source_id,
            'content_preview': doc.content[:500] if doc.content else '',
            'content_length': len(doc.content) if doc.content else 0,
            'has_embedding': doc.embedding is not None,
            'embedding_size': embedding_size,
            'field_values': doc.field_values or {},
            'content_hash': doc.content_hash[:16] if doc.content_hash else '',
            'created_at': doc.created_at,
            'updated_at': doc.updated_at,
        })

    # Obtener info del índice FAISS
    faiss_info = None
    try:
        from .services.faiss_index import FAISSIndexManager
        faiss_instance = FAISSIndexManager.get_instance(collection.name)
        if faiss_instance and faiss_instance.is_loaded:
            faiss_info = {
                'indexed': faiss_instance.ntotal,
                'dimension': faiss_instance.dimension,
            }
    except Exception:
        pass

    return render(request, 'intelligence/collections/detail.html', {
        'collection': collection,
        'field_definitions': field_defs,
        'embedding_info': embedding_info,
        'display_info': display_info,
        'filter_info': filter_info,
        'total_docs': total_docs,
        'docs_with_embedding': docs_with_embedding,
        'documents': doc_list,
        'active_section': 'collections',
        'field_names': ordered_fields,
        'faiss_info': faiss_info,
    })


# ═══════════════════════════════════════════════════════════════════════════════
# 5. DASHBOARD / STATS / SIMULATOR
# ═══════════════════════════════════════════════════════════════════════════════


def user_simulator(request):
    """Simulador de usuario para probar el chat."""
    users = User.objects.all().order_by('-created_at')[:20]
    conversations = Conversation.objects.all().order_by('-last_message_at')[:20]

    return render(request, 'intelligence/simulator.html', {
        'users': users,
        'conversations': conversations,
        'active_section': 'simulator'
    })


def intelligence_dashboard(request):
    """Dashboard general de Propifai Intelligence Layer."""
    # Skills stats
    skills = SKILL_SYSTEM.list_available_skills()
    active_skills = sum(1 for s in skills if s.get('is_active', True))
    total_skills = len(skills)

    # Collections stats
    total_collections = IntelligenceCollection.objects.count()
    active_collections = IntelligenceCollection.objects.filter(is_active=True).count()

    # Intent evaluation stats
    total_samples = len(INTENT_EVALUATION_SAMPLES)
    correct_intent = 0
    for sample in INTENT_EVALUATION_SAMPLES:
        predicted = IntentClassifier.classify(sample['question'])
        if predicted.intent == sample['expected_intent']:
            correct_intent += 1
    intent_accuracy = round((correct_intent / total_samples) * 100, 2) if total_samples else 0

    # Skill executions stats
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM intelligence_skill_execution")
        total_executions = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM intelligence_skill_execution WHERE status = 'success'")
        successful_executions = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM intelligence_skill_execution WHERE status = 'error'")
        error_executions = cursor.fetchone()[0]

    # Recent errors
    recent_errors = []
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT TOP 10 id, skill_name, error_message, executed_at "
            "FROM intelligence_skill_execution "
            "WHERE error_message IS NOT NULL AND error_message != '' "
            "ORDER BY executed_at DESC"
        )
        for row in cursor.fetchall():
            recent_errors.append({
                'id': row[0],
                'skill_name': row[1],
                'error_message': row[2],
                'executed_at': row[3]
            })

    # System health
    system_health = {
        'skills_active': active_skills,
        'collections_active': active_collections,
        'intent_accuracy': intent_accuracy,
        'execution_success_rate': round((successful_executions / max(total_executions, 1)) * 100, 2)
    }

    inactive_collections = total_collections - active_collections
    return render(request, 'intelligence/dashboard_general.html', {
        'active_section': 'dashboard',
        'skills': skills,
        'total_skills': total_skills,
        'active_skills': active_skills,
        'total_collections': total_collections,
        'active_collections': active_collections,
        'inactive_collections': inactive_collections,
        'intent_accuracy': intent_accuracy,
        'total_samples': total_samples,
        'total_executions': total_executions,
        'successful_executions': successful_executions,
        'error_executions': error_executions,
        'recent_errors': recent_errors,
        'system_health': system_health,
    })


def intelligence_config(request):
    """Vista de configuraciones del sistema Intelligence."""
    return render(request, 'intelligence/config.html', {
        'active_section': 'config'
    })

def intelligence_errors(request):
    """Vista de errores del sistema Intelligence."""
    errors = []
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, skill_name, status, error_message, executed_at "
            "FROM intelligence_skill_execution "
            "WHERE status = 'error' OR (error_message IS NOT NULL AND error_message != '') "
            "ORDER BY executed_at DESC"
        )
        for row in cursor.fetchall():
            errors.append({
                'id': row[0],
                'modulo': 'Skills',
                'skill_name': row[1],
                'status': row[2],
                'error_message': row[3],
                'executed_at': row[4]
            })

    # También consultar LogEntry del extractor WhatsApp con nivel WARNING/ERROR
    extractor_errors = []
    try:
        from django.db.models import F as models_F
        from whatsapp_extractor.models import LogEntry
        extractor_errors = list(
            LogEntry.objects
            .filter(nivel__in=['WARNING', 'ERROR'])
            .select_related('extractor_log')
            .order_by('-timestamp')[:50]
            .values(
                'id', 'nivel', 'mensaje', 'timestamp',
                extractor_log_id=models_F('extractor_log_id'),
                archivo_nombre=models_F('extractor_log__archivo__nombre_archivo'),
            )
        )
        # Renombrar campos para unificarlos con errors[]
        for ee in extractor_errors:
            ee['modulo'] = 'Extractor WhatsApp'
            ee['skill_name'] = ee.pop('archivo_nombre', '') or f"Log #{ee['extractor_log_id']}"
            ee['status'] = ee.pop('nivel')
            ee['error_message'] = ee.pop('mensaje')
            ee['executed_at'] = ee.pop('timestamp')
            ee['id'] = f"ext_{ee['id']}"
    except Exception:
        pass

    # Combinar y ordenar por fecha descendente
    all_errors = sorted(
        errors + extractor_errors,
        key=lambda x: x.get('executed_at') or '',
        reverse=True
    )[:100]

    return render(request, 'intelligence/errors.html', {
        'active_section': 'errors',
        'errors': all_errors,
    })

def intelligence_tests(request):
    """Vista de tests del sistema Intelligence."""
    return render(request, 'intelligence/tests.html', {
        'active_section': 'tests'
    })


def pil_evaluation(request):
    """
    Vista de evaluación PIL — F5-001.
    """
    import json
    from intelligence.tests.evaluation.runner import load_dataset
    
    dataset = load_dataset()
    
    return render(request, 'intelligence/evaluation.html', {
        'active_section': 'evaluation',
        'total_queries': len(dataset),
        'dataset_json': json.dumps([{
            'id': d['id'],
            'query': d['query'],
            'category': d['category'],
            'expected_skill': d.get('expected_skill'),
        } for d in dataset]),
    })


@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def pil_evaluation_api(request):
    """
    API de evaluación PIL — ejecuta SemanticRouter real y retorna resultados JSON.
    """
    import json
    import time
    from intelligence.tests.evaluation.runner import load_dataset, _get_router
    
    dataset = load_dataset()
    category_filter = request.data.get('category')
    
    if category_filter:
        dataset = [d for d in dataset if d['category'] == category_filter]
    
    results = {
        'total': len(dataset),
        'passed': 0,
        'total_latency_ms': 0.0,
        'errors': 0,
        'by_category': {},
        'details': [],
    }
    
    router = _get_router()
    
    for item in dataset:
        start = time.time()
        router_result = router.classify(item['query'])
        elapsed = (time.time() - start) * 1000
        
        expected = item.get('expected_skill')
        detected = router_result.skill_name if router_result.accepted else None
        
        is_match = False
        if expected is None and not router_result.accepted:
            is_match = True
        elif expected is not None and router_result.accepted and detected == expected:
            is_match = True
        
        if is_match:
            results['passed'] += 1
        
        results['total_latency_ms'] += elapsed
        
        cat = item['category']
        if cat not in results['by_category']:
            results['by_category'][cat] = {'total': 0, 'passed': 0}
        results['by_category'][cat]['total'] += 1
        if is_match:
            results['by_category'][cat]['passed'] += 1
        
        results['details'].append({
            'id': item['id'],
            'query': item['query'],
            'category': cat,
            'expected_skill': expected or 'N/A',
            'detected_skill': detected or 'N/A',
            'score': round(router_result.score, 4),
            'match': is_match,
            'latency_ms': round(elapsed, 1),
        })
    
    accuracy = (results['passed'] / results['total'] * 100) if results['total'] > 0 else 0
    
    return Response({
        'accuracy': round(accuracy, 1),
        'passed': results['passed'],
        'total': results['total'],
        'avg_latency_ms': round(results['total_latency_ms'] / max(results['total'], 1), 0),
        'errors': results['errors'],
        'by_category': {
            cat: {
                'passed': data['passed'],
                'total': data['total'],
                'accuracy': round(data['passed'] / data['total'] * 100, 1) if data['total'] > 0 else 0,
            }
            for cat, data in sorted(results['by_category'].items())
        },
        'details': results['details'],
    })


def intent_evaluation_dashboard(request):
    """Dashboard de evaluación del clasificador de intenciones."""
    evaluation_rows = []
    total_samples = len(INTENT_EVALUATION_SAMPLES)
    correct_intent = 0
    correct_skill = 0
    total_skill_checks = 0

    for sample in INTENT_EVALUATION_SAMPLES:
        question = sample['question']
        expected_intent = sample['expected_intent']
        expected_skill = sample.get('expected_skill')
        expected_description = sample.get('expected_description', '')

        predicted = IntentClassifier.classify(question)
        predicted_skill = ChatProcessor._find_skill_candidate(question)
        predicted_skill_name = predicted_skill.get('name') if predicted_skill else None

        intent_match = predicted.intent == expected_intent
        if intent_match:
            correct_intent += 1

        skill_match = None
        if expected_skill is not None:
            total_skill_checks += 1
            skill_match = predicted_skill_name == expected_skill
            if skill_match:
                correct_skill += 1

        evaluation_rows.append({
            'question': question,
            'expected_intent': expected_intent.value,
            'predicted_intent': predicted.intent.value,
            'intent_confidence': round(predicted.confidence, 2),
            'intent_match': intent_match,
            'expected_skill': expected_skill or 'N/A',
            'predicted_skill': predicted_skill_name or 'N/A',
            'skill_match': 'Sí' if skill_match else 'No' if expected_skill is not None else 'N/A',
            'expected_description': expected_description,
        })

    intent_accuracy = round((correct_intent / total_samples) * 100, 2) if total_samples else 0.0
    skill_accuracy = round((correct_skill / total_skill_checks) * 100, 2) if total_skill_checks else None

    return render(request, 'intelligence/intent_evaluation.html', {
        'evaluation_rows': evaluation_rows,
        'total_samples': total_samples,
        'correct_intent': correct_intent,
        'intent_accuracy': intent_accuracy,
        'total_skill_checks': total_skill_checks,
        'correct_skill': correct_skill,
        'skill_accuracy': skill_accuracy,
        'active_section': 'intent_evaluation',
    })


def system_stats(request):
    """Estadísticas detalladas del sistema."""
    total_users = User.objects.count()
    users_by_role = Role.objects.annotate(
        user_count=Count('user')
    ).values('name', 'user_count')

    total_conversations = Conversation.objects.count()
    conversations_with_memory = Conversation.objects.filter(
        metadata__has_key='memory_context'
    ).count()

    total_facts = Fact.objects.count()
    facts_by_category = Fact.objects.values('category').annotate(
        count=Count('id')
    ).order_by('-count')

    total_episodes = EpisodicMemory.objects.count()
    episodes_by_type = EpisodicMemory.objects.values('episode_type').annotate(
        count=Count('id')
    ).order_by('-count')

    total_collections = IntelligenceCollection.objects.count()
    collections_with_docs = IntelligenceCollection.objects.annotate(
        doc_count=Count('documents')
    ).values('name', 'doc_count')

    return render(request, 'intelligence/stats.html', {
        'total_users': total_users,
        'users_by_role': users_by_role,
        'total_conversations': total_conversations,
        'conversations_with_memory': conversations_with_memory,
        'total_facts': total_facts,
        'facts_by_category': facts_by_category,
        'total_episodes': total_episodes,
        'episodes_by_type': episodes_by_type,
        'total_collections': total_collections,
        'collections_with_docs': collections_with_docs,
        'active_section': 'stats'
    })


def activity_logs(request):
    """Registro de actividad del sistema."""
    episodes = EpisodicMemory.objects.all().order_by('-created_at')[:100]

    # Estadísticas de actividad
    total_episodes = EpisodicMemory.objects.count()
    episodes_today = EpisodicMemory.objects.filter(
        created_at__date=timezone.now().date()
    ).count()

    # Actividad por hora (últimas 24h)
    from django.db.models import Count
    from django.db.models.functions import TruncHour
    last_24h = timezone.now() - timezone.timedelta(hours=24)
    hourly_activity = EpisodicMemory.objects.filter(
        created_at__gte=last_24h
    ).annotate(
        hour=TruncHour('created_at')
    ).values('hour').annotate(
        count=Count('id')
    ).order_by('hour')

    # Tipos de episodios
    episodes_by_type = EpisodicMemory.objects.values('episode_type').annotate(
        count=Count('id')
    ).order_by('-count')

    # Intenciones detectadas
    intents_detected = EpisodicMemory.objects.values('intent_detected').annotate(
        count=Count('id')
    ).order_by('-count')

    # Feedback recibido
    feedback_count = EpisodicMemory.objects.exclude(
        feedback__isnull=True
    ).exclude(feedback='').count()

    return render(request, 'intelligence/activity_logs.html', {
        'episodes': episodes,
        'total_episodes': total_episodes,
        'episodes_today': episodes_today,
        'hourly_activity': hourly_activity,
        'episodes_by_type': episodes_by_type,
        'intents_detected': intents_detected,
        'feedback_count': feedback_count,
        'active_section': 'activity'
    })


# ═══════════════════════════════════════════════════════════════════════════════
# 6. RAG DISCOVERY & DYNAMIC (API)
# ═══════════════════════════════════════════════════════════════════════════════


@api_view(['GET'])
@permission_classes([AllowAny])
@authentication_classes([])
def rag_discovery_tables(request):
    """Descubre tablas disponibles en la base de datos para RAG."""
    try:
        from .services.rag import RAGService
        # Leer database_alias del query param, default 'propifai' para consistencia con el frontend
        database_alias = request.GET.get('database', 'propifai')
        force_refresh = request.GET.get('nocache', '').lower() in ('true', '1', 'yes')
        tables = RAGService.get_available_tables(database_alias=database_alias, force_refresh=force_refresh)
        return Response({
            'success': True,
            'tables': tables,
            'count': len(tables),
            'timestamp': timezone.now().isoformat()
        })
    except Exception as e:
        import traceback
        return Response({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc(),
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
@authentication_classes([])
def rag_discovery_table_schema(request, table_name):
    """Obtiene el esquema de una tabla específica."""
    try:
        from .services.rag import RAGService
        # Leer database_alias del query param, default 'propifai' para consistencia con el frontend
        database_alias = request.GET.get('database', 'propifai')
        schema_name = request.GET.get('schema', None)
        analysis = RAGService.analyze_table_schema(table_name, schema=schema_name, database_alias=database_alias)
        return Response({
            'success': True,
            'table_name': table_name,
            'analysis': analysis,
            'timestamp': timezone.now().isoformat()
        })
    except Exception as e:
        import traceback
        return Response({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc(),
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
@authentication_classes([])
def rag_discovery_foreign_keys(request, table_name):
    """Detecta foreign keys de una tabla."""
    try:
        from .services.rag import RAGService
        database_alias = request.GET.get('database', 'propifai')
        schema_name = request.GET.get('schema', None)
        
        foreign_keys = RAGService.detect_foreign_keys(table_name, schema=schema_name, database_alias=database_alias)
        
        return Response({
            'success': True,
            'table': table_name,
            'schema': schema_name or 'dbo',
            'database': database_alias,
            'foreign_keys': foreign_keys,
            'count': len(foreign_keys),
            'timestamp': timezone.now().isoformat()
        })
    except Exception as e:
        import traceback
        return Response({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc(),
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
@authentication_classes([])
def rag_discovery_table_preview(request, table_name):
    """Obtiene una vista previa de los datos de una tabla."""
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT TOP 10 * FROM {table_name}")
            columns = [col[0] for col in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

        return Response({
            'success': True,
            'table_name': table_name,
            'columns': columns,
            'rows': rows,
            'row_count': len(rows),
            'timestamp': timezone.now().isoformat()
        })
    except Exception as e:
        import traceback
        return Response({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc(),
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def rag_create_collection_dynamic(request):
    """Crea una colección RAG dinámicamente desde una tabla existente."""
    try:
        import json
        
        # Soporte dual: JSON body o FormData (request.POST)
        if request.content_type and 'application/json' in request.content_type:
            data = json.loads(request.body) if isinstance(request.body, bytes) else request.data
        else:
            # FormData: parsear campos JSON stringificados
            data = {}
            for key in request.POST:
                data[key] = request.POST.get(key)
            # Parsear campos JSON
            for json_field in ['embedding_fields', 'display_fields', 'filter_fields',
                               'field_definitions', 'table_relationships']:
                if json_field in data and isinstance(data[json_field], str):
                    try:
                        data[json_field] = json.loads(data[json_field])
                    except (json.JSONDecodeError, TypeError):
                        pass

        collection_name = data.get('collection_name') or data.get('name', '')
        table_name = data.get('table_name', '')
        schema_name = data.get('schema_name', 'dbo')
        description = data.get('description', '')
        min_level = int(data.get('min_level', 1))
        domain = data.get('domain', 'general')
        is_public = str(data.get('is_public', 'false')) == 'true' or data.get('is_public') == 'on'
        key_field = data.get('key_field', 'id')
        search_fields = data.get('search_fields') or data.get('embedding_fields', ['title', 'description'])
        display_fields = data.get('display_fields', ['title', 'price', 'district'])
        filter_fields = data.get('filter_fields', [])
        field_definitions = data.get('field_definitions', [])
        table_relationships = data.get('table_relationships', [])
        is_active = str(data.get('is_active', 'on')) == 'on'
        database_alias = data.get('database_alias', 'propifai')  # Default a propifai para el frontend

        if not collection_name or not table_name:
            return Response({
                'success': False,
                'error': 'collection_name y table_name son requeridos'
            }, status=status.HTTP_400_BAD_REQUEST)

        from .services.rag import RAGService
        result = RAGService.create_collection_dynamic(
            name=collection_name,
            table_name=table_name,
            schema=schema_name,
            description=description,
            min_level=min_level,
            domain=domain,
            is_public=is_public,
            key_field=key_field,
            embedding_fields=search_fields,
            display_fields=display_fields,
            filter_fields=filter_fields,
            field_definitions=field_definitions,
            table_relationships=table_relationships,
            is_active=is_active,
            database_alias=database_alias,
        )

        success, message, collection = result

        response_data = {
            'success': success,
            'message': message,
            'timestamp': timezone.now().isoformat()
        }

        if collection:
            response_data['collection'] = {
                'id': str(collection.id),
                'name': collection.name,
                'table_name': collection.table_name,
                'description': collection.description,
                'embedding_fields': collection.embedding_fields,
                'display_fields': collection.display_fields,
                'filter_fields': collection.filter_fields,
                'is_active': collection.is_active,
                'created_at': collection.created_at.isoformat() if collection.created_at else None,
            }

        status_code = status.HTTP_200_OK if success else status.HTTP_400_BAD_REQUEST
        return Response(response_data, status=status_code)

    except Exception as e:
        import traceback
        return Response({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc(),
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def rag_search_dynamic(request):
    """Busca en colecciones RAG dinámicamente."""
    try:
        import json
        data = json.loads(request.body) if isinstance(request.body, bytes) else request.data

        query = data.get('query', '')
        collection_names = data.get('collection_names', [])
        top_k = data.get('top_k', 5)

        if not query:
            return Response({
                'success': False,
                'error': 'Se requiere un query'
            }, status=status.HTTP_400_BAD_REQUEST)

        from .services.rag import RAGService
        results = RAGService.search_dynamic(
            query=query,
            collection_names=collection_names,
            top_k=top_k
        )

        return Response({
            'success': True,
            'query': query,
            'collections_searched': collection_names,
            'results_count': len(results),
            'results': results,
            'timestamp': timezone.now().isoformat()
        })

    except Exception as e:
        import traceback
        return Response({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc(),
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def rag_ingest_pdf(request, collection_name):
    """
    Ingiere un archivo PDF en una colección RAG.
    
    Recibe multipart/form-data con un archivo PDF y metadatos opcionales.
    El PDF se chunkifica (400 palabras, 50 overlap), se generan embeddings
    (modo passage) y se almacena en IntelligenceDocument.
    
    Args:
        request: HttpRequest con archivo PDF en request.FILES['file']
        collection_name: Nombre de la colección destino (path parameter)
        
    Returns:
        JSON con resultado de la ingesta
    """
    try:
        import json
        
        # Validar que se envió un archivo
        if 'file' not in request.FILES:
            return Response({
                'success': False,
                'error': 'No se envió ningún archivo. Usa el campo "file" en multipart/form-data.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        pdf_file = request.FILES['file']
        
        # Validar extensión
        if not pdf_file.name.lower().endswith('.pdf'):
            return Response({
                'success': False,
                'error': f'El archivo "{pdf_file.name}" no es un PDF. Extensión esperada: .pdf'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validar tamaño (máximo 50MB)
        max_size = 50 * 1024 * 1024  # 50MB
        if pdf_file.size > max_size:
            return Response({
                'success': False,
                'error': f'El archivo es demasiado grande ({pdf_file.size / 1024 / 1024:.1f}MB). Máximo: 50MB'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Guardar archivo temporal
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            for chunk in pdf_file.chunks():
                tmp_file.write(chunk)
            tmp_path = tmp_file.name
        
        try:
            # Parsear metadatos opcionales
            metadata = {}
            if request.POST.get('metadata'):
                try:
                    metadata = json.loads(request.POST['metadata'])
                except (json.JSONDecodeError, TypeError):
                    metadata = {'raw': request.POST.get('metadata')}
            
            # Agregar metadatos del archivo
            metadata['nombre_original'] = pdf_file.name
            metadata['tamano_bytes'] = pdf_file.size
            metadata['tipo_mime'] = pdf_file.content_type or 'application/pdf'
            
            # Ingerir PDF
            from .services.pdf_ingestion import PDFIngestionService
            
            success, message, stats = PDFIngestionService.ingest_pdf(
                pdf_path=tmp_path,
                collection_name=collection_name,
                metadata=metadata
            )
            
            if success:
                return Response({
                    'success': True,
                    'message': message,
                    'collection_name': collection_name,
                    'file_name': pdf_file.name,
                    'stats': stats,
                    'timestamp': timezone.now().isoformat()
                })
            else:
                return Response({
                    'success': False,
                    'error': message,
                    'collection_name': collection_name,
                    'file_name': pdf_file.name,
                    'stats': stats,
                    'timestamp': timezone.now().isoformat()
                }, status=status.HTTP_400_BAD_REQUEST)
        
        finally:
            # Limpiar archivo temporal
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
    
    except Exception as e:
        import traceback
        return Response({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc(),
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ═══════════════════════════════════════════════════════════════════════════════
# 7. CHAT WEB (Template View)
# ═══════════════════════════════════════════════════════════════════════════════


def chat_web(request):
    """
    Vista principal del chat web interactivo (SPEC-007).
    Renderiza el template del chat con contexto inicial.
    """
    user = getattr(request, 'current_user', None)

    # Obtener o crear usuario anónimo si no está autenticado
    if not user:
        session_key = request.session.session_key
        if not session_key:
            request.session.save()
            session_key = request.session.session_key

        user = User.objects.filter(
            metadata__session_key=session_key
        ).first()

        if not user:
            default_role = Role.objects.filter(default_level=1).first()
            if not default_role:
                default_role = Role.objects.create(
                    name='Usuario Básico',
                    default_level=1,
                    max_level=1,
                    default_domains=['general'],
                    capabilities={'memory': True, 'knowledge_base': False, 'metrics': False, 'projects': False},
                    description='Rol por defecto para usuarios nuevos'
                )

            anon_id = uuid.uuid4().hex[:10]
            user = User.objects.create(
                role=default_role,
                username=f'anon_{anon_id}',
                phone=f'anon_{anon_id}',
                is_active=True,
                metadata={'session_key': session_key, 'name': 'Visitante'}
            )

    # Obtener conversaciones del usuario
    conversations = Conversation.objects.filter(
        user=user
    ).order_by('-last_message_at')[:20]

    # Obtener colecciones disponibles para el nivel del usuario
    user_level = 1
    try:
        profile = UserIntelligenceProfile.objects.get(user=user)
        user_level = profile.level
    except UserIntelligenceProfile.DoesNotExist:
        if user.role:
            user_level = user.role.default_level

    available_collections = IntelligenceCollection.objects.filter(
        min_level__lte=user_level,
        is_active=True
    )

    # Estadísticas del usuario
    total_conversations = Conversation.objects.filter(user=user).count()
    total_messages = sum(
        len(c.messages) for c in Conversation.objects.filter(user=user)
    )

    return render(request, 'intelligence/chat.html', {
        'user': user,
        'user_id': str(user.id),
        'user_name': user.first_name or user.username or 'Usuario',
        'user_level': user_level,
        'conversations': conversations,
        'available_collections': available_collections,
        'total_conversations': total_conversations,
        'total_messages': total_messages,
        'active_section': 'chat'
    })


# ═══════════════════════════════════════════════════════════════════════════════
# 8. CHAT WEB API (refactorizada -> ChatProcessor)
# ═══════════════════════════════════════════════════════════════════════════════


@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def chat_web_api(request):
    """
    API para el chat web interactivo (SPEC-007).
    Refactorizada: delega toda la lógica de negocio a ChatProcessor.
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

        # Obtener o crear conversación
        conversation = ChatProcessor._get_or_create_conversation(
            user=user,
            app_id='chat-web',
            conversation_id=conversation_id,
        )

        # Construir contexto y delegar a ChatProcessor
        ctx = ChatContext(
            user=user,
            message=message,
            conversation=conversation,
            use_memory=use_memory,
            use_rag=use_rag,
            collections=collections,
            app_id='chat-web',
            skill_name=data.get('skill_name'),
            skill_params=data.get('skill_params', {}) or {},
            flow_name=data.get('flow_name'),
            flow_params=data.get('flow_params', {}) or {},
        )

        result = ChatProcessor.process_message(ctx)

        if not result.success:
            return Response({
                'success': False,
                'error': result.error,
                'traceback': result.metadata.get('traceback', ''),
                'timestamp': result.timestamp
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Detectar si la respuesta contiene HTML generado (formatear_propiedades)
        response_text = result.response_text or ''
        html_content = None
        if response_text.startswith('__HTML__') and response_text.endswith('__HTML__'):
            html_content = response_text[8:-8]  # Quitar marcadores
            response_text = ''  # El HTML se envía aparte

        return Response({
            'success': True,
            'conversation_id': result.conversation_id,
            'message_id': result.message_id,
            'response': response_text,
            'html': html_content,
            'metadata': result.metadata,
            'context_summary': result.context_summary,
            'timestamp': result.timestamp
        })

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


@level_required(2)
def conversation_flows_page(request):
    """Página de administración de los flujos de conversación."""
    flows = ConversationFlow.objects.all().order_by('name')
    return render(request, 'intelligence/conversation_flows.html', {
        'flows': flows,
        'active_section': 'chat_flows',
    })


@level_required(2)
def conversation_flow_create(request):
    """Crear un nuevo flujo de conversación desde la interfaz web."""
    errors = []
    form_data = {
        'name': '',
        'description': '',
        'initial_state': 'start',
        'is_active': True,
        'states': json.dumps({
            'start': {
                'message': '¡Hola! ¿En qué puedo ayudarte?',
                'buttons': [
                    {'text': 'Comprar', 'next_state': 'buy_flow'},
                    {'text': 'Vender', 'next_state': 'sell_flow'}
                ]
            }
        }, indent=2, ensure_ascii=False),
    }

    if request.method == 'POST':
        form_data['name'] = request.POST.get('name', '').strip()
        form_data['description'] = request.POST.get('description', '').strip()
        form_data['initial_state'] = request.POST.get('initial_state', 'start').strip()
        form_data['is_active'] = request.POST.get('is_active') == 'on'
        form_data['states'] = request.POST.get('states', '').strip()

        if not form_data['name']:
            errors.append('El nombre del flujo es obligatorio.')

        if not form_data['states']:
            errors.append('Los estados del flujo son obligatorios.')
        else:
            try:
                states = json.loads(form_data['states'])
            except json.JSONDecodeError as exc:
                errors.append(f'El JSON de estados no es válido: {str(exc)}')
                states = None

        if not errors:
            if ConversationFlow.objects.filter(name=form_data['name']).exists():
                errors.append('Ya existe un flujo con ese nombre.')
            else:
                ConversationFlow.objects.create(
                    name=form_data['name'],
                    description=form_data['description'],
                    initial_state=form_data['initial_state'] or 'start',
                    is_active=form_data['is_active'],
                    states=states or {},
                )
                messages.success(request, 'Flujo creado correctamente.')
                return redirect('intelligence:conversation_flows_page')

    return render(request, 'intelligence/conversation_flow_form.html', {
        'form_action': 'create',
        'form_data': form_data,
        'errors': errors,
    })


@level_required(2)
def conversation_flow_edit(request, flow_id):
    """Editar un flujo de conversación desde la interfaz web."""
    flow = get_object_or_404(ConversationFlow, id=flow_id)
    errors = []
    form_data = {
        'name': flow.name,
        'description': flow.description,
        'initial_state': flow.initial_state,
        'is_active': flow.is_active,
        'states': json.dumps(flow.states, indent=2, ensure_ascii=False),
    }

    if request.method == 'POST':
        form_data['name'] = request.POST.get('name', '').strip()
        form_data['description'] = request.POST.get('description', '').strip()
        form_data['initial_state'] = request.POST.get('initial_state', 'start').strip()
        form_data['is_active'] = request.POST.get('is_active') == 'on'
        form_data['states'] = request.POST.get('states', '').strip()

        if not form_data['name']:
            errors.append('El nombre del flujo es obligatorio.')

        if not form_data['states']:
            errors.append('Los estados del flujo son obligatorios.')
        else:
            try:
                states = json.loads(form_data['states'])
            except json.JSONDecodeError as exc:
                errors.append(f'El JSON de estados no es válido: {str(exc)}')
                states = None

        if not errors:
            duplicate = ConversationFlow.objects.filter(name=form_data['name']).exclude(id=flow.id).exists()
            if duplicate:
                errors.append('Ya existe otro flujo con ese nombre.')
            else:
                flow.name = form_data['name']
                flow.description = form_data['description']
                flow.initial_state = form_data['initial_state'] or 'start'
                flow.is_active = form_data['is_active']
                flow.states = states or {}
                flow.save()
                messages.success(request, 'Flujo actualizado correctamente.')
                return redirect('intelligence:conversation_flows_page')

    return render(request, 'intelligence/conversation_flow_form.html', {
        'form_action': 'edit',
        'flow': flow,
        'form_data': form_data,
        'errors': errors,
    })


@api_view(['GET'])
@permission_classes([AllowAny])
@authentication_classes([])
def conversation_flows_list(request):
    """Listado de flujos de conversación disponibles."""
    flows = ConversationFlow.objects.all().order_by('name')
    serializer = ConversationFlowSerializer(flows, many=True)
    return Response({
        'success': True,
        'flows': serializer.data,
        'timestamp': timezone.now().isoformat(),
    })


@api_view(['GET'])
@permission_classes([AllowAny])
@authentication_classes([])
def conversation_flow_detail(request, flow_id):
    """Detalle de un flujo de conversación."""
    flow = get_object_or_404(ConversationFlow, id=flow_id)
    serializer = ConversationFlowSerializer(flow)
    return Response({
        'success': True,
        'flow': serializer.data,
        'timestamp': timezone.now().isoformat(),
    })


@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def conversation_flow_toggle(request, flow_id):
    """Activa o desactiva un flujo de conversación."""
    flow = get_object_or_404(ConversationFlow, id=flow_id)
    flow.is_active = not flow.is_active
    flow.save(update_fields=['is_active'])
    return Response({
        'success': True,
        'flow_id': str(flow.id),
        'is_active': flow.is_active,
        'timestamp': timezone.now().isoformat(),
    })


# ═══════════════════════════════════════════════════════════════════════════════
# 9. CHAT WEB STREAM (refactorizada -> ChatProcessor)
# ═══════════════════════════════════════════════════════════════════════════════


@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def chat_web_stream(request):
    """
    API para streaming de respuestas en el chat web (SPEC-007).
    Refactorizada: delega toda la lógica de negocio a ChatProcessor.process_message_stream().
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

        # Obtener o crear conversación
        conversation = ChatProcessor._get_or_create_conversation(
            user=user,
            app_id='chat-web-stream',
            conversation_id=conversation_id,
            streaming=True,
        )

        # Construir contexto
        ctx = ChatContext(
            user=user,
            message=message,
            conversation=conversation,
            use_memory=use_memory,
            use_rag=use_rag,
            collections=collections,
            app_id='chat-web-stream',
            streaming=True,
            max_tokens=800,
            temperature=0.7,
            skill_name=data.get('skill_name'),
            skill_params=data.get('skill_params', {}) or {},
            flow_name=data.get('flow_name'),
            flow_params=data.get('flow_params', {}) or {},
        )

        def stream_generator():
            for chunk in ChatProcessor.process_message_stream(ctx):
                if chunk.type == 'metadata':
                    yield json.dumps({
                        'type': 'metadata',
                        'conversation_id': chunk.data.get('conversation_id', ''),
                        'context_summary': chunk.data.get('context_summary', {}),
                    }) + '\n'

                elif chunk.type == 'chunk':
                    yield json.dumps({
                        'type': 'chunk',
                        'content': chunk.data.get('content', ''),
                    }) + '\n'

                elif chunk.type == 'complete':
                    yield json.dumps({
                        'type': 'complete',
                        'message_id': chunk.data.get('message_id', ''),
                        'full_response': chunk.data.get('full_response', ''),
                        'timestamp': chunk.data.get('timestamp', timezone.now().isoformat()),
                    }) + '\n'

                elif chunk.type == 'error':
                    yield json.dumps({
                        'type': 'error',
                        'error': chunk.data.get('error', 'Error desconocido'),
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


@api_view(['GET'])
@permission_classes([AllowAny])
@authentication_classes([])
def skills_list(request):
    """Lista las skills disponibles en el sistema."""
    skills = SKILL_SYSTEM.list_available_skills()
    return Response({
        'success': True,
        'skills': skills,
    })


@api_view(['GET'])
@permission_classes([AllowAny])
@authentication_classes([])
def skill_info(request, skill_name):
    """Obtiene metadata detallada de una skill."""
    info = SKILL_SYSTEM.get_skill_info(skill_name)
    if not info:
        return Response({
            'success': False,
            'error': f"Skill '{skill_name}' no encontrada"
        }, status=status.HTTP_404_NOT_FOUND)
    return Response({
        'success': True,
        'skill': info,
    })


@api_view(['GET'])
@permission_classes([AllowAny])
@authentication_classes([])
def skill_metrics(request):
    """Retorna métricas resumidas del motor de skills."""
    metrics = SKILL_SYSTEM.get_metrics_summary()
    return Response({
        'success': True,
        'metrics': metrics,
    })


@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def skill_execute(request):
    """Ejecuta una skill directamente a través del motor de skills."""
    try:
        serializer = SkillExecuteRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'error': 'Datos inválidos',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        user_id = data.get('user_id')
        skill_name = data.get('skill_name')
        parameters = data.get('parameters', {}) or {}
        conversation_id = data.get('conversation_id')

        user = getattr(request, 'current_user', None)
        if not user and user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                user = None

        if not user:
            return Response({
                'success': False,
                'error': 'Usuario no autenticado. Debes iniciar sesión para ejecutar skills.'
            }, status=status.HTTP_401_UNAUTHORIZED)

        conversation = ChatProcessor._get_or_create_conversation(
            user=user,
            app_id='skills',
            conversation_id=conversation_id,
        )

        ctx = ChatContext(
            user=user,
            message=skill_name,
            conversation=conversation,
            use_memory=False,
            use_rag=False,
            app_id='skills',
            skill_name=skill_name,
            skill_params=parameters,
        )

        result = ChatProcessor.process_message(ctx)
        if not result.success:
            return Response({
                'success': False,
                'error': result.error,
                'metadata': result.metadata,
                'timestamp': result.timestamp,
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            'success': True,
            'conversation_id': result.conversation_id,
            'message_id': result.message_id,
            'response': result.response_text,
            'metadata': result.metadata,
            'timestamp': result.timestamp,
        })

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Error en skill_execute: {str(e)}\n{error_details}")
        return Response({
            'success': False,
            'error': str(e),
            'traceback': error_details,
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ═══════════════════════════════════════════════════════════════════════════════
# 10. CHAT WEB UPLOAD
# ═══════════════════════════════════════════════════════════════════════


@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def chat_web_upload(request):
    """
    API para subir archivos en el chat web.
    """
    try:
        user = getattr(request, 'current_user', None)
        if not user:
            return Response({
                'success': False,
                'error': 'Usuario no autenticado'
            }, status=status.HTTP_401_UNAUTHORIZED)

        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response({
                'success': False,
                'error': 'No se proporcionó ningún archivo'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Validar tipo de archivo
        allowed_types = [
            'image/jpeg', 'image/png', 'image/gif', 'image/webp',
            'application/pdf',
            'text/plain', 'text/csv',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.ms-excel',
        ]
        if uploaded_file.content_type not in allowed_types:
            return Response({
                'success': False,
                'error': f'Tipo de archivo no soportado: {uploaded_file.content_type}'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Validar tamaño (máximo 10MB)
        max_size = 10 * 1024 * 1024
        if uploaded_file.size > max_size:
            return Response({
                'success': False,
                'error': f'El archivo excede el tamaño máximo de 10MB'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Guardar archivo temporalmente
        import tempfile
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=os.path.splitext(uploaded_file.name)[1]
        ) as tmp_file:
            for chunk in uploaded_file.chunks():
                tmp_file.write(chunk)
            tmp_path = tmp_file.name

        try:
            # Procesar según tipo
            result = {'filename': uploaded_file.name, 'size': uploaded_file.size}

            if uploaded_file.content_type.startswith('image/'):
                # Imagen: extraer texto con OCR si es posible
                result['type'] = 'image'
                result['message'] = f"Imagen recibida: {uploaded_file.name}"
            elif uploaded_file.content_type == 'application/pdf':
                result['type'] = 'pdf'
                result['message'] = f"PDF recibido: {uploaded_file.name}"
            else:
                # Texto: leer contenido
                with open(tmp_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                result['type'] = 'text'
                result['content'] = content[:1000]  # Limitar a 1000 caracteres
                result['message'] = f"Archivo procesado: {uploaded_file.name}"

            return Response({
                'success': True,
                'data': result,
                'timestamp': timezone.now().isoformat()
            })

        finally:
            # Limpiar archivo temporal
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    except Exception as e:
        import traceback
        logger.error(f"Error en chat_web_upload: {str(e)}\n{traceback.format_exc()}")
        return Response({
            'success': False,
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ═══════════════════════════════════════════════════════════════════════════════
# 11. EPISODIC MEMORY (API)
# ═══════════════════════════════════════════════════════════════════════════════


@api_view(['GET'])
@permission_classes([AllowAny])
@authentication_classes([])
def episodic_memory_list(request):
    """
    Lista episodios de memoria episódica.
    """
    try:
        user = getattr(request, 'current_user', None)
        if not user:
            return Response({
                'success': False,
                'error': 'Usuario no autenticado'
            }, status=status.HTTP_401_UNAUTHORIZED)

        limit = int(request.GET.get('limit', 20))
        episode_type = request.GET.get('type', '')

        episodes = EpisodicMemory.objects.filter(user_id=str(user.id))
        if episode_type:
            episodes = episodes.filter(episode_type=episode_type)
        episodes = episodes.order_by('-created_at')[:limit]

        data = []
        for ep in episodes:
            data.append({
                'id': str(ep.id),
                'episode_type': ep.episode_type,
                'intent_detected': ep.intent_detected,
                'user_message_preview': ep.user_message[:100] if ep.user_message else '',
                'importance_score': ep.importance_score,
                'latency_ms': ep.latency_ms,
                'feedback': ep.feedback,
                'created_at': ep.created_at.isoformat() if ep.created_at else None,
            })

        return Response({
            'success': True,
            'episodes': data,
            'count': len(data),
            'timestamp': timezone.now().isoformat()
        })

    except Exception as e:
        import traceback
        return Response({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc(),
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
@authentication_classes([])
def episodic_memory_detail(request, episode_id):
    """
    Detalle de un episodio de memoria episódica.
    """
    try:
        episode = get_object_or_404(EpisodicMemory, id=episode_id)

        data = {
            'id': str(episode.id),
            'user_id': episode.user_id,
            'conversation_id': episode.conversation_id,
            'episode_type': episode.episode_type,
            'intent_detected': episode.intent_detected,
            'user_message': episode.user_message,
            'assistant_response': episode.assistant_response,
            'rag_context_used': episode.rag_context_used,
            'memory_context_used': episode.memory_context_used,
            'context': episode.context,
            'importance_score': episode.importance_score,
            'latency_ms': episode.latency_ms,
            'feedback': episode.feedback,
            'created_at': episode.created_at.isoformat() if episode.created_at else None,
        }

        return Response({
            'success': True,
            'episode': data,
            'timestamp': timezone.now().isoformat()
        })

    except Exception as e:
        import traceback
        return Response({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc(),
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def episodic_memory_feedback(request, episode_id):
    """
    Actualiza el feedback de un episodio.
    """
    try:
        episode = get_object_or_404(EpisodicMemory, id=episode_id)
        data = json.loads(request.body) if isinstance(request.body, bytes) else request.data

        feedback = data.get('feedback', '')
        if feedback not in ['positive', 'negative', 'neutral']:
            return Response({
                'success': False,
                'error': 'Feedback debe ser: positive, negative o neutral'
            }, status=status.HTTP_400_BAD_REQUEST)

        EpisodicMemoryService.update_feedback(
            episode_id=str(episode.id),
            feedback=feedback
        )

        return Response({
            'success': True,
            'message': 'Feedback actualizado exitosamente',
            'timestamp': timezone.now().isoformat()
        })

    except Exception as e:
        import traceback
        return Response({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc(),
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
@authentication_classes([])
def episodic_memory_stats(request):
    """
    Estadísticas de memoria episódica.
    """
    try:
        total_episodes = EpisodicMemory.objects.count()
        episodes_with_feedback = EpisodicMemory.objects.exclude(
            feedback__isnull=True
        ).exclude(feedback='').count()

        # Distribución por tipo
        by_type = EpisodicMemory.objects.values('episode_type').annotate(
            count=Count('id')
        ).order_by('-count')

        # Distribución por intención
        by_intent = EpisodicMemory.objects.values('intent_detected').annotate(
            count=Count('id')
        ).order_by('-count')

        # Importancia promedio
        avg_importance = EpisodicMemory.objects.aggregate(
            avg=Avg('importance_score')
        )['avg'] or 0

        # Latencia promedio
        avg_latency = EpisodicMemory.objects.aggregate(
            avg=Avg('latency_ms')
        )['avg'] or 0

        return Response({
            'success': True,
            'stats': {
                'total_episodes': total_episodes,
                'episodes_with_feedback': episodes_with_feedback,
                'avg_importance': round(avg_importance, 2),
                'avg_latency_ms': round(avg_latency, 2),
                'by_type': list(by_type),
                'by_intent': list(by_intent),
            },
            'timestamp': timezone.now().isoformat()
        })

    except Exception as e:
        import traceback
        return Response({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc(),
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ═══════════════════════════════════════════════════════════════════════════════
# 12. AUTH (register, login, logout)
# ═══════════════════════════════════════════════════════════════════════════════


def register_view(request):
    """Vista de registro de usuarios."""
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')

        field_errors = {}

        # Validaciones
        if not username:
            field_errors['username'] = 'El nombre de usuario es obligatorio.'
        elif User.objects.filter(phone=username).exists():
            field_errors['username'] = 'El nombre de usuario ya está registrado.'

        if not password:
            field_errors['password'] = 'La contraseña es obligatoria.'
        elif len(password) < 6:
            field_errors['password'] = 'La contraseña debe tener al menos 6 caracteres.'

        if password != confirm_password:
            field_errors['confirm_password'] = 'Las contraseñas no coinciden.'

        if not field_errors:
            try:
                from .authentication import register_user
                user = register_user(
                    username=username,
                    password=password,
                    email=email if email else None,
                    phone=phone if phone else None,
                )
                if user:
                    from .authentication import login_user
                    login_user(request, user)
                    messages.success(request, f'Bienvenido, {username}!')
                    return redirect('chat_web')
                else:
                    field_errors['username'] = 'Error al crear el usuario.'
            except Exception as e:
                field_errors['username'] = f'Error: {str(e)}'

        return render(request, 'intelligence/register.html', {
            'field_errors': field_errors,
            'values': {
                'username': username,
                'email': email,
                'phone': phone,
            }
        })

    return render(request, 'intelligence/register.html', {
        'field_errors': {},
        'values': {}
    })


def login_view(request):
    """Vista de inicio de sesión."""
    if request.method == 'POST':
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        next_url = request.POST.get('next', '/intelligence/chat/')

        from .authentication import authenticate_user, login_user
        user = authenticate_user(username=username, password=password)

        if user:
            login_user(request, user)
            messages.success(request, f'Bienvenido de nuevo, {username}!')
            return redirect(next_url)
        else:
            messages.error(request, 'Usuario o contraseña incorrectos.')
            # Redirigir de vuelta al dashboard de skills con el error
            return redirect(next_url)

    # GET: si el usuario ya está autenticado, redirigir al next
    # Si no, redirigir al dashboard de skills (que tiene el modal de login)
    # NOTA: /intelligence/skills/dashboard/ está en PUBLIC_PATHS del middleware
    next_url = request.GET.get('next', '/intelligence/chat/')
    user = getattr(request, 'current_user', None)
    if user:
        return redirect(next_url)
    return redirect('/intelligence/skills/dashboard/')


def logout_view(request):
    """Vista de cierre de sesión."""
    from django.contrib.auth import logout
    logout(request)
    # Limpiar sesión de intelligence
    if hasattr(request, 'session'):
        request.session.flush()
    # Redirigir al dashboard de skills
    next_url = request.GET.get('next', '/api/v1/intelligence/skills/dashboard/')
    return redirect(next_url)


# ═══════════════════════════════════════════════════════════════════════════════
# 13. USER CRUD (Template Views)
# ═══════════════════════════════════════════════════════════════════════════════


def user_list(request):
    """Lista de usuarios del sistema."""
    users = User.objects.all().order_by('-created_at')
    return render(request, 'intelligence/users/list.html', {
        'users': users,
        'active_section': 'users'
    })


@admin_required
def user_create(request):
    """Crear nuevo usuario."""
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password', '')
        role_id = request.POST.get('role')

        if username and password:
            try:
                role = Role.objects.get(id=role_id) if role_id else None
                if not role:
                    role = Role.objects.filter(default_level=1).first()

                user = User.objects.create(
                    phone=username,
                    email=email if email else None,
                    role=role,
                    is_active=True,
                    metadata={'name': username}
                )
                user.set_password(password)
                user.save()

                messages.success(request, f'Usuario "{username}" creado exitosamente.')
                return redirect('user_list')
            except Exception as e:
                messages.error(request, f'Error al crear usuario: {str(e)}')
        else:
            messages.error(request, 'Usuario y contraseña son obligatorios.')

    roles = Role.objects.all()
    return render(request, 'intelligence/users/create.html', {
        'roles': roles,
        'active_section': 'users'
    })


@admin_required
def user_edit(request, user_id):
    """Editar un usuario existente."""
    user = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        role_id = request.POST.get('role')
        password = request.POST.get('password', '')

        if username:
            try:
                user.phone = username
                user.email = email if email else None
                if role_id:
                    user.role = Role.objects.get(id=role_id)
                if password:
                    user.set_password(password)
                user.save()

                messages.success(request, f'Usuario "{username}" actualizado exitosamente.')
                return redirect('user_list')
            except Exception as e:
                messages.error(request, f'Error al actualizar usuario: {str(e)}')
        else:
            messages.error(request, 'El nombre de usuario es obligatorio.')

    roles = Role.objects.all()
    return render(request, 'intelligence/users/edit.html', {
        'user': user,
        'roles': roles,
        'active_section': 'users'
    })


@admin_required
def user_toggle_active(request, user_id):
    """Activar/desactivar un usuario."""
    user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        user.is_active = not user.is_active
        user.save()
        status_text = 'activado' if user.is_active else 'desactivado'
        messages.success(request, f'Usuario "{user.phone}" {status_text} exitosamente.')
        return redirect('user_list')


# ═══════════════════════════════════════════════════════════════════════════════
# 14. SKILLS DASHBOARD (SPEC-011)
# ═══════════════════════════════════════════════════════════════════════════════


# @level_required(1)  # TEMPORALMENTE DESHABILITADO PARA PROBAR GRÁFICOS
def skills_dashboard_view(request):
    """Dashboard principal de skills con KPIs, tabla y charts.
    
    TODOS los datos provienen de fuentes reales:
    - Skills registradas: SKILL_SYSTEM.list_available_skills()
    - Ejecuciones, latencia, éxito: SkillExecution (BD) via raw SQL
    - Cache hit rate: calculado desde SkillExecution.cached
    """
    # Autenticación real vía sesión
    from .authentication import get_authenticated_user
    user = get_authenticated_user(request)
    if user is None:
        # No hay sesión activa — mostrar dashboard público sin datos sensibles
        user = None
    from django.utils import timezone
    from datetime import timedelta
    import datetime
    
    # ── Redescubrir skills (para detectar skills nuevas sin reiniciar) ────
    try:
        from .skills.registry import SkillRegistry as DynamicRegistry
        DynamicRegistry().discover_skills("intelligence.skills")
    except Exception:
        pass
    
    # ── Skills del sistema ────────────────────────────────────────────────
    skills = SKILL_SYSTEM.list_available_skills()
    active_count = sum(1 for s in skills if s.get('is_active', True))
    
    # ── Stats globales desde BD (raw SQL para compatibilidad SQL Server) ──
    last_24h = timezone.now() - timedelta(hours=24)
    
    with connection.cursor() as cursor:
        # Total ejecuciones
        cursor.execute("SELECT COUNT(*) FROM intelligence_skill_execution")
        total_all = cursor.fetchone()[0]
        
        # Últimas 24h
        cursor.execute(
            "SELECT COUNT(*) FROM intelligence_skill_execution WHERE executed_at >= %s",
            [last_24h]
        )
        total_today = cursor.fetchone()[0]
        
        # Por status
        cursor.execute("SELECT COUNT(*) FROM intelligence_skill_execution WHERE status = 'success'")
        total_success = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM intelligence_skill_execution WHERE status = 'error'")
        total_error = cursor.fetchone()[0]
        
        # Cacheadas
        cursor.execute("SELECT COUNT(*) FROM intelligence_skill_execution WHERE cached = 1")
        total_cached = cursor.fetchone()[0]
        
        # Latencia promedio (solo exitosas)
        cursor.execute(
            "SELECT AVG(latency_ms) FROM intelligence_skill_execution WHERE status = 'success'"
        )
        avg_latency = cursor.fetchone()[0] or 0
    
    # Cache hit rate real desde BD
    cache_hit_rate = round((total_cached / max(total_all, 1)) * 100, 1)
    
    # Tasa de éxito real desde BD
    success_rate = round((total_success / max(total_all, 1)) * 100, 1)
    
    # ── Ejecuciones por skill (para la tabla) ────────────────────────────
    skill_exec_counts = {}
    skill_latency_avg = {}
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT skill_name, COUNT(*) as cnt "
            "FROM intelligence_skill_execution GROUP BY skill_name"
        )
        for row in cursor.fetchall():
            skill_exec_counts[row[0]] = row[1]
        
        cursor.execute(
            "SELECT skill_name, AVG(latency_ms) as avg_lat "
            "FROM intelligence_skill_execution WHERE status = 'success' "
            "GROUP BY skill_name"
        )
        for row in cursor.fetchall():
            skill_latency_avg[row[0]] = row[1]
    
    # Enriquecer skills con datos reales de BD
    for s in skills:
        name = s.get('name', '')
        s['execution_count'] = skill_exec_counts.get(name, 0)
        avg_lat = skill_latency_avg.get(name)
        s['avg_latency'] = round(avg_lat, 1) if avg_lat else None
    
    # ── Ejecuciones por hora (últimas 24h con labels reales) ─────────────
    executions_by_hour = []
    counts_by_hour = []
    now = timezone.now()
    with connection.cursor() as cursor:
        for i in range(24):
            hour_start = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=23 - i)
            hour_end = hour_start + timedelta(hours=1)
            cursor.execute(
                "SELECT COUNT(*) FROM intelligence_skill_execution "
                "WHERE executed_at >= %s AND executed_at < %s",
                [hour_start, hour_end]
            )
            count = cursor.fetchone()[0]
            # Convertir a hora local para el label
            local_hour_start = timezone.localtime(hour_start)
            label = local_hour_start.strftime('%H:00')
            executions_by_hour.append({'label': label, 'count': count})
            counts_by_hour.append(count)
    max_hour_count = max(counts_by_hour) if counts_by_hour else 0
    # Usar escala fija baja para que barras pequeñas se vean grandes
    scale_max = 5  # Máximo visual de 5 ejecuciones para la escala
    for entry in executions_by_hour:
        raw_pct = (entry['count'] / scale_max) * 100 if scale_max else 0
        entry['height_pct'] = min(100, round(raw_pct))  # Capear a 100%
        if entry['count'] > 0 and entry['height_pct'] < 30:
            entry['display_height_pct'] = 30
        else:
            entry['display_height_pct'] = entry['height_pct']

    # ── Ejecuciones recientes ─────────────────────────────────────────────
    recent_executions = []
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT TOP 20 id, skill_name, status, latency_ms, cached, error_message, executed_at "
            "FROM intelligence_skill_execution ORDER BY executed_at DESC"
        )
        columns = ['id', 'skill_name', 'status', 'latency_ms', 'cached', 'error_message', 'executed_at']
        for row in cursor.fetchall():
            exec_dict = dict(zip(columns, row))
            # Convertir UTC a America/Lima para el template
            if exec_dict.get('executed_at') and timezone.is_naive(exec_dict['executed_at']):
                exec_dict['executed_at'] = timezone.make_aware(exec_dict['executed_at'], datetime.timezone.utc)
            if exec_dict.get('executed_at'):
                exec_dict['executed_at'] = timezone.localtime(exec_dict['executed_at'])
            recent_executions.append(exec_dict)
    
    # ── Métricas resumidas para el template ───────────────────────────────
    metrics = {
        'total_executions': total_all,
        'successful_executions': total_success,
        'failed_executions': total_error,
        'cached_executions': total_cached,
        'success_rate': success_rate,
        'average_execution_time': round(avg_latency, 1),
    }
    
    # Ajustar escalado del gráfico de barras para preservar la distribución y garantizar visibilidad
    scale_max = max(5, max_hour_count)
    for entry in executions_by_hour:
        raw_pct = (entry['count'] / scale_max) * 100 if scale_max else 0
        entry['height_pct'] = min(100, round(raw_pct))
        entry['display_height_pct'] = max(entry['height_pct'], 25) if entry['count'] > 0 else 2

    context = {
        'active_section': 'skills',
        'skills': skills,
        'metrics': metrics,
        'recent_executions': recent_executions,
        'active_count': active_count,
        'total_today': total_today,
        'cache_hit_rate': cache_hit_rate,
        'avg_latency': round(avg_latency, 1),
        'executions_by_hour': executions_by_hour,
        'user': user,
        # Variables adicionales para el template rediseñado
        'total_execs': total_all,
        'success_rate': success_rate,
        'error_rate': round(100 - success_rate, 1),
        'error_count': total_error,
        'success_count': total_success,
        'today_count': total_today,
        'cached_count': total_cached,
        'nocache_pct': round(100 - cache_hit_rate, 1),
    }
    return render(request, 'intelligence/skills_dashboard.html', context)


@level_required(2)
def skill_detail_view(request, skill_name):
    """Detalle de una skill con info, métricas, panel de ejecución e historial.
    
    TODOS los datos provienen de SkillExecution (BD) via raw SQL
    para compatibilidad con SQL Server (ODBC Driver 18 modo estricto).
    """
    user = getattr(request, 'current_user', None)
    from django.db import connection
    from django.utils import timezone
    import datetime
    
    # Obtener info de la skill
    info = SKILL_SYSTEM.get_skill_info(skill_name)
    if not info:
        messages.error(request, f"Skill '{skill_name}' no encontrada")
        return redirect('intelligence:skills_dashboard')
    
    # ── Métricas específicas de la skill desde BD (raw SQL) ────────────────
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM intelligence_skill_execution WHERE skill_name = %s",
            [skill_name]
        )
        total_execs = cursor.fetchone()[0]
        
        cursor.execute(
            "SELECT COUNT(*) FROM intelligence_skill_execution "
            "WHERE skill_name = %s AND status = 'success'",
            [skill_name]
        )
        success_count = cursor.fetchone()[0]
        
        cursor.execute(
            "SELECT AVG(latency_ms) FROM intelligence_skill_execution "
            "WHERE skill_name = %s AND status = 'success'",
            [skill_name]
        )
        avg_latency = cursor.fetchone()[0] or 0
        
        cursor.execute(
            "SELECT COUNT(*) FROM intelligence_skill_execution "
            "WHERE skill_name = %s AND cached = 1",
            [skill_name]
        )
        cache_count = cursor.fetchone()[0]
    
    success_rate = round((success_count / max(total_execs, 1)) * 100, 1) if total_execs > 0 else 0
    cache_rate = round((cache_count / max(total_execs, 1)) * 100, 1) if total_execs > 0 else 0
    
    # ── Ejecuciones recientes de esta skill (raw SQL) ──────────────────────
    executions = []
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT TOP 50 id, skill_name, status, latency_ms, cached, "
            "error_message, executed_at, user_id "
            "FROM intelligence_skill_execution "
            "WHERE skill_name = %s "
            "ORDER BY executed_at DESC",
            [skill_name]
        )
        columns = ['id', 'skill_name', 'status', 'latency_ms', 'cached',
                   'error_message', 'executed_at', 'user_id']
        for row in cursor.fetchall():
            exec_dict = dict(zip(columns, row))
            # Convertir UTC a America/Lima para el template
            if exec_dict.get('executed_at') and timezone.is_naive(exec_dict['executed_at']):
                exec_dict['executed_at'] = timezone.make_aware(exec_dict['executed_at'], datetime.timezone.utc)
            if exec_dict.get('executed_at'):
                exec_dict['executed_at'] = timezone.localtime(exec_dict['executed_at'])
            # Obtener nombre de usuario
            uid = exec_dict.pop('user_id', None)
            exec_dict['user_name'] = 'Sistema'
            if uid:
                try:
                    u = User.objects.get(id=uid)
                    exec_dict['user_name'] = u.name or u.username or str(u.id)[:8]
                except Exception:
                    exec_dict['user_name'] = 'Sistema'
            executions.append(exec_dict)
    
    context = {
        'active_section': 'skills_dashboard',
        'skill': info,
        'executions': executions,
        'total_execs': total_execs,
        'success_rate': success_rate,
        'avg_latency': round(avg_latency, 1),
        'cache_rate': cache_rate,
        'user': user,
    }
    return render(request, 'intelligence/skills_detail.html', context)


@level_required(4)
def skill_create_view(request):
    """Formulario para crear una nueva skill."""
    user = getattr(request, 'current_user', None)
    
    if request.method == 'POST':
        skill_name = request.POST.get('skill_name', '').strip()
        description = request.POST.get('description', '').strip()
        category = request.POST.get('category', 'query')
        required_level = int(request.POST.get('required_level', 1))
        code_content = request.POST.get('code_content', '').strip()
        parameters_json = request.POST.get('parameters', '[]')
        
        if not skill_name or not code_content:
            messages.error(request, 'Nombre y código son obligatorios.')
            return render(request, 'intelligence/skills_create.html', {
                'active_section': 'skills_dashboard',
                'user': user,
                'error': 'Nombre y código son obligatorios.',
            })
        
        try:
            # Validar que el nombre sea válido como nombre de archivo
            import re
            if not re.match(r'^[a-z_][a-z0-9_]*$', skill_name):
                raise ValueError(
                    'El nombre debe empezar con minúscula o underscore y '
                    'contener solo minúsculas, números y underscores.'
                )
            
            # Validar sintaxis del código Python
            try:
                compile(code_content, f'{skill_name}.py', 'exec')
            except SyntaxError as e:
                messages.error(request, f'Error de sintaxis en el código: {e}')
                return render(request, 'intelligence/skills_create.html', {
                    'active_section': 'skills_dashboard',
                    'user': user,
                    'error': f'Error de sintaxis: {e}',
                    'form_data': request.POST,
                })
            
            # Guardar el archivo de la skill
            import os
            skills_dir = os.path.join(os.path.dirname(__file__), 'skills')
            filepath = os.path.join(skills_dir, f'{skill_name}.py')
            
            if os.path.exists(filepath):
                messages.error(request, f'Ya existe una skill con nombre "{skill_name}"')
                return render(request, 'intelligence/skills_create.html', {
                    'active_section': 'skills_dashboard',
                    'user': user,
                    'error': f'La skill "{skill_name}" ya existe.',
                    'form_data': request.POST,
                })
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(code_content)
            
            # Intentar registrar la skill
            try:
                from .skills.registry import SkillRegistry as DynamicRegistry
                count = DynamicRegistry().discover_skills_from_directory(skills_dir)
                messages.success(
                    request,
                    f'Skill "{skill_name}" creada exitosamente. '
                    f'Total skills registradas: {count}'
                )
            except Exception as e:
                messages.warning(
                    request,
                    f'Archivo creado pero no se pudo registrar automáticamente: {e}'
                )
            
            return redirect('intelligence:skills_dashboard')
            
        except ValueError as e:
            messages.error(request, str(e))
            return render(request, 'intelligence/skills_create.html', {
                'active_section': 'skills_dashboard',
                'user': user,
                'error': str(e),
                'form_data': request.POST,
            })
        except Exception as e:
            messages.error(request, f'Error al crear skill: {str(e)}')
            return render(request, 'intelligence/skills_create.html', {
                'active_section': 'skills_dashboard',
                'user': user,
                'error': str(e),
                'form_data': request.POST,
            })
    
    # GET: mostrar formulario vacío
    context = {
        'active_section': 'skills_dashboard',
        'user': user,
    }
    return render(request, 'intelligence/skills_create.html', context)


@level_required(4)
def skill_edit_view(request, skill_name):
    """Editar una skill existente."""
    user = getattr(request, 'current_user', None)
    
    import os
    skills_dir = os.path.join(os.path.dirname(__file__), 'skills')
    filepath = os.path.join(skills_dir, f'{skill_name}.py')
    
    if not os.path.exists(filepath):
        messages.error(request, f'Skill "{skill_name}" no encontrada')
        return redirect('intelligence:skills_dashboard')
    
    if request.method == 'POST':
        code_content = request.POST.get('code_content', '').strip()
        
        if not code_content:
            messages.error(request, 'El código no puede estar vacío.')
            return render(request, 'intelligence/skills_create.html', {
                'active_section': 'skills_dashboard',
                'user': user,
                'skill_name': skill_name,
                'is_edit': True,
            })
        
        try:
            compile(code_content, f'{skill_name}.py', 'exec')
        except SyntaxError as e:
            messages.error(request, f'Error de sintaxis: {e}')
            return render(request, 'intelligence/skills_create.html', {
                'active_section': 'skills_dashboard',
                'user': user,
                'skill_name': skill_name,
                'is_edit': True,
                'error': str(e),
                'code_content': code_content,
            })
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(code_content)
        
        # Recargar skill
        try:
            from .skills.registry import SkillRegistry as DynamicRegistry
            DynamicRegistry().reload_skill(skill_name)
        except Exception:
            pass
        
        messages.success(request, f'Skill "{skill_name}" actualizada exitosamente.')
        return redirect('intelligence:skill_detail', skill_name=skill_name)
    
    # GET: leer archivo actual
    with open(filepath, 'r', encoding='utf-8') as f:
        code_content = f.read()
    
    info = SKILL_SYSTEM.get_skill_info(skill_name) or {}
    
    context = {
        'active_section': 'skills_dashboard',
        'user': user,
        'skill_name': skill_name,
        'skill_info': info,
        'code_content': code_content,
        'is_edit': True,
    }
    return render(request, 'intelligence/skills_create.html', context)


@level_required(3)
def skill_metrics_view(request):
    """Página de métricas globales con charts.
    
    Usa raw SQL para compatibilidad con SQL Server (ODBC Driver 18 modo estricto).
    """
    user = getattr(request, 'current_user', None)
    from django.db import connection
    from django.utils import timezone
    from datetime import timedelta
    
    metrics = SKILL_SYSTEM.get_metrics_summary()
    skills = SKILL_SYSTEM.list_available_skills()
    
    last_7_days = timezone.now() - timedelta(days=7)
    
    # ── Stats globales desde BD (raw SQL) ─────────────────────────────────
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM intelligence_skill_execution")
        total_execs = cursor.fetchone()[0]
        
        cursor.execute(
            "SELECT COUNT(*) FROM intelligence_skill_execution WHERE status = 'success'"
        )
        success_count = cursor.fetchone()[0]
        
        cursor.execute(
            "SELECT COUNT(*) FROM intelligence_skill_execution WHERE status = 'error'"
        )
        error_count = cursor.fetchone()[0]
        
        cursor.execute(
            "SELECT AVG(latency_ms) FROM intelligence_skill_execution WHERE status = 'success'"
        )
        avg_latency = cursor.fetchone()[0] or 0
    
    success_rate = round((success_count / max(total_execs, 1)) * 100, 1) if total_execs > 0 else 0
    
    # ── Ejecuciones por skill ─────────────────────────────────────────────
    execs_by_skill = {}
    latency_by_skill = {}
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT skill_name, COUNT(*) as cnt "
            "FROM intelligence_skill_execution GROUP BY skill_name"
        )
        for row in cursor.fetchall():
            execs_by_skill[row[0]] = row[1]
        
        cursor.execute(
            "SELECT skill_name, AVG(latency_ms) as avg_lat "
            "FROM intelligence_skill_execution WHERE status = 'success' "
            "GROUP BY skill_name"
        )
        for row in cursor.fetchall():
            latency_by_skill[row[0]] = round(row[1], 1) if row[1] else 0
    
    # ── Timeline 7 días ───────────────────────────────────────────────────
    timeline = {}
    with connection.cursor() as cursor:
        for i in range(7):
            day = timezone.now() - timedelta(days=6-i)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            cursor.execute(
                "SELECT COUNT(*) FROM intelligence_skill_execution "
                "WHERE executed_at >= %s AND executed_at < %s",
                [day_start, day_end]
            )
            count = cursor.fetchone()[0]
            timeline[day.strftime('%Y-%m-%d')] = count
    
    # ── Success rate por categoría ────────────────────────────────────────
    success_by_category = {}
    categories = set(s.get('category', 'general') for s in skills)
    for cat in categories:
        cat_skills = [s.get('name') for s in skills if s.get('category', 'general') == cat]
        if not cat_skills:
            continue
        with connection.cursor() as cursor:
            placeholders = ','.join(['%s'] * len(cat_skills))
            cursor.execute(
                f"SELECT COUNT(*) FROM intelligence_skill_execution "
                f"WHERE skill_name IN ({placeholders})",
                cat_skills
            )
            total_cat = cursor.fetchone()[0]
            
            cursor.execute(
                f"SELECT COUNT(*) FROM intelligence_skill_execution "
                f"WHERE skill_name IN ({placeholders}) AND status = 'success'",
                cat_skills
            )
            success_cat = cursor.fetchone()[0]
        
        if total_cat > 0:
            success_by_category[cat] = round((success_cat / total_cat * 100), 1)
    
    context = {
        'active_section': 'skills_dashboard',
        'user': user,
        'metrics': metrics,
        'skills': skills,
        'total_execs': total_execs,
        'success_rate': success_rate,
        'avg_latency': round(avg_latency, 1),
        'error_count': error_count,
        'execs_by_skill': execs_by_skill,
        'latency_by_skill': latency_by_skill,
        'timeline': timeline,
        'success_by_category': success_by_category,
    }
    return render(request, 'intelligence/skills_metrics.html', context)


@level_required(3)
def skill_logs_view(request):
    """Página de logs de ejecución con filtros.
    
    Usa raw SQL para compatibilidad con SQL Server (ODBC Driver 18 modo estricto).
    """
    user = getattr(request, 'current_user', None)
    from django.db import connection
    from django.utils import timezone
    import datetime
    
    # Filtros
    skill_filter = request.GET.get('skill', '')
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('q', '')
    
    # Paginación
    page = int(request.GET.get('page', 1))
    page_size = 50
    
    # Construir WHERE dinámico
    where_clauses = []
    params = []
    
    if skill_filter:
        where_clauses.append("skill_name = %s")
        params.append(skill_filter)
    if status_filter:
        where_clauses.append("status = %s")
        params.append(status_filter)
    if search_query:
        where_clauses.append(
            "(skill_name LIKE %s OR error_message LIKE %s OR parameters LIKE %s)"
        )
        like = f"%{search_query}%"
        params.extend([like, like, like])
    
    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)
    
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT COUNT(*) FROM intelligence_skill_execution {where_sql}",
            params
        )
        total = cursor.fetchone()[0]
    
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    offset = (page - 1) * page_size
    
    executions = []
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT TOP {page_size} id, skill_name, status, latency_ms, cached, "
            f"error_message, executed_at "
            f"FROM intelligence_skill_execution {where_sql} "
            f"ORDER BY executed_at DESC",
            params
        )
        columns = ['id', 'skill_name', 'status', 'latency_ms', 'cached',
                   'error_message', 'executed_at']
        for row in cursor.fetchall():
            exec_dict = dict(zip(columns, row))
            # Convertir UTC a America/Lima para el template
            if exec_dict.get('executed_at') and timezone.is_naive(exec_dict['executed_at']):
                exec_dict['executed_at'] = timezone.make_aware(exec_dict['executed_at'], datetime.timezone.utc)
            if exec_dict.get('executed_at'):
                exec_dict['executed_at'] = timezone.localtime(exec_dict['executed_at'])
            executions.append(exec_dict)
    
    # Lista de skills para el filtro
    skills = SKILL_SYSTEM.list_available_skills()
    skill_names = [s.get('name', '') for s in skills]
    
    context = {
        'active_section': 'skills_dashboard',
        'user': user,
        'executions': executions,
        'skill_names': skill_names,
        'current_skill': skill_filter,
        'current_status': status_filter,
        'current_query': search_query,
        'page': page,
        'total_pages': total_pages,
        'total': total,
        'page_size': page_size,
    }
    return render(request, 'intelligence/skills_logs.html', context)


@api_view(['GET'])
@level_required(3)
def skill_logs_api(request):
    """API JSON de logs para DataTables.
    
    Usa raw SQL para compatibilidad con SQL Server (ODBC Driver 18 modo estricto).
    """
    from django.db import connection
    from django.utils import timezone
    import datetime
    
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 50))
    skill_filter = request.GET.get('skill', '')
    status_filter = request.GET.get('status', '')
    
    # Construir WHERE dinámico
    where_clauses = []
    params = []
    
    if skill_filter:
        where_clauses.append("skill_name = %s")
        params.append(skill_filter)
    if status_filter:
        where_clauses.append("status = %s")
        params.append(status_filter)
    
    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)
    
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT COUNT(*) FROM intelligence_skill_execution {where_sql}",
            params
        )
        total = cursor.fetchone()[0]
    
    offset = (page - 1) * page_size
    
    executions = []
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT id, skill_name, status, latency_ms, cached, "
            f"error_message, executed_at "
            f"FROM intelligence_skill_execution {where_sql} "
            f"ORDER BY executed_at DESC "
            f"OFFSET {offset} ROWS FETCH NEXT {page_size} ROWS ONLY",
            params
        )
        columns = ['id', 'skill_name', 'status', 'latency_ms', 'cached',
                   'error_message', 'executed_at']
        for row in cursor.fetchall():
            exec_dict = dict(zip(columns, row))
            # Convertir UTC a America/Lima para el template
            if exec_dict.get('executed_at') and timezone.is_naive(exec_dict['executed_at']):
                exec_dict['executed_at'] = timezone.make_aware(exec_dict['executed_at'], datetime.timezone.utc)
            if exec_dict.get('executed_at'):
                exec_dict['executed_at'] = timezone.localtime(exec_dict['executed_at'])
            executions.append(exec_dict)
    
    return Response({
        'count': total,
        'page': page,
        'page_size': page_size,
        'results': executions,
    })


@level_required(4)
def skill_clear_cache(request, skill_name):
    """Limpia el cache de una skill específica."""
    if request.method == 'POST':
        try:
            if hasattr(SKILL_SYSTEM, 'invalidate_cache'):
                count = SKILL_SYSTEM.invalidate_cache(skill_name=skill_name)
                messages.success(
                    request,
                    f'Cache limpiado para "{skill_name}". {count} entradas eliminadas.'
                )
            else:
                messages.warning(request, 'El sistema de cache no está disponible.')
        except Exception as e:
            messages.error(request, f'Error al limpiar cache: {str(e)}')
    return redirect('intelligence:skill_detail', skill_name=skill_name)


@admin_required
def skill_toggle_active(request, skill_name):
    """Activar/desactivar una skill (solo admin)."""
    if request.method == 'POST':
        try:
            registry = SKILL_SYSTEM.registry if hasattr(SKILL_SYSTEM, 'registry') else None
            if registry and hasattr(registry, 'unregister_skill'):
                info = SKILL_SYSTEM.get_skill_info(skill_name)
                if info and info.get('is_active', True):
                    registry.unregister_skill(skill_name)
                    messages.success(request, f'Skill "{skill_name}" desactivada.')
                else:
                    registry.reload_skill(skill_name)
                    messages.success(request, f'Skill "{skill_name}" activada.')
            else:
                messages.warning(request, 'No se puede cambiar el estado de la skill.')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    return redirect('intelligence:skills_dashboard')


@api_view(['GET'])
@level_required(1)
def skill_stats_api(request):
    """API JSON con stats agregados para los charts del dashboard.
    
    TODOS los datos provienen de SkillExecution (BD) via raw SQL
    para compatibilidad con SQL Server (ODBC Driver 18 modo estricto).
    """
    from django.utils import timezone
    from datetime import timedelta
    from django.db import connection
    
    last_24h = timezone.now() - timedelta(hours=24)
    last_7d = timezone.now() - timedelta(days=7)
    
    skills = SKILL_SYSTEM.list_available_skills()
    
    # ── Stats globales desde BD (raw SQL) ─────────────────────────────────
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM intelligence_skill_execution")
        total_all = cursor.fetchone()[0]
        
        cursor.execute(
            "SELECT COUNT(*) FROM intelligence_skill_execution WHERE status = 'success'"
        )
        total_success = cursor.fetchone()[0]
        
        cursor.execute(
            "SELECT COUNT(*) FROM intelligence_skill_execution WHERE status = 'error'"
        )
        total_error = cursor.fetchone()[0]
        
        cursor.execute(
            "SELECT COUNT(*) FROM intelligence_skill_execution WHERE cached = 1"
        )
        total_cached = cursor.fetchone()[0]
        
        cursor.execute(
            "SELECT AVG(latency_ms) FROM intelligence_skill_execution WHERE status = 'success'"
        )
        avg_latency = cursor.fetchone()[0] or 0
        
        cursor.execute(
            "SELECT COUNT(*) FROM intelligence_skill_execution WHERE executed_at >= %s",
            [last_24h]
        )
        total_today = cursor.fetchone()[0]
        
        cursor.execute(
            "SELECT COUNT(*) FROM intelligence_skill_execution WHERE executed_at >= %s",
            [last_7d]
        )
        total_7d = cursor.fetchone()[0]
    
    success_rate = round((total_success / max(total_all, 1)) * 100, 1)
    cache_hit_rate = round((total_cached / max(total_all, 1)) * 100, 1)
    
    # ── Ejecuciones por hora (últimas 24h con labels reales) ─────────────
    executions_by_hour = {}
    now = timezone.now()
    with connection.cursor() as cursor:
        for i in range(24):
            hour_start = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=23 - i)
            hour_end = hour_start + timedelta(hours=1)
            cursor.execute(
                "SELECT COUNT(*) FROM intelligence_skill_execution "
                "WHERE executed_at >= %s AND executed_at < %s",
                [hour_start, hour_end]
            )
            count = cursor.fetchone()[0]
            label = hour_start.strftime('%H:00')
            executions_by_hour[label] = count
    
    # ── Ejecuciones por skill ─────────────────────────────────────────────
    execs_by_skill = {}
    latency_by_skill = {}
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT skill_name, COUNT(*) as cnt "
            "FROM intelligence_skill_execution GROUP BY skill_name"
        )
        for row in cursor.fetchall():
            execs_by_skill[row[0]] = row[1]
        
        cursor.execute(
            "SELECT skill_name, AVG(latency_ms) as avg_lat "
            "FROM intelligence_skill_execution WHERE status = 'success' "
            "GROUP BY skill_name"
        )
        for row in cursor.fetchall():
            latency_by_skill[row[0]] = round(row[1], 1) if row[1] else 0
    
    # ── Success rate por categoría ────────────────────────────────────────
    success_by_category = {}
    categories = set(s.get('category', 'general') for s in skills)
    for cat in categories:
        cat_skills = [s.get('name') for s in skills if s.get('category', 'general') == cat]
        if not cat_skills:
            continue
        with connection.cursor() as cursor:
            placeholders = ','.join(['%s'] * len(cat_skills))
            cursor.execute(
                f"SELECT COUNT(*) FROM intelligence_skill_execution "
                f"WHERE skill_name IN ({placeholders})",
                cat_skills
            )
            total_cat = cursor.fetchone()[0]
            
            cursor.execute(
                f"SELECT COUNT(*) FROM intelligence_skill_execution "
                f"WHERE skill_name IN ({placeholders}) AND status = 'success'",
                cat_skills
            )
            success_cat = cursor.fetchone()[0]
        
        if total_cat > 0:
            success_by_category[cat] = round((success_cat / total_cat * 100), 1)
    
    return Response({
        'skills_count': len(skills),
        'active_count': sum(1 for s in skills if s.get('is_active', True)),
        'total_executions_today': total_today,
        'total_executions_all': total_all,
        'total_executions_7d': total_7d,
        'total_success': total_success,
        'total_error': total_error,
        'total_cached': total_cached,
        'avg_latency_ms': round(avg_latency, 1),
        'success_rate': success_rate,
        'cache_hit_rate': cache_hit_rate,
        'executions_by_hour': executions_by_hour,
        'executions_by_skill': execs_by_skill,
        'latency_by_skill': latency_by_skill,
        'success_rate_by_category': success_by_category,
    })


@level_required(1)
def skill_execution_detail_view(request, execution_id):
    """Detalle completo de una ejecución individual de skill.
    
    Muestra los parámetros de entrada (question/prompt), el resultado
    (respuesta del sistema), error message, latencia, cache, timestamp y usuario.
    """
    from django.utils import timezone
    import datetime
    from django.db import connection
    import json
    
    user = getattr(request, 'current_user', None)
    skills = SKILL_SYSTEM.list_available_skills()
    skill_map = {s.get('name'): s for s in skills}
    
    execution = None
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, skill_name, status, latency_ms, cached, "
            "error_message, executed_at, parameters, result, user_id "
            "FROM intelligence_skill_execution WHERE id = %s",
            [str(execution_id)]
        )
        row = cursor.fetchone()
        if row:
            columns = ['id', 'skill_name', 'status', 'latency_ms', 'cached',
                       'error_message', 'executed_at', 'parameters', 'result', 'user_id']
            execution = dict(zip(columns, row))
            
            # Convertir executed_at a America/Lima
            if execution.get('executed_at') and timezone.is_naive(execution['executed_at']):
                execution['executed_at'] = timezone.make_aware(
                    execution['executed_at'], datetime.timezone.utc
                )
            if execution.get('executed_at'):
                execution['executed_at'] = timezone.localtime(execution['executed_at'])
            
            # Parsear JSON fields
            if execution.get('parameters') and isinstance(execution['parameters'], str):
                try:
                    execution['parameters'] = json.loads(execution['parameters'])
                except (json.JSONDecodeError, TypeError):
                    pass
            if execution.get('result') and isinstance(execution['result'], str):
                try:
                    execution['result'] = json.loads(execution['result'])
                except (json.JSONDecodeError, TypeError):
                    pass
            
            # Resolver nombre de usuario
            execution['user_name'] = 'Sistema'
            if execution.get('user_id'):
                try:
                    cursor.execute(
                        "SELECT username FROM intelligence_user WHERE id = %s",
                        [str(execution['user_id'])]
                    )
                    user_row = cursor.fetchone()
                    if user_row:
                        execution['user_name'] = user_row[0]
                except Exception:
                    pass
    
    if not execution:
        return render(request, 'intelligence/skills_execution_detail.html', {
            'execution': None,
            'error': 'Ejecución no encontrada',
            'skill_info': None,
        })
    
    skill_info = skill_map.get(execution.get('skill_name', ''))
    
    return render(request, 'intelligence/skills_execution_detail.html', {
        'execution': execution,
        'error': None,
        'skill_info': skill_info,
    })


# ═══════════════════════════════════════════════════════════════════════════════
# PERFILES DE INTELIGENCIA (Niveles v2)
# ═══════════════════════════════════════════════════════════════════════════════

@admin_required
def profile_list(request):
    """Lista todos los perfiles de inteligencia."""
    from .models import UserIntelligenceProfile
    
    profiles = UserIntelligenceProfile.objects.select_related('user__role').all().order_by('user__username')
    
    return render(request, 'intelligence/profiles/list.html', {
        'profiles': profiles,
        'active_section': 'profiles',
    })


@admin_required
def profile_detail(request, profile_id):
    """Detalle de un perfil de inteligencia."""
    from .models import UserIntelligenceProfile, IntelligenceCollection
    
    try:
        profile = UserIntelligenceProfile.objects.select_related('user__role').get(id=profile_id)
    except UserIntelligenceProfile.DoesNotExist:
        messages.error(request, "Perfil de inteligencia no encontrado.")
        return redirect('intelligence:profile_list')
    
    extra_collections = profile.extra_collections.all()
    blocked_collections = profile.blocked_collections.all()
    all_collections = IntelligenceCollection.objects.filter(is_active=True).order_by('name')
    
    return render(request, 'intelligence/profiles/detail.html', {
        'profile': profile,
        'extra_collections': extra_collections,
        'blocked_collections': blocked_collections,
        'all_collections': all_collections,
        'active_section': 'profiles',
    })


@admin_required
def profile_edit(request, profile_id):
    """Edita un perfil de inteligencia (nivel, dominios, colecciones extra/bloqueadas)."""
    from .models import UserIntelligenceProfile, IntelligenceCollection, LEVEL_CHOICES, DOMAIN_CHOICES
    
    try:
        profile = UserIntelligenceProfile.objects.select_related('user__role').get(id=profile_id)
    except UserIntelligenceProfile.DoesNotExist:
        messages.error(request, "Perfil de inteligencia no encontrado.")
        return redirect('intelligence:profile_list')
    
    if request.method == 'POST':
        try:
            # Actualizar nivel
            new_level = int(request.POST.get('level', profile.level))
            if 1 <= new_level <= 5:
                profile.level = new_level
            
            # Actualizar dominios (vienen como lista desde checkboxes)
            domains_list = request.POST.getlist('allowed_domains')
            profile.allowed_domains = [d.strip() for d in domains_list if d.strip()]
            
            # Actualizar colecciones extra
            extra_ids = request.POST.getlist('extra_collections')
            profile.extra_collections.set(extra_ids)
            
            # Actualizar colecciones bloqueadas
            blocked_ids = request.POST.getlist('blocked_collections')
            profile.blocked_collections.set(blocked_ids)
            
            profile.save()
            messages.success(request, f"Perfil de {profile.user.username} actualizado correctamente.")
            return redirect('intelligence:profile_detail', profile_id=profile.id)
            
        except Exception as e:
            messages.error(request, f"Error actualizando perfil: {e}")
    
    all_collections = IntelligenceCollection.objects.filter(is_active=True).order_by('name')
    extra_collections = profile.extra_collections.all()
    blocked_collections = profile.blocked_collections.all()
    
    return render(request, 'intelligence/profiles/edit.html', {
        'profile': profile,
        'all_collections': all_collections,
        'extra_collections': extra_collections,
        'blocked_collections': blocked_collections,
        'level_choices': LEVEL_CHOICES,
        'domain_choices': DOMAIN_CHOICES,
        'active_section': 'profiles',
    })


@admin_required
def profile_reset(request, profile_id):
    """Resetea un perfil a los valores por defecto del rol."""
    from .models import UserIntelligenceProfile
    
    try:
        profile = UserIntelligenceProfile.objects.select_related('user__role').get(id=profile_id)
    except UserIntelligenceProfile.DoesNotExist:
        messages.error(request, "Perfil de inteligencia no encontrado.")
        return redirect('intelligence:profile_list')
    
    if request.method == 'POST':
        try:
            if profile.user.role:
                profile.level = profile.user.role.default_level
                profile.allowed_domains = profile.user.role.default_domains or ['general']
            else:
                profile.level = 1
                profile.allowed_domains = ['general']
            
            profile.extra_collections.clear()
            profile.blocked_collections.clear()
            profile.save()
            
            messages.success(request, f"Perfil de {profile.user.username} reseteado a valores del rol.")
        except Exception as e:
            messages.error(request, f"Error reseteando perfil: {e}")
    
    return redirect('intelligence:profile_detail', profile_id=profile.id)


# ═══════════════════════════════════════════════════════════════════════════════
# API DE PERFILES DE INTELIGENCIA
# ═══════════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([AllowAny])
@authentication_classes([])
def api_profile_list(request):
    """API: Lista todos los perfiles de inteligencia."""
    from .models import UserIntelligenceProfile
    
    try:
        profiles = UserIntelligenceProfile.objects.select_related('user').all().order_by('user__username')
        data = []
        for p in profiles:
            data.append({
                'id': str(p.id),
                'user_id': str(p.user.id),
                'username': p.user.username,
                'level': p.level,
                'allowed_domains': p.allowed_domains,
                'extra_collections': list(p.extra_collections.values_list('name', flat=True)),
                'blocked_collections': list(p.blocked_collections.values_list('name', flat=True)),
                'created_at': p.created_at.isoformat() if p.created_at else None,
                'updated_at': p.updated_at.isoformat() if p.updated_at else None,
            })
        
        return Response({
            'success': True,
            'profiles': data,
            'count': len(data),
        })
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e),
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
@authentication_classes([])
def api_profile_detail(request, profile_id):
    """API: Detalle de un perfil de inteligencia."""
    from .models import UserIntelligenceProfile
    
    try:
        profile = UserIntelligenceProfile.objects.select_related('user').get(id=profile_id)
        return Response({
            'success': True,
            'profile': {
                'id': str(profile.id),
                'user_id': str(profile.user.id),
                'username': profile.user.username,
                'level': profile.level,
                'allowed_domains': profile.allowed_domains,
                'extra_collections': list(profile.extra_collections.values('id', 'name')),
                'blocked_collections': list(profile.blocked_collections.values('id', 'name')),
                'created_at': profile.created_at.isoformat() if profile.created_at else None,
                'updated_at': profile.updated_at.isoformat() if profile.updated_at else None,
            },
        })
    except UserIntelligenceProfile.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Perfil no encontrado',
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e),
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT', 'PATCH'])
@permission_classes([AllowAny])
@authentication_classes([])
def api_profile_update(request, profile_id):
    """API: Actualiza un perfil de inteligencia."""
    from .models import UserIntelligenceProfile, IntelligenceCollection
    
    try:
        profile = UserIntelligenceProfile.objects.select_related('user').get(id=profile_id)
    except UserIntelligenceProfile.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Perfil no encontrado',
        }, status=status.HTTP_404_NOT_FOUND)
    
    try:
        import json
        data = json.loads(request.body) if isinstance(request.body, bytes) else request.data
        
        if 'level' in data:
            new_level = int(data['level'])
            if 1 <= new_level <= 5:
                profile.level = new_level
        
        if 'allowed_domains' in data:
            profile.allowed_domains = data['allowed_domains']
        
        if 'extra_collections' in data:
            extra_names = data['extra_collections']
            extra_colls = IntelligenceCollection.objects.filter(name__in=extra_names)
            profile.extra_collections.set(extra_colls)
        
        if 'blocked_collections' in data:
            blocked_names = data['blocked_collections']
            blocked_colls = IntelligenceCollection.objects.filter(name__in=blocked_names)
            profile.blocked_collections.set(blocked_colls)
        
        profile.save()
        
        return Response({
            'success': True,
            'message': f"Perfil de {profile.user.username} actualizado.",
            'profile': {
                'id': str(profile.id),
                'level': profile.level,
                'allowed_domains': profile.allowed_domains,
            },
        })
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e),
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([AllowAny])
@authentication_classes([])
def api_my_profile(request):
    """API: Obtiene el perfil de inteligencia del usuario actual."""
    from .permissions import get_user_profile
    
    profile = get_user_profile(request)
    
    if not profile:
        return Response({
            'success': False,
            'error': 'No se pudo determinar el perfil de inteligencia',
        }, status=status.HTTP_404_NOT_FOUND)
    
    return Response({
        'success': True,
        'profile': {
            'id': str(profile.id) if hasattr(profile, 'id') else None,
            'level': profile.level,
            'allowed_domains': profile.allowed_domains,
            'extra_collections': list(profile.extra_collections.values('id', 'name')) if hasattr(profile, 'extra_collections') else [],
            'blocked_collections': list(profile.blocked_collections.values('id', 'name')) if hasattr(profile, 'blocked_collections') else [],
        },
    })


@api_view(['GET'])
@permission_classes([AllowAny])
@authentication_classes([])
def api_check_collection_access(request, collection_name):
    """API: Verifica si el usuario actual puede acceder a una colección."""
    from .permissions import get_user_profile
    from .models import IntelligenceCollection
    
    profile = get_user_profile(request)
    
    if not profile:
        return Response({
            'success': False,
            'error': 'No se pudo determinar el perfil de inteligencia',
            'accessible': False,
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        collection = IntelligenceCollection.objects.get(name=collection_name, is_active=True)
    except IntelligenceCollection.DoesNotExist:
        return Response({
            'success': False,
            'error': f"Colección '{collection_name}' no encontrada",
            'accessible': False,
        }, status=status.HTTP_404_NOT_FOUND)
    
    can_access, reason = profile.can_access_collection(collection)
    
    return Response({
        'success': True,
        'accessible': can_access,
        'reason': reason if not can_access else None,
        'collection': {
            'name': collection.name,
            'min_level': collection.min_level,
            'domain': collection.domain,
            'is_public': collection.is_public,
        },
        'profile': {
            'level': profile.level,
            'allowed_domains': profile.allowed_domains,
        },
    })


# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD DE CONSUMO DE IA (DeepSeek)
# ═══════════════════════════════════════════════════════════════════════════════

def ai_consumption_dashboard(request):
    """
    Dashboard de consumo de tokens de IA (DeepSeek).
    Muestra un gráfico de barras por hora para una fecha seleccionada,
    con métricas de total de tokens, llamadas, costo estimado, etc.
    Incluye desglose granular por caller_app (chatbot, extractor, skills, etc.)
    """
    from .models import AIConsumptionLog
    from django.db.models import Sum, Count, Avg
    from django.db.models.functions import ExtractHour
    from datetime import date, timedelta
    
    # Fecha seleccionada (por defecto hoy)
    fecha_str = request.GET.get('fecha', '')
    if fecha_str:
        try:
            fecha_seleccionada = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            fecha_seleccionada = timezone.now().date()
    else:
        fecha_seleccionada = timezone.now().date()
    
    # Filtro opcional por caller_app
    caller_filter = request.GET.get('caller', '')
    
    # Rango de fechas para el selector (últimos 30 días)
    hoy = timezone.now().date()
    fechas_disponibles = [
        (hoy - timedelta(days=i)).isoformat()
        for i in range(30)
    ]
    
    # Query base para la fecha seleccionada
    logs_del_dia = AIConsumptionLog.objects.filter(
        created_at__date=fecha_seleccionada
    )
    
    # Aplicar filtro por caller_app si se especificó
    if caller_filter:
        logs_del_dia = logs_del_dia.filter(caller_app=caller_filter)
    
    # Métricas generales del día
    total_llamadas = logs_del_dia.count()
    total_tokens = logs_del_dia.aggregate(
        total=Sum('total_tokens')
    )['total'] or 0
    total_prompt = logs_del_dia.aggregate(
        total=Sum('prompt_tokens')
    )['total'] or 0
    total_completion = logs_del_dia.aggregate(
        total=Sum('completion_tokens')
    )['total'] or 0
    costo_total = logs_del_dia.aggregate(
        total=Sum('estimated_cost_usd')
    )['total'] or 0
    llamadas_exitosas = logs_del_dia.filter(success=True).count()
    llamadas_fallidas = logs_del_dia.filter(success=False).count()
    duracion_promedio = logs_del_dia.aggregate(
        avg=Avg('duration_ms')
    )['avg'] or 0
    
    # Agregación por hora (0-23)
    horas_data = []
    for hora in range(24):
        logs_hora = logs_del_dia.filter(
            created_at__hour=hora
        )
        count = logs_hora.count()
        tokens_hora = logs_hora.aggregate(
            total=Sum('total_tokens')
        )['total'] or 0
        costo_hora = logs_hora.aggregate(
            total=Sum('estimated_cost_usd')
        )['total'] or 0
        
        horas_data.append({
            'hora': hora,
            'hora_label': f'{hora:02d}:00',
            'llamadas': count,
            'tokens': tokens_hora,
            'costo': float(costo_hora),
        })
    
    # ── DESGLOSE GRANULAR POR caller_app ──
    caller_stats = []
    callers_disponibles = logs_del_dia.values('caller_app').distinct()
    
    for item in callers_disponibles:
        app_name = item['caller_app'] or 'desconocido'
        qs = logs_del_dia.filter(caller_app=app_name)
        stats = qs.aggregate(
            llamadas=Count('id'),
            tokens=Sum('total_tokens'),
            prompt=Sum('prompt_tokens'),
            completion=Sum('completion_tokens'),
            costo=Sum('estimated_cost_usd'),
            duracion=Avg('duration_ms'),
        )
        exitosas = qs.filter(success=True).count()
        fallidas = qs.filter(success=False).count()
        
        caller_stats.append({
            'caller_app': app_name,
            'llamadas': stats['llamadas'] or 0,
            'tokens': stats['tokens'] or 0,
            'prompt': stats['prompt'] or 0,
            'completion': stats['completion'] or 0,
            'costo': float(stats['costo'] or 0),
            'duracion_promedio': int(stats['duracion'] or 0),
            'exitosas': exitosas,
            'fallidas': fallidas,
            'tasa_exito': round((exitosas / (exitosas + fallidas) * 100) if (exitosas + fallidas) > 0 else 0, 1),
        })
    
    # Ordenar por llamadas descendente
    caller_stats.sort(key=lambda x: x['llamadas'], reverse=True)
    
    # ── DESGLOSE POR ENDPOINT (función específica) ──
    endpoint_stats = []
    endpoints = logs_del_dia.values('endpoint').distinct()
    
    for item in endpoints:
        ep_name = item['endpoint'] or 'desconocido'
        qs = logs_del_dia.filter(endpoint=ep_name)
        stats = qs.aggregate(
            llamadas=Count('id'),
            tokens=Sum('total_tokens'),
            costo=Sum('estimated_cost_usd'),
        )
        endpoint_stats.append({
            'endpoint': ep_name,
            'llamadas': stats['llamadas'] or 0,
            'tokens': stats['tokens'] or 0,
            'costo': float(stats['costo'] or 0),
        })
    
    endpoint_stats.sort(key=lambda x: x['llamadas'], reverse=True)
    
    # Últimos registros (para la tabla)
    ultimos_registros = logs_del_dia.order_by('-created_at')[:20]
    
    # Datos para el gráfico (JSON)
    chart_labels = [h['hora_label'] for h in horas_data]
    chart_llamadas = [h['llamadas'] for h in horas_data]
    chart_tokens = [h['tokens'] for h in horas_data]
    
    # Datos para gráfico de caller_app (top 5)
    caller_chart_labels = [c['caller_app'][:25] for c in caller_stats[:5]]
    caller_chart_llamadas = [c['llamadas'] for c in caller_stats[:5]]
    caller_chart_tokens = [c['tokens'] for c in caller_stats[:5]]
    
    context = {
        'fecha_seleccionada': fecha_seleccionada,
        'fecha_seleccionada_str': fecha_seleccionada.isoformat(),
        'fechas_disponibles': fechas_disponibles,
        'total_llamadas': total_llamadas,
        'total_tokens': total_tokens,
        'total_prompt': total_prompt,
        'total_completion': total_completion,
        'costo_total': float(costo_total),
        'llamadas_exitosas': llamadas_exitosas,
        'llamadas_fallidas': llamadas_fallidas,
        'duracion_promedio': int(duracion_promedio),
        'horas_data': horas_data,
        'caller_stats': caller_stats,
        'endpoint_stats': endpoint_stats,
        'ultimos_registros': ultimos_registros,
        'chart_labels': json.dumps(chart_labels),
        'chart_llamadas': json.dumps(chart_llamadas),
        'chart_tokens': json.dumps(chart_tokens),
        'caller_chart_labels': json.dumps(caller_chart_labels),
        'caller_chart_llamadas': json.dumps(caller_chart_llamadas),
        'caller_chart_tokens': json.dumps(caller_chart_tokens),
        'caller_filter': caller_filter,
        'hoy': hoy,
        'seccion_actual': 'consumo-ia',
    }
    
    return render(request, 'intelligence/ai_consumption_dashboard.html', context)
