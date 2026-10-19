from copy import deepcopy
from types import SimpleNamespace

from django.test import TestCase, SimpleTestCase
from ingestas.models import PropiedadesCompetencia
from acm.components_views import scraped_rows
from acm.components_engine import candidates, calculate, parameters
from acm.access import DEFAULTS
from acm.access_data import project
from acm.test_components import params, sample
from scrapi.building_features import apply_features


class ComparableFeatureDataTests(TestCase):
    def create(self, kind='Departamento', **extra):
        values = dict(fuente='remax', id_origen='features', tipo_inmueble=kind,
            tipo_operacion='Venta', precio_usd=200000, area_terreno=150, area_construida=120,
            latitud=-16.4, longitud=-71.5, precision_ubicacion='exacta', estado_publicacion='activa')
        return PropiedadesCompetencia.objects.create(**{**values, **extra})

    def row(self):
        return list(scraped_rows(params()))[0]

    def test_legacy_floor_and_parking_match_the_quality_listing(self):
        prop = self.create(datos_crudos={'Piso':'7', 'Cocheras':'2 lineales techadas'})
        row = self.row()
        self.assertEqual(row['floor_label'], prop.piso_departamento)
        self.assertEqual(row['floor'], 7)
        self.assertEqual(row['parking_has'], prop.tiene_cochera)
        self.assertEqual(row['parking_types'], ['lineal_techada'])
        self.assertNotIn('datos_crudos', row)

    def test_confirmed_zero_and_missing_values_stay_different(self):
        prop = self.create(datos_crudos={'Piso':0}, descripcion='Sin cochera.')
        row = self.row()
        self.assertEqual(row['floor_label'], '0')
        self.assertEqual(row['floor'], 0)
        self.assertIs(row['parking_has'], False)
        prop.datos_crudos={};prop.descripcion='';prop.estacionamientos=0;prop.save()
        row = self.row()
        self.assertIsNone(row['floor_label'])
        self.assertIsNone(row['parking_has'], 'A historical default zero does not prove absence')

    def test_reviewed_mixed_parking_and_multilevel_floor_survive_candidate_normalization(self):
        raw=apply_features({'tipo_inmueble':'Departamento','descripcion':
            'Una cochera lineal techada y otra paralela no techada.', 'datos_crudos':{}})['datos_crudos']
        raw.update(piso_departamento='3 y 4', _floor_evidence={'version':1,'status':'explicit','manual':True})
        self.create(datos_crudos=raw)
        row=self.row()
        p=parameters({**params(),'property_type':'Departamento','built':120})
        candidate=candidates([row],p)[0]
        self.assertEqual(candidate['floor_label'],'3 y 4')
        self.assertIsNone(candidate['floor'])
        self.assertEqual(candidate['parking_types'],['lineal_techada','paralela_no_techada'])

    def test_house_has_parking_without_an_apartment_floor(self):
        self.create(kind='Casa', descripcion='2 cocheras paralelas techadas. Piso 3.')
        row=self.row()
        self.assertIs(row['parking_has'],True)
        self.assertEqual(row['parking_types'],['paralela_techada'])
        self.assertIsNone(row['floor_label'])


class ComparableFeatureProjectionTests(SimpleTestCase):
    def test_property_fields_survive_basic_projection_and_respect_property_data_permission(self):
        record=sample()[0]
        record.update(floor_label='3 y 4',parking_has=True,parking_types=['lineal_techada'],
                      parking_status='explicit',image='')
        flags=deepcopy(DEFAULTS)
        access=SimpleNamespace(permissions=flags,user=SimpleNamespace(pk='1'),can_configure=False)
        request=SimpleNamespace(acm_access=access)
        state={'params':{},'records':[record]}
        safe,_,_=project(request,state)
        for field in ('floor_label','parking_has','parking_types','parking_status'):
            self.assertEqual(safe['records'][0][field],record[field])
        flags['property_data']=False
        safe,_,_=project(request,state)
        self.assertNotIn('parking_types',safe['records'][0])
        self.assertNotIn('floor_label',safe['records'][0])

    def test_display_features_do_not_change_the_valuation_or_selected_properties(self):
        p=parameters(params())
        original=sample()
        before=calculate(candidates(original,p),p)
        modified=deepcopy(original)
        for row in modified:
            row.update(floor_label='7',parking_has=True,parking_types=['paralela_techada'])
        after=calculate(candidates(modified,p),p)
        for field in ('new','house_ids','land_ids'):
            self.assertEqual(before[field],after[field])
