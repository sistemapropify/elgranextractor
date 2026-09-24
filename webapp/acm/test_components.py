import json
from types import SimpleNamespace
from unittest.mock import patch
from django.test import SimpleTestCase, TestCase, RequestFactory
from django.urls import resolve, reverse
from acm.components_engine import parameters,candidates,calculate,old_estimate
from acm.components_views import search,recalculate,page,scraped_rows,propify_rows


def params():
    return {'lat':-16.4,'lng':-71.5,'radius':500,'max_radius':2000,'land':150,'built':200,'sources':['remax','propify']}


def record(key,kind='Casa',**kwargs):
    return {'id':key,'source':'remax','code':key,'kind':kind,'price':350000 if kind=='Casa' else 300000,
            'land':150,'built':200 if kind=='Casa' else None,'lat':-16.4,'lng':-71.5,
            'precision':'exacta','state':'activa','operation':'Venta','title':'Inmueble','district':'Cayma',
            'url':'','image':'','converted':False,**kwargs}


def sample():
    return [record('a'),record('b',price=320000,built=150),record('c',price=340000,lat=-16.399)]+[
        record(f'l{i}','Terreno',lat=-16.402-i*.0001) for i in range(5)]


class ComponentsEngineTests(SimpleTestCase):
    def test_three_lands_produce_house_breakdown_and_estimate(self):
        raw=sample()[:6]
        result=calculate(candidates(raw,params()),params())
        self.assertEqual(result['land_count'],3)
        self.assertEqual(result['status'],'ok')
        self.assertEqual(result['new']['total'],340000)
        self.assertEqual(len(result['breakdown']),3)
        self.assertTrue(any('Muestra reducida' in m for m in result['messages']))

    def test_nonpositive_house_does_not_block_three_valid_houses(self):
        raw=sample()+[record('bad',price=100000)]
        result=calculate(candidates(raw,params()),params())
        self.assertEqual(result['status'],'ok')
        self.assertEqual(result['new']['total'],340000)
        self.assertEqual(result['usable_house_count'],3)
        self.assertFalse(next(r for r in result['breakdown'] if r['id']=='bad')['usable'])
    def test_land_target_needs_no_construction_and_stays_in_selected_radius(self):
        p=parameters({**params(),'property_type':'Terreno','built':0})
        rows=candidates(sample(),p)
        result=calculate(rows,p)
        self.assertEqual({r['kind'] for r in rows},{'Terreno'})
        self.assertEqual(result['new']['total'],300000)
        self.assertEqual(result['model'],'land')

    def test_office_and_apartment_do_not_require_land(self):
        for target in ('Oficina','Departamento'):
            p=parameters({**params(),'property_type':target,'land':0,'built':100})
            rows=candidates([record(str(i),kind=target,land=None,built=100,price=price) for i,price in enumerate([100000,110000,120000])],p)
            result=calculate(rows,p)
            self.assertEqual(result['model'],'built')
            self.assertEqual(result['new']['total'],110000)
            self.assertEqual(len(result['breakdown']),3)

    def test_rooms_baths_filter_and_missing_data_visible(self):
        p=parameters({**params(),'rooms':3,'baths':2})
        rows=candidates([record('match',rooms=3,baths=2),record('missing'),record('different',rooms=4,baths=2)],p)
        by_id={r['id']:r for r in rows}
        self.assertFalse(by_id['match']['issues'])
        self.assertTrue(by_id['missing']['issues'])
        self.assertTrue(by_id['different']['issues'])

    def test_user_example_separates_300000_land(self):
        result=calculate(candidates(sample(),params()),params())
        self.assertEqual(result['status'],'ok')
        self.assertEqual(result['land_unit'],2000)
        by_id={r['id']:r for r in result['breakdown']}
        self.assertEqual(by_id['a']['land_value'],300000)
        self.assertEqual(by_id['a']['land_unit'],2000)
        self.assertEqual(by_id['a']['remainder'],50000)
        self.assertEqual(by_id['a']['built_unit'],250)
        self.assertEqual(by_id['b']['remainder'],20000)
        self.assertAlmostEqual(by_id['b']['built_unit'],133.3333333)
        self.assertEqual(result['new']['total'],340000)

    def test_changing_land_selection_updates_every_house_breakdown(self):
        raw=sample()+[record('extra','Terreno',price=180000)]
        raw[-2]['price']=180000
        raw[-3]['price']=180000
        rows=candidates(raw,params())
        before=calculate(rows,params())
        after=calculate(rows,params(),['extra'])
        self.assertEqual(before['land_unit'],1600)
        self.assertEqual(after['land_unit'],2000)
        self.assertEqual(len(after['breakdown']),3)
        for b in after['breakdown']:
            old=next(r for r in before['breakdown'] if r['id']==b['id'])
            self.assertEqual(b['land_unit'],2000)
            self.assertNotEqual(b['remainder'],old['remainder'])
            self.assertAlmostEqual(b['land_value']+b['remainder'],b['price'])

    def test_previous_formula_exact(self):
        value=old_estimate([{'price':350000,'built':200,'distance':0},{'price':320000,'built':150,'distance':100}],200)
        expected=((1750/2+(320000/150)/101)/(1/2+1/101))*200
        self.assertAlmostEqual(value['total'],expected)

    def test_incomplete_visible_but_never_computed(self):
        rows=candidates(sample()+[record('incomplete',land=None,price=9999999)],params())
        bad=next(r for r in rows if r['id']=='incomplete')
        self.assertIn('Falta área de terreno',bad['issues'])
        result=calculate(rows,params())
        self.assertNotIn('incomplete',result['house_ids'])
        self.assertEqual(result['old']['houses'],3)

    def test_expand_lands_only_in_500m_steps(self):
        raw=[record('near')]+[record(f'l{i}','Terreno',lat=-16.406-i*.0001) for i in range(5)]+[record('far',lat=-16.406)]
        rows=candidates(raw,params());result=calculate(rows,params())
        self.assertNotIn('far',[r['id'] for r in rows])
        self.assertEqual(result['land_radius'],1000)
        self.assertEqual(result['land_count'],5)

    def test_exclusion_recalculates_both(self):
        rows=candidates(sample(),params());full=calculate(rows,params());less=calculate(rows,params(),['a'])
        self.assertNotEqual(full['old']['total'],less['old']['total'])
        self.assertIsNotNone(less['new']);self.assertEqual(less['house_count'],2)

    def test_negative_remainder_is_not_clipped_and_other_houses_calculate(self):
        raw=sample();raw[0]['price']=250000
        result=calculate(candidates(raw,params()),params())
        self.assertIsNotNone(result['new'])
        self.assertTrue(any(r['remainder']<0 for r in result['breakdown']))

    def test_one_land_and_one_house_calculate(self):
        result=calculate(candidates([record('house'),record('land','Terreno')],params()),params())
        self.assertEqual(result['new']['total'],350000)
        self.assertEqual(result['land_radius'],500)
        self.assertTrue(any('Muestra reducida' in m for m in result['messages']))

    def test_dispersion_warns_instead_of_blocking(self):
        raw=[record('house',price=3000000)]+[record(str(i),'Terreno',price=price) for i,price in enumerate([15000,30000,45000,1500000,1650000])]
        result=calculate(candidates(raw,params()),params())
        self.assertGreater(result['land_dispersion'],1)
        self.assertIsNotNone(result['new'])

    def test_no_land_never_invents_land_value(self):
        result=calculate(candidates([record('house')],params()),params())
        self.assertIsNone(result['land_unit'])
        self.assertIsNone(result['new'])

    def test_single_comparable_for_other_types(self):
        for target in ('Terreno','Departamento','Oficina'):
            p=parameters({**params(),'property_type':target})
            r=record('only',kind=target,built=None if target=='Terreno' else 200)
            result=calculate(candidates([r],p),p)
            self.assertEqual(result['status'],'ok')

    def test_exact_location_required_for_calculation(self):
        raw=sample();raw[0]['precision']='aproximada'
        rows=candidates(raw,params())
        self.assertIn('Ubicación no exacta',next(r for r in rows if r['id']=='a')['issues'])

    def test_propify_and_remax_duplicate_count_once(self):
        raw=sample()+[record('propify-a',source='propify')]
        rows=candidates(raw,params())
        duplicate=next(r for r in rows if r['id']=='a')
        self.assertEqual(duplicate['duplicate_of'],'propify-a')
        self.assertEqual(calculate(rows,params())['house_count'],3)

    def test_terrain_with_construction_is_not_bare_land(self):
        rows=candidates([record('l','Terreno',built=100)],params())
        self.assertTrue(rows[0]['issues'])

    def test_invalid_parameters_and_currency_are_not_guessed(self):
        for key,value in [('lat',float('nan')),('radius',-1),('land',0),('built',None)]:
            with self.subTest(key=key),self.assertRaises(ValueError):parameters({**params(),key:value})


