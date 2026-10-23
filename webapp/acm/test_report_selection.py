import io
from types import SimpleNamespace
from unittest.mock import patch
from django.test import SimpleTestCase, override_settings
from .test_components import params, record, sample, _pdf_text
from .components_engine import candidates, calculate
from .components_pdf import build_acm_pdf, _static_map, _maps_key
from .report_selection import report_records, report_total, report_values, report_unit_price
from .components_html import build_acm_html


class ReportSelectionTests(SimpleTestCase):
    def test_html_contains_only_selected_records_and_manual_value(self):
        p=params();rows=candidates(sample(),p)
        selected=rows[0]
        selected['title']='Casa seleccionada <script>alert(1)</script>'
        selected['url']='javascript:alert(1)'
        for row in rows[1:]:
            row['title']='NO INCLUIR EN INFORME'
        result=calculate(rows,p)
        p.update(report_ids=[selected['id']],manual_valuation=234000)
        html=build_acm_html(p,rows,result)
        self.assertIn('USD 234,000',html)
        self.assertIn('USD 245,700',html)
        self.assertIn('USD 222,300',html)
        self.assertIn('Casa seleccionada &lt;script&gt;',html)
        self.assertNotIn('<script>',html)
        self.assertNotIn('javascript:',html)
        self.assertNotIn('NO INCLUIR EN INFORME',html)
        self.assertIn('ajuste por terreno',html)

    def test_html_supports_apartment_and_land_operations(self):
        for kind,area in [('Departamento','built'),('Terreno','land')]:
            p={**params(),'property_type':kind}
            rows=candidates([record('only',kind=kind,built=100 if kind=='Departamento' else None)],p)
            result=calculate(rows,p)
            p['report_ids']=['only']
            html=build_acm_html(p,rows,result)
            self.assertIn('Mediana del precio por m²',html)
            self.assertIn(f"{p[area]:,.0f} m²",html)
            self.assertIn('Ver anuncio',build_acm_html(p,[{**rows[0],'url':'https://example.com/propiedad'}],result))

    def test_only_checked_records_and_manual_total_are_reported(self):
        p=params();rows=candidates(sample(),p);p['report_ids']=[rows[0]['id']]
        self.assertEqual(report_records(p,rows),[rows[0]])
        self.assertEqual(report_records(p,rows,[rows[0]['id']]),[rows[0]])
        result=calculate(rows,p);p['manual_valuation']=234000
        self.assertEqual(report_total(p,result),234000)

    def test_pdf_uses_commercial_value_with_five_percent_market_limits(self):
        p={**params(),'property_type':'Departamento','land':0,'built':90,'radius':700}
        rows=[record('p1',kind='Departamento',price=79900,land=None,built=90,distance=624,issues=[]),
              record('p2',kind='Departamento',price=94476.74,land=None,built=87,distance=331,issues=[]),
              record('p3',kind='Departamento',price=72000,land=None,built=68,distance=657,issues=[])]
        result=calculate(rows,p)
        self.assertAlmostEqual(result['new']['total'],95294.11764705881)
        result['old']['total']=92479.83
        p['manual_valuation']=110000
        self.assertEqual(report_values(p,result),{'market_entry':115500,'commercial':110000,'immediate':104500})
        pdf=build_acm_pdf(p,rows,result,fetch_images=False)
        text=_pdf_text(pdf)
        self.assertNotIn(b'EXPECTATIVA CLIENTE',text)
        self.assertNotIn(b'92,479.83',text)
        self.assertNotIn(b'PRECIO DE VENTA SUGERIDO',text)
        self.assertIn(b'115,500',text)
        self.assertIn(b'110,000',text)
        self.assertIn(b'104,500',text)
        self.assertLess(text.index(b'VALOR DE SALIDA AL MERCADO'),text.index(b'VALOR COMERCIAL'))
        self.assertLess(text.index(b'VALOR COMERCIAL'),text.index(b'VALOR DE REALIZACI'))
        p.pop('manual_valuation')
        self.assertAlmostEqual(report_values(p,result)['commercial'],95294.11764705881)

    def test_report_unit_price_uses_the_final_value_and_correct_target_area(self):
        for kind,area_key in [('Casa','built'),('Departamento','built'),('Terreno','land')]:
            p={**params(),'property_type':kind,'land':200,'built':100,'manual_valuation':240000}
            result={'model':'land' if kind=='Terreno' else 'components','new':{'total':300000}}
            self.assertEqual(report_unit_price(p,result),240000/p[area_key])
            p.pop('manual_valuation');self.assertEqual(report_unit_price(p,result,1234),300000/p[area_key])
        self.assertIsNone(report_unit_price({'manual_valuation':100,'built':0},{'new':{}}))
        self.assertEqual(report_unit_price({'manual_valuation':100,'land':20,'built':100},{'new':{'area_basis':'land'}}),5)

    def test_land_report_uses_adopted_unit_instead_of_unweighted_comparable_average(self):
        from .client_report import prepare_report
        from .components_report import build_acm_docx
        from docx import Document
        p = {**params(), 'property_type': 'Terreno', 'land': 1212, 'built': 0}
        rows = candidates([record(str(i), 'Terreno', land=1212, price=unit*1212)
                           for i, unit in enumerate((600, 650, 1000))], p)
        result = calculate(rows, p)
        self.assertEqual(result['new']['total'], 787800)
        for adjusted, expected_total, expected_unit in ((False, 787800, 650), (True, 789012, 651)):
            with self.subTest(adjusted=adjusted):
                inputs = {**p, **({'manual_valuation': 789012} if adjusted else {})}
                data = prepare_report(inputs, rows, result, fetch_images=False)
                self.assertEqual(data['average'], expected_unit)
                self.assertEqual(data['values']['commercial'], expected_total)
                self.assertEqual(data['average'] * p['land'], expected_total)
                pdf = _pdf_text(build_acm_pdf(inputs, rows, result, fetch_images=False))
                self.assertIn(f'{expected_unit:,.0f}'.encode(), pdf)
                self.assertIn(f'{expected_total:,.0f}'.encode(), pdf)
                doc = Document(io.BytesIO(build_acm_docx(inputs, rows, result, fetch_images=False)))
                text = '\n'.join(cell.text for table in doc.tables for row in table.rows for cell in row.cells)
                self.assertIn(f'{expected_unit:,.0f}', text)
                self.assertIn(f'{expected_total:,.0f}', text)
                self.assertNotIn('Nuevo precio', text)

    def test_pdf_heading_and_chart_use_final_value_per_m2_without_adjustment_labels(self):
        p={**params(),'property_type':'Departamento','land':0,'built':90,'manual_valuation':110000}
        rows=[record('one',kind='Departamento',price=90000,land=None,built=90,distance=100,issues=[])]
        result=calculate(rows,p)
        with patch('acm.components_pdf._bar_chart',return_value=None) as chart:
            pdf=build_acm_pdf(p,rows,result,fetch_images=False)
        self.assertAlmostEqual(chart.call_args.args[2],110000/90)
        text=_pdf_text(pdf)
        self.assertIn(b'PRECIO PROMEDIO DE VENTA POR M2',text)
        self.assertIn(b'1,222',text)
        self.assertNotIn(b'Nuevo precio',text)
        self.assertNotIn(b'manualmente',text)

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

    def test_client_sheet_limits_the_location_map_and_cards_to_five_nearest_selected_properties(self):
        p=params()
        raw=[record(f'house-{i}',district=f'SELECTED-DISTRICT-{i}') for i in range(7)]+sample()[3:]
        rows=candidates(raw,p)
        p['report_ids']=[row['id'] for row in raw[:7]]
        with patch('acm.components_pdf._static_map',return_value=None) as maps, patch('acm.components_pdf._reverse_geocode',return_value='Cayma'):
            pdf=build_acm_pdf(p,rows,calculate(rows,p),fetch_images=True)
        self.assertEqual(maps.call_count,1)
        self.assertEqual(len(maps.call_args.args[1]),6)
        text=_pdf_text(pdf)
        for i in range(5):
            self.assertIn(f'SELECTED-DISTRICT-{i}'.encode(),text)
        for i in range(5,7):
            self.assertNotIn(f'SELECTED-DISTRICT-{i}'.encode(),text)


