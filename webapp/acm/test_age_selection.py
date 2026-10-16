import json
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch
from django.core.cache import cache
from django.test import SimpleTestCase, RequestFactory
from .comparable_policy import age_years, priority, selection_metrics
from .components_engine import parameters, candidates, calculate
from .components_ai import propose_result
from .components_views import search, explain_ai, recalculate, load_records
from .test_components import params, record


def at(key, meters, **kwargs):
    kwargs.setdefault('built', 200 if kwargs.get('kind', 'Casa') != 'Terreno' else None)
    return record(key, lat=-16.4+meters/111195, **kwargs)


class AgeSelectionTests(SimpleTestCase):
    def test_optional_age_keeps_distance_and_zero_is_not_missing(self):
        for raw in (None, ''):
            p=parameters({**params(), 'age':raw})
            self.assertIsNone(p['age'])
            rows=candidates([at('near',30,age=25),at('new',250,age=0),record('soil','Terreno',price=150000)],p)
            self.assertEqual(calculate(rows,p)['recommended_ids'],['near'])
        self.assertEqual(parameters({**params(),'age':'0'})['age'],0)

    def test_invalid_age_and_land_ignore(self):
        for raw in ('nan','inf',-1,151,1.5,True):
            with self.subTest(age=raw),self.assertRaises(ValueError):
                parameters({**params(),'age':raw})
        self.assertIsNone(parameters({**params(),'property_type':'Terreno','age':100})['age'])

    def test_two_nearby_complete_houses_use_both_adjusted_values(self):
        p=parameters(params())
        rows=candidates([at('a',20,price=350000),at('b',40,price=370000),
                         at('far',250,price=600000),record('soil','Terreno',price=150000)],p)
        r=calculate(rows,p)
        self.assertEqual(r['recommended_ids'],['a','b'])
        self.assertAlmostEqual(r['new']['total'],360000)
        details={d['id']:d for d in r['breakdown']}
        self.assertEqual(details['a']['similarity_weight'],50)
        self.assertEqual(details['b']['similarity_weight'],50)
        self.assertFalse(details['far']['usable'])
        self.assertEqual(calculate(rows,p,['a'])['recommended_ids'],['b'])

    def test_nearby_bad_surfaces_and_extreme_price_do_not_join_group(self):
        p=parameters(params())
        rows=candidates([at('a',20),at('size',21,built=110),at('extreme',22,price=5000000),
                         record('soil','Terreno',price=150000)],p)
        self.assertEqual(calculate(rows,p)['recommended_ids'],['a'])

    def test_three_is_an_automatic_cap(self):
        p=parameters(params())
        rows=candidates([at(str(i),20+i*5,price=350000+i*1000) for i in range(5)]+
                        [record('soil','Terreno',price=150000)],p)
        self.assertEqual(calculate(rows,p)['recommended_ids'],['0','1','2'])

    def test_two_close_apartments_do_not_need_a_distant_third(self):
        p=parameters({**params(),'property_type':'Departamento'})
        rows=candidates([at('a',20,kind='Departamento',price=300000),
                         at('b',40,kind='Departamento',price=320000),
                         at('far',450,kind='Departamento',price=500000)],p)
        r=calculate(rows,p)
        self.assertEqual(r['house_ids'],['a','b'])
        self.assertEqual(r['new']['total'],310000)

    def test_age_and_distance_jointly_rank_apartments(self):
        p=parameters({**params(),'property_type':'Departamento','age':20})
        rows=candidates([at('exact-far',450,kind='Departamento',age=20),
                         at('near-similar',120,kind='Departamento',age=19),
                         at('near-different',80,kind='Departamento',age=5)],p)
        r=calculate(rows,p)
        self.assertEqual(r['house_ids'][0],'near-similar')
        self.assertEqual(r['selection_method'],'age_proximity')

    def test_premieres_precede_young_properties_and_do_not_fill_quota(self):
        p=parameters({**params(),'property_type':'Departamento','age':0})
        rows=candidates([at('new',450,kind='Departamento',age=0),
                         at('young',20,kind='Departamento',age=1),
                         at('unknown',10,kind='Departamento')],p)
        r=calculate(rows,p)
        self.assertEqual(r['house_ids'],['new'])
        self.assertTrue(next(row for row in rows if row['id']=='unknown')['issues'])

    def test_no_premieres_uses_age_proximity_and_warns(self):
        p=parameters({**params(),'property_type':'Departamento','age':0})
        rows=candidates([at('young',120,kind='Departamento',age=2),
                         at('old',100,kind='Departamento',age=20)],p)
        r=calculate(rows,p)
        self.assertEqual(r['house_ids'][0],'young')
        self.assertTrue(any('No se encontraron estrenos' in m for m in r['messages']))

    def test_unknown_and_conflicted_age_never_become_premieres(self):
        p=parameters({**params(),'age':0})
        rows=candidates([at('unknown',20),at('conflict',30,age=0,age_conflict='conflicting_age_values'),
                         record('soil','Terreno',price=150000)],p)
        self.assertIsNone(calculate(rows,p)['new'])
        self.assertTrue(all(r['issues'] for r in rows if r['kind']=='Casa'))

    def test_radius_does_not_rescale_selection_score(self):
        row=record('a',distance=200,age=19)
        p=parameters({**params(),'age':20})
        self.assertEqual(selection_metrics(row,p),selection_metrics(row,{**p,'radius':1000}))

    def test_house_41_uses_only_terrain_but_40_still_uses_construction(self):
        for age, expected in ((40,'components'),(41,'land')):
            p=parameters({**params(),'age':age,'built':200 if age==40 else ''})
            rows=candidates([at('house',20,age=age),record('soil','Terreno',price=150000)],p)
            r=calculate(rows,p)
            self.assertEqual(r['model'],expected)
            if age==41:
                self.assertEqual(r['new']['total'],150000)
                self.assertEqual(r['new']['built_value'],0)
                self.assertEqual(r['new']['area_basis'],'land')
                self.assertEqual(r['house_ids'],[])
                self.assertEqual(r['property_type'],'Casa')
                self.assertEqual(r['valuation_mode'],'land_only')

    def test_old_apartment_and_office_still_need_built_area(self):
        for target in ('Departamento','Oficina'):
            with self.assertRaises(ValueError):parameters({**params(),'property_type':target,'age':50,'built':''})
            p=parameters({**params(),'property_type':target,'age':50})
            r=calculate(candidates([at('a',20,kind=target,age=50)],p),p)
            self.assertEqual(r['new']['area_basis'],'built')

    def test_incomplete_age_is_not_filled_into_selected_department_group(self):
        p=parameters({**params(),'property_type':'Departamento','age':20})
        rows=candidates([at('a',40,kind='Departamento',age=20),
                         at('no-age',20,kind='Departamento')],p)
        self.assertEqual(calculate(rows,p)['house_ids'],['a'])

    @patch('acm.components_views.bounded_propify_rows',side_effect=TimeoutError)
    @patch('acm.components_views.scraped_rows')
    def test_slow_external_source_returns_explicit_partial_results(self, portals, remote):
        p=parameters(params())
        portals.return_value=[at('a',40)]
        rows,warnings=load_records(p)
        self.assertEqual([r['id'] for r in rows],['a'])
        self.assertTrue(any('resultado parcial' in message for message in warnings))


