from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from prospects.propify_auth import WEB_PROFILE_SESSION_KEY, WEB_TOKEN_SESSION_KEY

from .forms import ExternalAgentForm
from .models import DocumentType, ExternalAgent, ExternalAgentAttachment


class ExternalAgentsViewsTests(TestCase):
    def setUp(self):
        self.personal_type = DocumentType.objects.create(
            name='DNI',
            scope=DocumentType.Scope.PERSONAL,
            sort_order=1,
        )
        self.attachment_type = DocumentType.objects.create(
            name='DNI frontal',
            scope=DocumentType.Scope.ATTACHMENT,
            sort_order=1,
        )
        self.agent = ExternalAgent.objects.create(
            first_name='Ana',
            paternal_last_name='Quispe',
            maternal_last_name='Rojas',
            personal_document_type=self.personal_type,
            document_number='12345678',
            address='Av. Ejemplo 123',
            email='ana@example.com',
            mobile='+51 999 111 222',
            created_by_username='tester',
            updated_by_username='tester',
        )

    def authenticate_propify(self):
        session = self.client.session
        session[WEB_TOKEN_SESSION_KEY] = 'test-token'
        session[WEB_PROFILE_SESSION_KEY] = {
            'id': '99',
            'username': 'tester',
            'email': 'tester@example.com',
        }
        session.save()

    def test_private_module_redirects_to_its_propify_login(self):
        response = self.client.get(reverse('external_agents:dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/agentes-externos/login/', response['Location'])

    def test_dashboard_renders_existing_agent(self):
        self.authenticate_propify()
        response = self.client.get(reverse('external_agents:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ana Quispe Rojas')
        self.assertContains(response, '12345678')

    def test_all_module_pages_render(self):
        login_response = self.client.get(reverse('external_agents:login'))
        self.assertEqual(login_response.status_code, 200)
        self.assertContains(login_response, 'Ingresar con Propify')

        self.authenticate_propify()
        pages = [
            reverse('external_agents:agent_create'),
            reverse('external_agents:agent_detail', kwargs={'pk': self.agent.pk}),
            reverse('external_agents:agent_edit', kwargs={'pk': self.agent.pk}),
            reverse('external_agents:configuration'),
        ]
        for url in pages:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)

    def test_create_agent_records_propify_user(self):
        self.authenticate_propify()
        response = self.client.post(reverse('external_agents:agent_create'), {
            'first_name': 'Luis',
            'paternal_last_name': 'Mamani',
            'maternal_last_name': '',
            'personal_document_type': self.personal_type.pk,
            'document_number': '87654321',
            'address': 'Calle Uno 456',
            'email': 'luis@example.com',
            'mobile': '+51 988 777 666',
        })
        created = ExternalAgent.objects.get(document_number='87654321')
        self.assertRedirects(
            response,
            reverse('external_agents:agent_detail', kwargs={'pk': created.pk}),
        )
        self.assertEqual(created.created_by_username, 'tester')

    def test_duplicate_person_document_is_rejected(self):
        form = ExternalAgentForm(data={
            'first_name': 'Otra',
            'paternal_last_name': 'Persona',
            'maternal_last_name': '',
            'personal_document_type': self.personal_type.pk,
            'document_number': '12345678',
            'address': 'Calle Dos 789',
            'email': 'otra@example.com',
            'mobile': '+51 900 000 000',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('document_number', form.errors)

    def test_personal_and_attachment_catalogs_are_separate(self):
        self.authenticate_propify()
        response = self.client.post(
            reverse('external_agents:document_type_create'),
            {'scope': DocumentType.Scope.ATTACHMENT, 'name': 'Contrato firmado', 'sort_order': 2},
        )
        self.assertRedirects(response, reverse('external_agents:configuration'))
        self.assertTrue(DocumentType.objects.filter(
            name='Contrato firmado',
            scope=DocumentType.Scope.ATTACHMENT,
        ).exists())
        self.assertFalse(DocumentType.objects.filter(
            name='Contrato firmado',
            scope=DocumentType.Scope.PERSONAL,
        ).exists())

    def test_attachment_upload_and_delete(self):
        self.authenticate_propify()
        uploaded = SimpleUploadedFile(
            'identidad.pdf',
            b'%PDF-1.4 test',
            content_type='application/pdf',
        )
        field = ExternalAgentAttachment._meta.get_field('file')
        with patch.object(
            field.storage,
            'save',
            return_value='agentes-externos/2026/10/identidad.pdf',
        ) as storage_save:
            response = self.client.post(
                reverse('external_agents:attachment_upload', kwargs={'pk': self.agent.pk}),
                {'document_type': self.attachment_type.pk, 'file': uploaded},
            )
        self.assertRedirects(
            response,
            reverse('external_agents:agent_detail', kwargs={'pk': self.agent.pk}),
        )
        attachment = ExternalAgentAttachment.objects.get(agent=self.agent)
        self.assertEqual(attachment.original_name, 'identidad.pdf')
        self.assertEqual(attachment.uploaded_by_username, 'tester')
        storage_save.assert_called_once()

        with patch.object(field.storage, 'delete') as storage_delete:
            response = self.client.post(reverse(
                'external_agents:attachment_delete',
                kwargs={'pk': self.agent.pk, 'attachment_pk': attachment.pk},
            ))
        self.assertRedirects(
            response,
            reverse('external_agents:agent_detail', kwargs={'pk': self.agent.pk}),
        )
        self.assertFalse(
            ExternalAgentAttachment.objects.filter(pk=attachment.pk).exists()
        )
        storage_delete.assert_called_once()