class ComponentsEndpointTests(SimpleTestCase):
    def setUp(self):
        self.factory=RequestFactory();self.user=SimpleNamespace(pk=1,is_active=True,is_authenticated=True)

    def request(self,data):
        req=self.factory.post('/',json.dumps(data),content_type='application/json');req.current_user=self.user
        req._dont_enforce_csrf_checks=True
        return req

    def test_anonymous_and_csrf_denied(self):
        req=self.factory.post('/',json.dumps(params()),content_type='application/json');req._dont_enforce_csrf_checks=True
        self.assertEqual(search(req).status_code,401)
        req=self.request(params());req._dont_enforce_csrf_checks=False
        self.assertEqual(search(req).status_code,403)

    @patch('acm.components_views.load_records')
    def test_signed_snapshot_and_user_bound_recalculation(self,load):
        load.return_value=(candidates(sample(),params()),[])
        response=search(self.request(params()));self.assertEqual(response.status_code,200)
        data=json.loads(response.content)
        response=recalculate(self.request({'token':data['token'],'excluded':['a']}))
        self.assertEqual(response.status_code,200)
        self.assertEqual(json.loads(response.content)['result']['house_count'],2)
        self.user.pk=2
        self.assertEqual(recalculate(self.request({'token':data['token']})).status_code,400)
        self.assertEqual(recalculate(self.request({'token':data['token']+'tampered'})).status_code,400)

    def test_page_has_old_and_new_panels(self):
        req=self.factory.get('/');req.current_user=self.user
        response=page(req)
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'cmp-old')
        self.assertContains(response,'Referencias incompletas',count=0)
        self.assertContains(response,'Solo referencia')

    def test_main_dashboard_uses_components_and_detail_modal(self):
        self.assertEqual(reverse('acm:acm_analisis'),'/acm/analisis/')
        self.assertIs(resolve('/acm/analisis/').func,page)
        req=self.factory.get('/acm/analisis/');req.current_user=self.user
        response=resolve(req.path).func(req)
        self.assertContains(response,'data-search-url="/acm/componentes/buscar/"')
        self.assertContains(response,'id="cmp-detail"')
        self.assertContains(response,'Cerrar detalle')
        self.assertNotContains(response,'ENTORNO DE PRUEBAS')

    def test_page_shell_remains_visible_before_login(self):
        response=page(self.factory.get('/acm/analisis/'))
        self.assertEqual(response.status_code,200)
        self.assertEqual(response['X-ACM-Model'],'componentes-1')
        self.assertEqual(response['Cache-Control'],'no-store')