class AIIncompleteReferenceTests(SimpleTestCase):
    def setUp(self):
        from .test_access_helpers import install_propify_fixture
        install_propify_fixture(self)
        cache.clear()
        self.p=parameters({**params(),'age':20})
        self.rows=candidates([at('a',20,age=20),at('review',30,age=20,built=None),
                              record('soil','Terreno',price=150000)],self.p)
        self.r=calculate(self.rows,self.p)

    def invoke(self, body):
        api=Mock(return_value=(True,'OK',{'content':json.dumps(body)}))
        service=SimpleNamespace(LLMService=SimpleNamespace(_call_deepseek_api=api))
        with patch.dict(sys.modules,{'intelligence.services.llm':service}):
            return propose_result('age-agent',self.p,self.rows,self.r,[]),api

    def test_review_can_be_recommended_without_entering_calculation(self):
        proposal,api=self.invoke({'ids':['a'],'revisar':[{'id':'review','motivo':'Cercana y de edad similar; completar construcción.'}],
                                 'justificacion':'Usar la completa y revisar la otra.'})
        self.assertEqual(proposal['ids'],['a'])
        self.assertEqual(proposal['reviews'][0]['id'],'review')
        self.assertIn('Falta área construida',proposal['reviews'][0]['missing'])
        self.assertNotIn('review',self.r['recommended_ids'])
        data=json.loads(api.call_args.kwargs['messages'][0]['content'])
        self.assertEqual(data['referencias_para_revisar'][0]['id'],'review')

    def test_ai_cannot_put_incomplete_id_into_ready_selection(self):
        with self.assertRaises(RuntimeError):
            self.invoke({'ids':['review'],'justificacion':'Inventar el metraje.'})

    def test_only_review_recommendations_are_allowed(self):
        proposal,_=self.invoke({'ids':[], 'revisar':[{'id':'review','motivo':'Completar construcción.'}],
                               'justificacion':'Solo recomendación para revisión.'})
        self.assertEqual(proposal['ids'],[])
        self.assertEqual(len(proposal['reviews']),1)

    def request(self,data):
        request=RequestFactory().post('/',json.dumps(data),content_type='application/json')
        request.current_user=SimpleNamespace(pk=1,is_active=True,is_authenticated=True)
        request._dont_enforce_csrf_checks=True
        return request

    def test_signed_review_is_retained_but_cannot_override_valuation(self):
        review={'id':'review','reason':'Completar construcción.','missing':['Falta área construida']}
        with patch('acm.components_views.load_records',return_value=(self.rows,[])):
            token=json.loads(search(self.request(self.p)).content)['token']
        with patch('acm.components_ai.propose_result',return_value={'ids':[],'reviews':[review],'explanation':'Revisar','omitted':0}):
            response=explain_ai(self.request({'token':token}))
        self.assertEqual(response.status_code,200)
        body=json.loads(response.content)
        self.assertEqual(body['proposal']['ids'],[])
        r=json.loads(recalculate(self.request({'token':body['current_token']})).content)
        self.assertEqual(r['result']['new']['total'],self.r['new']['total'])
        from .access_data import opaque_id
        request=self.request({})
        from .access import get_access
        get_access(request)
        self.assertEqual(r['params']['ai_review_recommendations'],[{**review,'id':opaque_id(request,'review')}])

    def test_retired_or_review_excluded_reference_never_recommended(self):
        for key,value in (('state','retirada'),('review_excluded',True)):
            self.rows[1][key]=value
            with self.assertRaises(RuntimeError):
                self.invoke({'ids':[], 'revisar':[{'id':'review','motivo':'Completar.'}], 'justificacion':'Revisar'})
            self.rows[1].update(state='activa',review_excluded=False)

    def test_reviews_are_available_when_no_complete_house_can_be_valued(self):
        rows=[r for r in self.rows if r['id']!='a']
        review={'id':'review','reason':'Completar construcción.','missing':['Falta área construida']}
        with patch('acm.components_views.load_records',return_value=(rows,[])):
            token=json.loads(search(self.request(self.p)).content)['token']
        with patch('acm.components_ai.propose_result',return_value={'ids':[],'reviews':[review],'explanation':'Revisar','omitted':0}):
            response=explain_ai(self.request({'token':token}))
        self.assertEqual(response.status_code,200)
        self.assertIsNone(json.loads(response.content)['proposal']['result']['new'])
