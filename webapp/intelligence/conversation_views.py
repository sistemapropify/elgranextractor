"""Session-owned conversation history for the existing web chat."""
import uuid

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods, require_GET

from .models import AppConfig, Conversation, User


def _session_user(request):
    user = getattr(request, 'current_user', None)
    if isinstance(user, User) and user.is_active:
        return user
    session_key = request.session.session_key
    if not session_key:
        return None
    return User.objects.filter(is_active=True, metadata__session_key=session_key).first()


def _summary(conversation):
    return {'id': str(conversation.pk), 'title': conversation.title,
            'updated_at': conversation.last_message_at.isoformat()}


@require_http_methods(['GET', 'POST'])
def chat_web_conversations(request):
    user = _session_user(request)
    if user is None:
        return JsonResponse({'error': 'Abre el chat para iniciar una sesión.'}, status=403)
    app = AppConfig.objects.filter(pk='chat-web', is_active=True).first()
    if app is None:
        return JsonResponse({'error': 'El chat no está disponible.'}, status=503)
    if request.method == 'POST':
        conversation = Conversation.objects.create(user=user, app=app,
            session_id=f'chat_web_{uuid.uuid4().hex}', messages=[])
        return JsonResponse({'conversation': _summary(conversation)}, status=201)
    rows = list(Conversation.objects.filter(user=user, app=app, is_active=True)
                .order_by('-last_message_at', '-pk')[:50])
    return JsonResponse({'count': len(rows), 'conversations': [_summary(row) for row in rows]})


@require_GET
def chat_web_conversation_detail(request, conversation_id):
    user = _session_user(request)
    if user is None:
        return JsonResponse({'error': 'Sesión requerida.'}, status=403)
    conversation = get_object_or_404(Conversation, pk=conversation_id, user=user,
                                    app_id='chat-web', app__is_active=True, is_active=True)
    return JsonResponse({'conversation': {**_summary(conversation),
                                         'messages': conversation.messages or []}})
