from django.test import TestCase, Client
from django.urls import reverse

from intelligence.models import AppConfig, Conversation, Role, User
from intelligence.services.chat_processor import ChatProcessor


class ChatWebConversationApiTests(TestCase):
    def setUp(self):
        self.role = Role.objects.create(
            name='Chat tester',
            default_level=1,
            max_level=1,
        )
        session = self.client.session
        session['chat_test'] = True
        session.save()

        self.user = User.objects.create(
            role=self.role,
            username='chat_tester',
            phone='chat_tester',
            is_active=True,
            metadata={'session_key': session.session_key},
        )
        self.other_user = User.objects.create(
            role=self.role,
            username='other_chat_tester',
            phone='other_chat_tester',
            is_active=True,
        )
        self.app = AppConfig.objects.create(
            id='chat-web',
            name='Chat Web',
            level=1,
            is_active=True,
        )

    def test_title_is_derived_for_legacy_conversation(self):
        conversation = Conversation.objects.create(
            user=self.user,
            app=self.app,
            session_id='legacy-chat',
            messages=[{'role': 'user', 'content': 'Busca departamentos en Cayma'}],
        )
        self.assertEqual(conversation.title, 'Busca departamentos en Cayma')

    def test_first_user_message_persists_title(self):
        conversation = Conversation.objects.create(
            user=self.user,
            app=self.app,
            session_id='new-chat',
            messages=[],
        )
        ChatProcessor._save_user_message(conversation, 'Casas en Cayma')
        conversation.refresh_from_db()
        self.assertEqual(conversation.metadata['title'], 'Casas en Cayma')

    def test_create_list_and_open_conversation_from_session(self):
        collection_url = reverse('intelligence:chat_web_conversations')
        created = self.client.post(
            collection_url,
            {},
            content_type='application/json',
        )
        self.assertEqual(created.status_code, 201)
        conversation_id = created.json()['conversation']['id']

        listed = self.client.get(collection_url)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()['count'], 1)

        detail_url = reverse(
            'intelligence:chat_web_conversation_detail',
            kwargs={'conversation_id': conversation_id},
        )
        detail = self.client.get(detail_url)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()['conversation']['messages'], [])

    def test_cannot_open_another_users_conversation(self):
        foreign = Conversation.objects.create(
            user=self.other_user,
            app=self.app,
            session_id='foreign-chat',
            messages=[],
        )
        detail_url = reverse(
            'intelligence:chat_web_conversation_detail',
            kwargs={'conversation_id': foreign.id},
        )
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 404)

    def test_anonymous_or_inactive_session_cannot_read_history(self):
        url = reverse('intelligence:chat_web_conversations')
        self.assertEqual(Client().get(url).status_code, 403)
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_create_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.cookies = self.client.cookies
        self.assertEqual(client.post(reverse('intelligence:chat_web_conversations'), {}).status_code, 403)