class ComponentsDatabaseTests(TestCase):
    def test_fresh_scraper_records_are_read_on_each_search(self):
        from ingestas.models import PropiedadesCompetencia
        prop=PropiedadesCompetencia.objects.create(fuente='remax',id_origen='direct',tipo_inmueble='Casa',
            tipo_operacion='Venta',precio_usd=350000,area_terreno=150,area_construida=200,
            latitud=-16.4,longitud=-71.5,precision_ubicacion='exacta',estado_publicacion='activa')
        self.assertEqual(list(scraped_rows(params()))[0]['price'],350000)
        prop.precio_usd=360000;prop.save()
        self.assertEqual(list(scraped_rows(params()))[0]['price'],360000)

    @patch('cuadrantizacion.views._available_propify_properties')
    def test_propify_converts_soles_and_retains_separate_areas(self,load):
        load.return_value=[{'id':1,'code':'P1','title':'Casa','price':344000,'currency_symbol':'S/.',
            'operation_type':'Venta','property_type':'Casa','land_area_m2':150,'built_area_m2':200,
            'lat':-16.4,'lng':-71.5,'district':'Cayma','url':None,'image_url':None}]
        row=list(propify_rows())[0]
        self.assertEqual(row['price'],100000)
        self.assertEqual(row['land'],150)
        self.assertEqual(row['built'],200)