class SelectedReportEndpointTests(SimpleTestCase):
    def setUp(self):
        from django.test import RequestFactory
        self.factory=RequestFactory();self.user=SimpleNamespace(pk=1,is_active=True,is_authenticated=True)
        from .test_access_helpers import install_propify_fixture
        install_propify_fixture(self)

    def request(self,data):
        import json
        request=self.factory.post('/',json.dumps(data),content_type='application/json')
        request.current_user=self.user;request._dont_enforce_csrf_checks=True
        return request

    @patch('acm.components_views._persist_history')
    @patch('acm.components_views.load_records')
    def test_html_download_uses_signed_selection_and_rejects_invalid_requests(self,load,persist):
        import json
        from django.urls import reverse
        from .components_views import search,html_report
        self.assertEqual(reverse('acm:componentes_informe_html'),'/acm/componentes/informe-html/')
        p=params();load.return_value=(candidates(sample(),p),[])
        persist.return_value=(SimpleNamespace(codigo_display='ACM-html-test'),True)
        snapshot=json.loads(search(self.request(p)).content)
        selected=[snapshot['records'][0]['id']]
        response=html_report(self.request({'token':snapshot['token'],'report_ids':selected,'manual_valuation':234000}))
        self.assertEqual(response.status_code,200)
        self.assertEqual(response['Content-Type'],'text/html; charset=utf-8')
        self.assertIn('attachment',response['Content-Disposition'])
        self.assertEqual(response['X-ACM-History-Code'],'ACM-html-test')
        self.assertIn(b'USD 234,000',response.content)
        self.assertEqual(persist.call_args.args[1]['report_ids'],[sample()[0]['id']])
        for payload,status in [({'token':snapshot['token'],'report_ids':[]},422),
                               ({'token':snapshot['token'],'report_ids':['foreign']},400),
                               ({'token':'tampered'},400)]:
            self.assertEqual(html_report(self.request(payload)).status_code,status)
        request=self.request({'token':snapshot['token']});request.current_user=None
        self.assertEqual(html_report(request).status_code,401)
        request=self.request({'token':snapshot['token']});request._dont_enforce_csrf_checks=False
        self.assertEqual(html_report(request).status_code,403)

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
        response=pdf_report(self.request({'token':snapshot['token'],'report_ids':selected,
            'manual_valuation':234000,'report_notes':'Conservación revisada.'}))
        self.assertEqual(response.status_code,200)
        self.assertEqual(build.call_args.args[0]['report_ids'],selected)
        self.assertEqual(build.call_args.args[0]['manual_valuation'],234000)
        self.assertEqual(pdf_report(self.request({'token':snapshot['token'],'report_ids':[]})).status_code,422)
        self.assertEqual(pdf_report(self.request({'token':snapshot['token'],'report_ids':['foreign']})).status_code,400)
        self.assertEqual(pdf_report(self.request({'token':snapshot['token'],'manual_valuation':'nan'})).status_code,400)
