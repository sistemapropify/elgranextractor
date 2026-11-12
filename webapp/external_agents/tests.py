from unittest.mock import patch

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from prospects.propify_auth import WEB_PROFILE_SESSION_KEY, WEB_TOKEN_SESSION_KEY

from .forms import ExternalAgentForm
from .models import (
    CommissionCollection,
    CommissionCollectionEntry,
    CommissionPayment,
    DocumentType,
    ExternalAgent,
    ExternalAgentAttachment,
)
from .views import _normalize_closing


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
        self.attachment_type_cv = DocumentType.objects.create(
            name='Curriculum Vitae',
            scope=DocumentType.Scope.ATTACHMENT,
            sort_order=2,
        )
        self.agent = ExternalAgent.objects.create(
            full_name='Ana Quispe Rojas',
            personal_document_type=self.personal_type,
            document_number='12345678',
            address='Av. Ejemplo 123',
            email='ana@example.com',
            mobile='+51 999 111 222',
            observations='Disponible para proyectos en Arequipa.',
            level=ExternalAgent.Level.SENIOR,
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
        self.assertContains(response, 'Senior')
        self.assertContains(response, 'class="ea-agent-card"')
        self.assertContains(response, 'vista=matriz')
        self.assertIn('no-store', response['Cache-Control'])

    def test_dashboard_renders_excel_style_matrix(self):
        self.authenticate_propify()
        ExternalAgentAttachment.objects.create(
            agent=self.agent,
            document_type=self.attachment_type,
            file='agentes-externos/matriz.pdf',
            original_name='DNI y certificado.pdf',
            uploaded_by_username='tester',
        )
        response = self.client.get(
            reverse('external_agents:dashboard'),
            {'vista': 'matriz'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="ea-matrix"')
        for heading in (
            'ID',
            'Nombres y apellidos',
            'Nivel',
            'DNI / documento',
            'Celular',
            'Correo',
            'Dirección',
            'Observaciones',
            'Documentos',
        ):
            self.assertContains(response, heading)
        self.assertContains(response, 'Ana Quispe Rojas')
        self.assertContains(response, 'Disponible para proyectos en Arequipa.')
        self.assertContains(response, 'DNI y certificado.pdf')

    def test_all_module_pages_render(self):
        login_response = self.client.get(reverse('external_agents:login'))
        self.assertEqual(login_response.status_code, 200)
        self.assertContains(login_response, 'Ingresar con Propify')
        self.assertContains(login_response, 'id="loginForm"')
        self.assertContains(login_response, "button.disabled = true")

        self.authenticate_propify()
        create_response = self.client.get(reverse('external_agents:agent_create'))
        self.assertContains(create_response, 'enctype="multipart/form-data"')
        self.assertContains(create_response, 'Training')
        self.assertContains(create_response, 'Junior')
        self.assertContains(create_response, 'Senior')
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
            'full_name': 'Luis Mamani',
            'personal_document_type': self.personal_type.pk,
            'document_number': '87654321',
            'address': 'Calle Uno 456',
            'email': 'luis@example.com',
            'mobile': '+51 988 777 666',
            'level': ExternalAgent.Level.JUNIOR,
            'observations': 'Prefiere contacto por WhatsApp.',
        })
        created = ExternalAgent.objects.get(document_number='87654321')
        self.assertRedirects(
            response,
            reverse('external_agents:agent_detail', kwargs={'pk': created.pk}),
        )
        self.assertEqual(created.created_by_username, 'tester')
        self.assertEqual(created.level, ExternalAgent.Level.JUNIOR)
        self.assertEqual(created.observations, 'Prefiere contacto por WhatsApp.')

    def test_create_agent_accepts_multiple_attachments_during_registration(self):
        self.authenticate_propify()
        identity = SimpleUploadedFile(
            'dni.pdf',
            b'%PDF-1.4 registration',
            content_type='application/pdf',
        )
        curriculum = SimpleUploadedFile(
            'curriculum.pdf',
            b'%PDF-1.4 curriculum',
            content_type='application/pdf',
        )
        certificate = SimpleUploadedFile(
            'certificado.pdf',
            b'%PDF-1.4 certificate',
            content_type='application/pdf',
        )
        field = ExternalAgentAttachment._meta.get_field('file')
        with patch.object(
            field.storage,
            'save',
            side_effect=[
                'agentes-externos/2026/11/dni.pdf',
                'agentes-externos/2026/11/curriculum.pdf',
                'agentes-externos/2026/11/certificado.pdf',
            ],
        ):
            response = self.client.post(reverse('external_agents:agent_create'), {
                'full_name': 'Luis Mamani',
                'personal_document_type': self.personal_type.pk,
                'document_number': '87654321',
                'address': 'Calle Uno 456',
                'email': 'luis@example.com',
                'mobile': '+51 988 777 666',
                'doc_2-document_type': self.attachment_type.pk,
                'doc_2-file': identity,
                'doc_3-document_type': self.attachment_type_cv.pk,
                'doc_3-file': curriculum,
                'doc_4-document_type': self.attachment_type_cv.pk,
                'doc_4-file': certificate,
            })
        created = ExternalAgent.objects.get(document_number='87654321')
        self.assertRedirects(
            response,
            reverse('external_agents:agent_detail', kwargs={'pk': created.pk}),
        )
        attachments = list(
            ExternalAgentAttachment.objects.filter(agent=created).order_by('pk')
        )
        self.assertEqual(len(attachments), 3)
        self.assertEqual(
            [attachment.original_name for attachment in attachments],
            ['dni.pdf', 'curriculum.pdf', 'certificado.pdf'],
        )

    def test_attachment_during_registration_requires_its_type(self):
        self.authenticate_propify()
        uploaded = SimpleUploadedFile(
            'sin-tipo.pdf',
            b'%PDF-1.4 missing type',
            content_type='application/pdf',
        )
        response = self.client.post(reverse('external_agents:agent_create'), {
            'full_name': 'Luis Mamani',
            'personal_document_type': self.personal_type.pk,
            'document_number': '87654321',
            'address': 'Calle Uno 456',
            'email': 'luis@example.com',
            'mobile': '+51 988 777 666',
            'doc_0-file': uploaded,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'Selecciona el tipo de documento.',
        )
        self.assertFalse(ExternalAgent.objects.filter(document_number='87654321').exists())

    def test_duplicate_person_document_is_rejected(self):
        form = ExternalAgentForm(data={
            'full_name': 'Otra Persona',
            'personal_document_type': self.personal_type.pk,
            'document_number': '12345678',
            'address': 'Calle Dos 789',
            'email': 'otra@example.com',
            'mobile': '+51 900 000 000',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('document_number', form.errors)

    def test_all_agent_fields_are_optional(self):
        form = ExternalAgentForm()
        required = {
            name: field.required
            for name, field in form.fields.items()
        }
        self.assertFalse(any(required.values()), required)

        self.authenticate_propify()
        before = ExternalAgent.objects.count()
        first = self.client.post(reverse('external_agents:agent_create'), {})
        second = self.client.post(reverse('external_agents:agent_create'), {})
        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        self.assertEqual(ExternalAgent.objects.count(), before + 2)
        blank_agents = ExternalAgent.objects.filter(
            full_name='',
            document_number='',
        )
        self.assertGreaterEqual(blank_agents.count(), 2)

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
                {
                    'doc_0-document_type': self.attachment_type.pk,
                    'doc_0-file': uploaded,
                },
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

    def test_detail_uses_attachment_modals_and_preview(self):
        self.authenticate_propify()
        attachment = ExternalAgentAttachment.objects.create(
            agent=self.agent,
            document_type=self.attachment_type,
            file='agentes-externos/prueba.pdf',
            original_name='prueba.pdf',
            uploaded_by_username='tester',
        )
        response = self.client.get(
            reverse('external_agents:agent_detail', kwargs={'pk': self.agent.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="eaOpenAttachmentUpload"')
        self.assertContains(response, 'id="eaAttachmentUploadDialog"')
        self.assertContains(response, 'id="eaAttachmentPreviewDialog"')
        self.assertContains(response, 'id="eaAttachmentPreviewOpen"')
        self.assertContains(response, 'class="ea-file-preview-button"')
        self.assertContains(response, 'Disponible para proyectos en Arequipa.')
        self.assertIn('no-store', response['Cache-Control'])

        field = ExternalAgentAttachment._meta.get_field('file')
        with patch.object(
            field.storage,
            'open',
            return_value=ContentFile(b'%PDF-1.4 preview'),
        ):
            preview = self.client.get(reverse(
                'external_agents:attachment_preview',
                kwargs={'pk': self.agent.pk, 'attachment_pk': attachment.pk},
            ))
        self.assertEqual(preview.status_code, 200)
        self.assertTrue(
            preview['Content-Disposition'].startswith('inline;')
        )
        self.assertEqual(preview['Content-Type'], 'application/pdf')
        self.assertEqual(preview['X-Frame-Options'], 'SAMEORIGIN')

    def closing_payload(self):
        return [{
            'id': 42,
            'property_code': 'PROP000261',
            'property_title': 'Casa en Urb. Colonial II',
            'closing_date': '2026-11-06',
            'amount': '259000.00',
            'currency_code': 'USD',
            'commission_pct': '0.60',
            'commission_amount': '1554.00',
            'agents_amount': '310.80',
            'brokers_amount': '0.00',
            'propify_amount': '1243.20',
            'is_verified': True,
            'sides': [
                {
                    'role': 'listing',
                    'role_display': 'Captación',
                    'agent_name': 'Agente de Captación',
                    'share_pct': '50.00',
                    'agent_pct': '20.00',
                    'side_amount': '777.00',
                    'agent_amount': '155.40',
                    'broker_name': None,
                    'broker_pct': '0.00',
                    'broker_amount': '0.00',
                },
                {
                    'role': 'buyer',
                    'role_display': 'Comprador',
                    'agent_name': 'Agente Comprador',
                    'share_pct': '50.00',
                    'agent_pct': '20.00',
                    'side_amount': '777.00',
                    'agent_amount': '155.40',
                    'broker_name': None,
                    'broker_pct': '0.00',
                    'broker_amount': '0.00',
                },
            ],
        }]

    def test_normalize_closing_uses_real_propify_commission_fields(self):
        row = _normalize_closing(self.closing_payload()[0])
        self.assertEqual(row['code'], 'PROP000261')
        self.assertEqual(row['amount'], 259000)
        self.assertEqual(row['commission'], 1554)
        self.assertEqual(row['agents_total'], 310.8)
        self.assertEqual(row['commission_propify'], 1243.2)
        self.assertEqual(row['currency'], 'USD')
        self.assertEqual(
            [agent['amount'] for agent in row['agents']],
            [155.4, 155.4],
        )
        self.assertEqual(
            {item['name'] for item in row['payables']},
            {'Agente de Captación', 'Agente Comprador', 'Propify'},
        )
        payable_types = {
            item['name']: item['type'] for item in row['payables']
        }
        self.assertEqual(
            payable_types['Agente de Captación'],
            CommissionPayment.BeneficiaryType.SELLER,
        )
        self.assertEqual(
            payable_types['Agente Comprador'],
            CommissionPayment.BeneficiaryType.BUYER,
        )

    def test_normalize_accepts_legacy_my_closings_fallback(self):
        row = _normalize_closing({
            'id': 7,
            'code': 'PROP000007',
            'title': 'Residencia de respaldo',
            'closing_date': '2026-11-01',
            'closing_amount': '100000.00',
            'currency_code': 'PEN',
            'commission_final': '3.00',
            'commission_total_amount': '3000.00',
            'commission_agent_amount': '2400.00',
            'commission_propify_amount': '600.00',
            'responsible_name': 'Agente de Captación',
        })
        self.assertEqual(row['code'], 'PROP000007')
        self.assertEqual(row['currency'], 'PEN')
        self.assertEqual(row['commission'], 3000)
        self.assertEqual(row['agents'][0]['amount'], 2400)
        self.assertEqual(row['commission_propify'], 600)

    def test_closing_screen_separates_agents_and_preserves_partial_collections(self):
        self.authenticate_propify()
        with patch(
            'external_agents.views._propify_closings',
            return_value=(self.closing_payload(), None),
        ):
            response = self.client.get(reverse('external_agents:cierres'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Agente de Captación')
        self.assertContains(response, 'Agente Comprador')
        self.assertContains(response, 'Comisión de agentes')
        self.assertContains(response, 'USD 1,554.00')
        self.assertContains(response, 'USD 1,243.20')
        self.assertNotContains(response, 'Pagos a agentes')

        collection = CommissionCollection.objects.get(operation_code='PROP000261')
        self.assertEqual(float(collection.amount_to_collect), 1554)
        self.assertEqual(float(collection.amount_for_agents), 310.8)
        self.assertEqual(float(collection.amount_for_propify), 1243.2)
        self.assertEqual(collection.currency_code, 'USD')

        first = self.client.post(
            reverse('external_agents:collection_add'),
            {
                'operation_code': 'PROP000261',
                'amount': '1000.00',
                'collection_date': '2026-11-07',
                'payment_method': 'Transferencia',
                'voucher': 'OP-001',
            },
        )
        second = self.client.post(
            reverse('external_agents:collection_add'),
            {
                'operation_code': 'PROP000261',
                'amount': '500.00',
                'collection_date': '2026-11-08',
                'payment_method': 'Transferencia',
                'voucher': 'OP-002',
            },
        )
        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        collection.refresh_from_db()
        self.assertEqual(float(collection.collected_amount), 1500)
        self.assertEqual(collection.status, CommissionCollection.Status.PARTIAL)
        self.assertEqual(
            list(
                CommissionCollectionEntry.objects
                .order_by('collection_date')
                .values_list('amount', flat=True)
            ),
            [1000, 500],
        )

        overpaid = self.client.post(
            reverse('external_agents:collection_add'),
            {
                'operation_code': 'PROP000261',
                'amount': '100.00',
                'collection_date': '2026-11-09',
            },
        )
        self.assertEqual(overpaid.status_code, 302)
        collection.refresh_from_db()
        self.assertEqual(float(collection.collected_amount), 1500)
        self.assertEqual(CommissionCollectionEntry.objects.count(), 2)

        payment = self.client.post(
            reverse('external_agents:payment_add'),
            {
                'operation_code': 'PROP000261',
                'beneficiary_type': CommissionPayment.BeneficiaryType.BUYER,
                'beneficiary_name': 'Agente Comprador',
                'amount': '155.40',
                'currency_code': 'USD',
                'status': CommissionPayment.Status.PAID,
                'payment_date': '2026-11-09',
                'voucher': 'PAGO-001',
            },
        )
        self.assertEqual(payment.status_code, 302)
        saved_payment = CommissionPayment.objects.get(operation_code='PROP000261')
        self.assertEqual(saved_payment.beneficiary_name, 'Agente Comprador')
        self.assertEqual(saved_payment.currency_code, 'USD')
        self.assertEqual(float(saved_payment.amount), 155.4)
