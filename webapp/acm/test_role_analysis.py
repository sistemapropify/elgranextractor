import copy
import json
from urllib.parse import urlsplit, parse_qs
from unittest.mock import patch

from django.core import signing
from django.core.exceptions import PermissionDenied
from django.test import TestCase, RequestFactory

from .access import ACMAccess, ACMIdentity, policy_for
from .access_data import issue_snapshot, read_snapshot, opaque_id, unseal
from .access_models import ACMPortalAnalysis, ACMRolePolicy
from .components_engine import candidates, parameters
from .portal_views import perspective
from .role_analysis import SESSION_ANALYSIS, resume_analysis
from .test_access import ROLES
from .test_components import params, sample


class RoleAnalysisTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.session = {}
        self.p = parameters(params())
        self.rows = candidates(sample(), self.p)
        self.rows[0].update(source='remax', title='Original source property',
                            url='https://remax.pe/example', description='Original description')
        self.state = dict(user='77', params=self.p, records=self.rows, warnings=[])

    def access(self, role=18, owner='77'):
        selected = next(r for r in ROLES if r['id'] == role)
        own = ROLES[0]
        flags, revision = policy_for(selected)
        nonce = self.session.get('acm_role_perspective', {}).get('nonce', '')
        return ACMAccess(ACMIdentity(owner, 'fixture'), own, selected, flags, revision, nonce)

    def request(self, role=18, data=None, key=None, owner='77'):
        request = self.factory.post('/acm/vista-por-rol/', data) if data is not None else self.factory.get('/acm/analisis/', {'analysis_view':key} if key else {})
        request.session = self.session
        request.acm_access = self.access(role, owner)
        request.acm_identity = request.acm_access.user
        request._dont_enforce_csrf_checks = True
        return request

    def selection(self):
        request = self.request()
        return {'token': issue_snapshot(request, self.state),
                'excluded':[opaque_id(request, self.rows[-1]['id'])],
                'report_ids':[opaque_id(request, self.rows[0]['id'])],
                'manual_valuation':234567.89, 'report_notes':'Conservacion y ubicacion.',
                'ui':{'hidden_ids':[opaque_id(request, self.rows[1]['id'])],
                      'layers':['property','property_reference'],
                      'viewport':{'lat':-16.4,'lng':-71.5,'zoom':17}}}

    def switch(self, role_id=20, selection=None, key=None, source_role=18):
        data = {'role_id':role_id}
        if selection is not None:
            data['analysis_selection'] = json.dumps(selection)
        if key:
            data['analysis_view'] = key
        with patch('acm.access.role_catalog', return_value=ROLES):
            return perspective(self.request(role=source_role, data=data))

    def key(self, response):
        self.assertEqual(response.status_code, 302, response.content)
        return parse_qs(urlsplit(response.url).query)['analysis_view'][0]

    def test_switch_preserves_sample_adjustment_notes_selection_and_viewport(self):
        selection = self.selection()
        with patch('acm.components_views.load_records') as search:
            key = self.key(self.switch(selection=selection))
            request = self.request(role=20, key=key)
            resumed = resume_analysis(request)
        search.assert_not_called()
        snapshot = resumed['snapshot']
        self.assertEqual(len(snapshot['records']), len(self.rows))
        self.assertEqual(snapshot['params']['manual_valuation'],234567.89)
        self.assertEqual(snapshot['params']['report_notes'],'Conservacion y ubicacion.')
        self.assertEqual(snapshot['params']['report_ids'],selection['report_ids'])
        self.assertEqual(resumed['excluded'],selection['excluded'])
        self.assertEqual(resumed['ui']['hidden_ids'],selection['ui']['hidden_ids'])
        self.assertEqual(resumed['ui']['viewport'],selection['ui']['viewport'])
        self.assertEqual(ACMPortalAnalysis.objects.count(),0)
        raw = read_snapshot(request,snapshot['token'])
        self.assertEqual(raw['records'][0]['source'],'remax')
        self.assertEqual(raw['user'],'77')

    def test_basic_result_hides_origin_but_returning_to_admin_restores_it(self):
        key = self.key(self.switch(selection=self.selection()))
        basic = resume_analysis(self.request(role=20,key=key))['snapshot']
        self.assertEqual(basic['records'][0]['source'],'comparable')
        self.assertEqual(basic['records'][0]['url'],'')
        self.assertNotIn('remax',json.dumps(basic['records']).lower())
        key = self.key(self.switch(role_id=0,key=key,source_role=20))
        own = resume_analysis(self.request(key=key))['snapshot']
        self.assertEqual(own['records'][0]['source'],'remax')
        self.assertEqual(own['records'][0]['url'],'https://remax.pe/example')

    def test_role_without_results_receives_no_property_data_and_can_return(self):
        ACMRolePolicy.objects.create(role_id=20,permissions={'property_data':False},updated_by='77')
        key = self.key(self.switch(selection=self.selection()))
        self.assertEqual(resume_analysis(self.request(role=20,key=key)),{'blocked':True})
        key = self.key(self.switch(role_id=0,key=key,source_role=20))
        self.assertEqual(len(resume_analysis(self.request(key=key))['snapshot']['records']),len(self.rows))

    def test_saved_analysis_is_private_and_owner_bound(self):
        key = self.key(self.switch(selection=self.selection()))
        self.assertNotIn('remax',json.dumps(self.session[SESSION_ANALYSIS]).lower())
        self.assertEqual(resume_analysis(self.request(role=20,key=key,owner='88')),{'unavailable':True})

    def test_another_browser_without_handoff_cannot_load_analysis(self):
        key = self.key(self.switch(selection=self.selection()))
        self.session = {}
        self.assertEqual(resume_analysis(self.request(key=key)),{'unavailable':True})

    def test_invalid_or_stale_token_cannot_switch_role(self):
        selection = self.selection()
        selection['token'] = 'invalid'
        self.assertEqual(self.switch(selection=selection).status_code,409)
        self.assertNotIn('acm_role_perspective',self.session)
        self.assertNotIn(SESSION_ANALYSIS,self.session)

    def test_ordinary_role_cannot_switch_even_with_a_valid_snapshot(self):
        request = self.request(data={'role_id':18})
        request.acm_access.own_role = ROLES[3]
        request.acm_access.role = ROLES[3]
        with self.assertRaises(PermissionDenied):
            perspective(request)

    def test_new_analysis_page_does_not_automatically_reopen_old_result(self):
        self.key(self.switch(selection=self.selection()))
        self.assertIsNone(resume_analysis(self.request()))

    @patch('acm.access.role_catalog', return_value=ROLES)
    def test_new_role_page_embeds_projected_results_and_keeps_role_form(self, catalog):
        from .components_views import page
        key = self.key(self.switch(selection=self.selection()))
        response = page(self.request(role=20, key=key))
        self.assertEqual(response.status_code,200)
        html = response.content.decode()
        self.assertIn('id="acm-perspective-form"',html)
        self.assertIn('id="cmp-role-analysis-data"',html)
        self.assertIn('components.js?v=66',html)
        import re
        payload = json.loads(re.search(r'id="cmp-role-analysis-data"[^>]*>(.*?)</script>',html,re.S)[1])
        self.assertEqual(payload['snapshot']['records'][0]['source'],'comparable')
        self.assertNotIn('remax',json.dumps(payload['snapshot']['records']).lower())
