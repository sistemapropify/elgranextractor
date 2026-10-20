from types import SimpleNamespace
from unittest.mock import patch

from django.http import Http404, HttpResponse
from django.test import RequestFactory, TestCase

from .access import ACMAccess, ACMIdentity, policy_for
from .access_data import persist_history
from .access_models import ACMPortalAnalysis
from .components_engine import calculate, candidates, parameters
from .history_access import attach_authors, lookup_authors, visible_history
from .test_access import ROLES
from .test_components import params, sample
from . import components_views, portal_views


class HistoryVisibilityTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.params = parameters(params())
        self.records = candidates(sample(), self.params)
        self.result = calculate(self.records, self.params)
        self.author = ACMIdentity('178', 'joyzlis', 'Liz Joyce', 'Ramos León')
        self.foreign, _ = persist_history(self.author, self.params, self.records, self.result)
        self.own, _ = persist_history(ACMIdentity('77', 'agente'), self.params, self.records, self.result)
        self.catalog = patch('acm.access.role_catalog', return_value=ROLES)
        self.catalog.start()
        self.addCleanup(self.catalog.stop)

    def access(self, role=20, own=None, superuser=False):
        selected = next(r for r in ROLES if r['id'] == role)
        original = next(r for r in ROLES if r['id'] == (own or role))
        permissions, revision = policy_for(selected)
        return ACMAccess(ACMIdentity('77', 'adminpropify' if superuser else 'agente',
                                     is_superuser=superuser), original, selected, permissions, revision, '')

    def request(self, access=None, query='', post=False):
        request = self.factory.post('/acm/historial/') if post else self.factory.get('/acm/historial/'+query)
        request.session = {}
        request.acm_access = access or self.access()
        request.acm_identity = request.acm_access.user
        request._dont_enforce_csrf_checks = True
        return request

    def test_manager_and_verified_superadmin_see_all_and_creator_column(self):
        for access in (self.access(role=8), self.access(role=7, superuser=True)):
            request = self.request(access)
            self.assertEqual(visible_history(request).count(), 2)
            response = portal_views.history(request)
            self.assertContains(response, '<th scope="col">Usuario</th>', html=True)
            self.assertContains(response, 'joyzlis')
            self.assertContains(response, 'Liz Joyce Ramos León')
            self.assertContains(response, 'Todos los ACM')
            self.assertNotContains(response, f'{self.foreign.pk}/eliminar/')
            self.assertContains(portal_views.dashboard(request), '2</strong>')

    def test_agent_developer_and_non_superuser_administrator_stay_personal(self):
        for role in (20, 7, 18, 22):
            response = portal_views.history(self.request(self.access(role=role)))
            self.assertContains(response, self.own.codigo_display)
            self.assertNotContains(response, self.foreign.codigo_display)
            self.assertNotContains(response, 'joyzlis')
        access = self.access()
        access.own_role = access.role = dict(ROLES[2], id=12, name='Asistente de Gerencia')
        self.assertFalse(access.can_view_all_history)

    def test_preview_cannot_elevate_global_scope_and_basic_preview_is_personal(self):
        self.assertFalse(self.access(role=8, own=7).can_view_all_history)
        self.assertFalse(self.access(role=20, own=8).can_view_all_history)
        self.assertFalse(self.access(role=20, own=7, superuser=True).can_view_all_history)
        self.assertTrue(self.access(role=8, own=7, superuser=True).can_view_all_history)

    def test_explicit_history_and_report_restrictions_still_apply(self):
        access = self.access(role=8)
        access.permissions['history'] = False
        self.assertFalse(access.can_view_all_history)
        self.assertEqual(portal_views.history(self.request(access)).status_code, 403)
        self.assertEqual(components_views.history_pdf_report(self.request(access), self.foreign.pk).status_code, 403)
        access = self.access(role=8)
        access.permissions['reports'] = False
        self.assertEqual(components_views.history_pdf_report(self.request(access), self.foreign.pk).status_code, 403)

    def test_direct_foreign_access_denied_for_agent_and_delete_denied_for_manager(self):
        for view in (components_views.replicate_history, components_views.history_pdf_report,
                     components_views.history_word_report):
            with self.assertRaises(Http404):
                view(self.request(), self.foreign.pk)
        for access in (self.access(role=8), self.access(role=7, superuser=True)):
            with self.assertRaises(Http404):
                portal_views.delete_analysis(self.request(access, post=True), self.foreign.pk)
        self.assertTrue(ACMPortalAnalysis.objects.filter(pk=self.foreign.pk).exists())

    @patch('acm.components_views.page', return_value=HttpResponse('replicated'))
    def test_manager_can_replicate_foreign_analysis(self, page):
        self.assertEqual(components_views.replicate_history(self.request(self.access(role=8)), self.foreign.pk).status_code, 200)
        self.assertEqual(page.call_args.kwargs['replication']['code'], self.foreign.codigo_display)

    def test_downloads_preserve_original_creator_and_saved_date(self):
        for module, builder, view in (
            ('components_pdf', 'build_acm_pdf', components_views.history_pdf_report),
            ('components_report', 'build_acm_docx', components_views.history_word_report),
        ):
            with patch(f'acm.{module}.{builder}', return_value=b'report') as build:
                response = view(self.request(self.access(role=7, superuser=True)), self.foreign.pk)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(build.call_args.kwargs['user'].username, 'joyzlis')
                self.assertEqual(build.call_args.kwargs['generated_at'], self.foreign.created_at)

    @patch('acm.history_access.lookup_authors')
    def test_legacy_authors_resolved_in_one_batch_and_missing_account_has_label(self, lookup):
        lookup.return_value = {'178': self.author}
        rows = [SimpleNamespace(owner_id=owner, snapshot={}) for owner in ('178', '178', '999', '77')]
        attached = attach_authors(rows, ACMIdentity('77', 'agente'))
        lookup.assert_called_once_with({'178', '999'})
        self.assertEqual(attached[0].author.username, 'joyzlis')
        self.assertEqual(attached[2].author.username, 'Usuario 999')
        self.assertTrue(attached[3].is_own)

    def test_missing_directory_is_tolerated(self):
        self.assertEqual(lookup_authors({'178'}), {})

    def test_saved_author_does_not_change_deduplication(self):
        again, created = persist_history(ACMIdentity('178', 'nuevo_nombre'), self.params, self.records, self.result)
        self.assertFalse(created)
        self.assertEqual(again.pk, self.foreign.pk)
        self.assertEqual(again.snapshot['author']['username'], 'joyzlis')

    def test_creator_and_address_are_escaped(self):
        snapshot = self.foreign.snapshot
        snapshot['author']['username'] = '<script>author()</script>'
        snapshot['params']['address'] = '<script>address()</script>'
        self.foreign.save(update_fields=['snapshot'])
        response = portal_views.history(self.request(self.access(role=8)))
        self.assertContains(response, '&lt;script&gt;author()&lt;/script&gt;')
        self.assertNotContains(response, '<script>author()</script>')
        self.assertContains(response, '&lt;script&gt;address()&lt;/script&gt;')

    @patch('acm.portal_views.render', return_value=HttpResponse('ok'))
    def test_global_history_pagination(self, render):
        ACMPortalAnalysis.objects.bulk_create([
            ACMPortalAnalysis(owner_id='178', fingerprint=f'{i:064x}', snapshot=self.foreign.snapshot)
            for i in range(26)
        ])
        portal_views.history(self.request(self.access(role=8), '?page=2'))
        page = render.call_args.args[2]['history_page']
        self.assertEqual(page.paginator.count, 28)
        self.assertEqual(len(page.object_list), 3)
        self.assertTrue(all(row.author.username in ('joyzlis', 'agente') for row in page))
