"""
Puente entre n8n (WhatsApp) y el motor de chat existente de intelligence/.

No modifica intelligence/: solo reutiliza su API pública tal como lo hace
intelligence.views.chat_web_api (ChatProcessor, ChatContext, User, Role).
La sesión por lead la resuelve ChatProcessor._get_or_create_conversation
(misma lógica que usa el chat-web): una conversación activa por
(usuario, app_id), reutilizada entre mensajes hasta que se resetea.
"""

import os
import re

from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from intelligence.models import User, Role, Conversation
from intelligence.services.chat_processor import ChatProcessor, ChatContext

APP_ID = 'whatsapp-n8n'
LEAD_ROLE_NAME = 'Lead WhatsApp'


def _check_api_key(request) -> bool:
    expected = os.environ.get('N8N_BRIDGE_API_KEY', '')
    if not expected:
        return False
    return request.headers.get('X-N8N-API-Key', '') == expected


def _normalize_phone(raw: str) -> str:
    return re.sub(r'[^\d+]', '', raw or '')


def _get_or_create_lead_role() -> Role:
    role, _ = Role.objects.get_or_create(
        name=LEAD_ROLE_NAME,
        defaults={
            'default_level': 1,
            'max_level': 1,
            'default_domains': ['agente'],
            'capabilities': {
                'memory': True, 'knowledge_base': True,
                'metrics': False, 'projects': False,
            },
            'description': 'Leads que escriben por WhatsApp, conectados vía n8n.',
        },
    )
    return role


def _get_or_create_lead(phone: str, name: str = '') -> User:
    phone = _normalize_phone(phone)
    if not phone:
        raise ValueError("'phone' vacío o inválido")
    try:
        return User.objects.get(phone=phone)
    except User.DoesNotExist:
        pass
    role = _get_or_create_lead_role()
    username = f"wa_{phone.lstrip('+')}"[:50]
    user, _ = User.objects.get_or_create(
        phone=phone,
        defaults={
            'username': username,
            'first_name': name or '',
            'role': role,
            'is_active': True,
            'metadata': {'source': 'whatsapp_n8n'},
        },
    )
    return user


@api_view(['GET'])
@permission_classes([AllowAny])
@authentication_classes([])
def ping(request):
    """GET /api/n8n/ping/ — para el nodo de test de conexión en n8n."""
    ok = _check_api_key(request)
    return Response(
        {'success': ok, 'service': 'n8n_bridge'},
        status=status.HTTP_200_OK if ok else status.HTTP_401_UNAUTHORIZED,
    )


@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def lead_message(request):
    """
    POST /api/n8n/message/
    Header: X-N8N-API-Key: <secreto>
    Body: {"phone": "+51987654321", "message": "...", "name": "Juan Perez" (opcional)}

    Reenvía el mensaje al mismo ChatProcessor que usa el chat-web/canvas.
    """
    if not _check_api_key(request):
        return Response(
            {'success': False, 'error': 'API key inválida o no configurada'},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    phone = request.data.get('phone')
    message = request.data.get('message')
    name = request.data.get('name', '')

    if not phone or not message:
        return Response(
            {'success': False, 'error': "'phone' y 'message' son requeridos"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        lead = _get_or_create_lead(phone, name)
    except ValueError as e:
        return Response({'success': False, 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    conversation = ChatProcessor._get_or_create_conversation(user=lead, app_id=APP_ID)

    ctx = ChatContext(
        user=lead,
        message=message,
        conversation=conversation,
        use_memory=True,
        use_rag=True,
        collections=[],
        app_id=APP_ID,
    )
    result = ChatProcessor.process_message(ctx)

    return Response(
        {
            'success': result.success,
            'response': result.response_text,
            'lead_id': str(lead.id),
            'conversation_id': result.conversation_id,
            'error': result.error,
        },
        status=status.HTTP_200_OK if result.success else status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def reset_session(request):
    """
    POST /api/n8n/reset/
    Body: {"phone": "+51987654321"}

    Cierra la conversación activa del lead para que el siguiente mensaje
    arranque una sesión nueva, sin historial previo.
    """
    if not _check_api_key(request):
        return Response(
            {'success': False, 'error': 'API key inválida o no configurada'},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    phone = request.data.get('phone')
    if not phone:
        return Response({'success': False, 'error': "'phone' es requerido"}, status=status.HTTP_400_BAD_REQUEST)

    phone = _normalize_phone(phone)
    try:
        lead = User.objects.get(phone=phone)
    except User.DoesNotExist:
        return Response({'success': True, 'reset': False, 'detail': 'No hay conversación previa para este número.'})

    updated = Conversation.objects.filter(user=lead, app_id=APP_ID, is_active=True).update(is_active=False)
    return Response({'success': True, 'reset': updated > 0})
