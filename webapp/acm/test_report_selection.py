import io
from types import SimpleNamespace
from unittest.mock import patch
from django.test import SimpleTestCase, override_settings
from .test_components import params, record, sample, _pdf_text
from .components_engine import candidates, calculate
from .components_pdf import build_acm_pdf, _static_map, _maps_key
from .report_selection import report_records, report_total


class ReportSelectionTests(SimpleTestCase):
    def test_only_checked_records_and_manual_total_are_reported(self):
        p=params();rows=candidates(sample(),p);p['report_ids']=[rows[0]['id']]
        self.assertEqual(report_records(p,rows),[rows[0]])
        self.assertEqual(report_records(p,rows,[rows[0]['id']]),[rows[0]])
        result=calculate(rows,p);p['manual_valuation']=234000
        self.assertEqual(report_total(p,result),234000)

    def test_pdf_does_not_include_property_codes_or_unchecked_properties(self):
        p=params();raw=sample()
        for i,row in enumerate(raw):
            row['code']='PRIVATE-CODE-'+str(i)
            row['district']='ONLY-SELECTED' if i==0 else 'NOT-SELECTED-'+str(i)
        rows=candidates(raw,p);p['report_ids']=[raw[0]['id']];p['manual_valuation']=234000
        pdf=build_acm_pdf(p,rows,calculate(rows,p),fetch_images=False)
        text=_pdf_text(pdf)
        self.assertNotIn(b'PRIVATE-CODE',text)
        self.assertNotIn(b'NOT-SELECTED',text)
        self.assertIn(b'ONLY-SELECTED',text)
        self.assertIn(b'234,000',text)

    @override_settings(GOOGLE_MAPS_STATIC_API_KEY='static-server-key')
    def test_static_key_is_separate_and_size_respects_google_limit(self):
        self.assertEqual(_maps_key(),'static-server-key')
        response=SimpleNamespace(status_code=200,content=b'image',headers={'Content-Type':'image/png'})
        with patch('requests.get',return_value=response) as get:
            self.assertEqual(_static_map((-16.4,-71.5),[],'static-server-key',size=(700,460)),b'image')
        self.assertEqual(get.call_args.kwargs['params']['size'],'640x460')

    def test_map_can_recover_after_previous_errors(self):
        bad=SimpleNamespace(status_code=403,content=b'API disabled',headers={'Content-Type':'text/plain'})
        good=SimpleNamespace(status_code=200,content=b'png',headers={'Content-Type':'image/png'})
        with patch('requests.get',side_effect=[bad,bad,good]):
            self.assertIsNone(_static_map((-16.4,-71.5),[],'test'))
            self.assertIsNone(_static_map((-16.4,-71.5),[],'test'))
            self.assertEqual(_static_map((-16.4,-71.5),[],'test'),b'png')

    def test_every_selected_property_gets_a_location_map_and_is_printed(self):
        p=params()
        raw=[record(f'house-{i}',district=f'SELECTED-DISTRICT-{i}') for i in range(7)]+sample()[3:]
        rows=candidates(raw,p)
        p['report_ids']=[row['id'] for row in raw[:7]]
        with patch('acm.components_pdf._static_map',return_value=None) as maps, patch('acm.components_pdf._reverse_geocode',return_value='Cayma'):
            pdf=build_acm_pdf(p,rows,calculate(rows,p),fetch_images=True)
        self.assertEqual(sum(call.kwargs.get('size')==(320,240) for call in maps.call_args_list),7)
        text=_pdf_text(pdf)
        for i in range(7):
            self.assertIn(f'SELECTED-DISTRICT-{i}'.encode(),text)


class SelectedReportEndpointTests(SimpleTestCase):
    def setUp(self):
        from django.test import RequestFactory
        self.factory=RequestFactory();self.user=SimpleNamespace(pk=1,is_active=True,is_authenticated=True)

    def request(self,data):
        import json
        request=self.factory.post('/',json.dumps(data),content_type='application/json')
        request.current_user=self.user;request._dont_enforce_csrf_checks=True
        return request

    @patch('acm.components_views._persist_history')
    @patch('acm.components_pdf.build_acm_pdf',return_value=b'%PDF-selection')
    @patch('acm.components_views.load_records')
    def test_selected_ids_and_manual_value_reach_report(self,load,build,persist):
        import json
        from .components_views import search,pdf_report
        p=params();load.return_value=(candidates(sample(),p),[])
        persist.return_value=(SimpleNamespace(codigo_display='ACM-test'),True)
        snapshot=json.loads(search(self.request(p)).content)
        selected=[snapshot['records'][0]['id']]
        response=pdf_report(self.request({'token':snapshot['token'],'report_ids':selected,'manual_valuation':234000}))
        self.assertEqual(response.status_code,200)
        self.assertEqual(build.call_args.args[0]['report_ids'],selected)
        self.assertEqual(build.call_args.args[0]['manual_valuation'],234000)
        self.assertEqual(pdf_report(self.request({'token':snapshot['token'],'report_ids':[]})).status_code,422)
        self.assertEqual(pdf_report(self.request({'token':snapshot['token'],'report_ids':['foreign']})).status_code,400)
        self.assertEqual(pdf_report(self.request({'token':snapshot['token'],'manual_valuation':'nan'})).status_code,400)
