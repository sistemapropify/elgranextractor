from types import SimpleNamespace

from django.test import RequestFactory, SimpleTestCase

from .components_engine import calculate, candidates, parameters
from .test_components import params, record


class ZoneLandTests(SimpleTestCase):
    def test_soil_indicator_is_available_for_every_property_type_without_lot_area(self):
        for target in ('Casa', 'Departamento', 'Oficina', 'Terreno'):
            with self.subTest(target=target):
                p = parameters({**params(), 'property_type': target,
                                'land': 0 if target in ('Departamento', 'Oficina') else 150})
                raw = [record('soil-a', 'Terreno', price=75000, land=150),
                       record('soil-b', 'Terreno', price=140000, land=200),
                       record('soil-c', 'Terreno', price=270000, land=300),
                       record('outer', 'Terreno', price=1500000, land=150,
                              lat=p['lat'] + 800 / 111195)]
                if target != 'Terreno':
                    raw.append(record('target', target, price=350000, built=200))
                rows = candidates(raw, p)
                result = calculate(rows, p)
                self.assertEqual(result['zone_land']['unit'], 700)
                self.assertEqual(result['zone_land']['count'], 3)
                self.assertEqual(result['zone_land']['radius'], 500)
                self.assertEqual(set(result['zone_land']['ids']), {'soil-a', 'soil-b', 'soil-c'})
                if target in ('Departamento', 'Oficina'):
                    self.assertEqual(result['new']['total'], 350000)
                    self.assertEqual(result['house_ids'], ['target'])
                    self.assertIsNone(result['land_unit'], 'The independent indicator must not replace the property model.')

    def test_soil_radius_expands_only_when_needed_and_exclusions_recalculate(self):
        p = parameters({**params(), 'property_type': 'Departamento', 'land': 0})
        rows = candidates([record('near', 'Terreno', price=90000, land=150,
                                  lat=p['lat'] + 700 / 111195),
                           record('far', 'Terreno', price=120000, land=150,
                                  lat=p['lat'] + 1400 / 111195)], p)
        result = calculate(rows, p)
        self.assertIsNone(result['new'])
        self.assertEqual(result['zone_land']['unit'], 600)
        self.assertEqual(result['zone_land']['radius'], 1000)
        result = calculate(rows, p, ['near'])
        self.assertEqual(result['zone_land']['unit'], 800)
        self.assertEqual(result['zone_land']['radius'], 1500)
        self.assertIsNone(calculate(rows, p, ['near', 'far'])['zone_land']['unit'])

    def test_soil_does_not_use_houses_rentals_buildings_or_unverified_land(self):
        p = parameters({**params(), 'property_type': 'Oficina', 'land': 0})
        raw = [record('good', 'Terreno', price=90000),
               record('house', price=999999),
               record('rental', 'Terreno', operation='Alquiler'),
               record('building', 'Terreno', built=100),
               record('approximate', 'Terreno', precision='aproximada'),
               record('inactive', 'Terreno', state='retirada'),
               record('quality', 'Terreno', review_excluded=True),
               record('no-area', 'Terreno', land=None),
               record('no-price', 'Terreno', price=None),
               record('outside', 'Terreno', lat=p['lat'] + 2100 / 111195)]
        result = calculate(candidates(raw, p), p)
        self.assertEqual(result['zone_land']['ids'], ['good'])
        self.assertEqual(result['zone_land']['unit'], 600)

    def test_basic_projection_keeps_soil_indicator_and_anonymizes_its_evidence(self):
        from .access import DEFAULTS
        from .access_data import project
        p = parameters({**params(), 'property_type': 'Departamento', 'land': 0})
        rows = candidates([record('remax-private-id', 'Terreno', price=90000)], p)
        request = RequestFactory().get('/')
        request.acm_access = SimpleNamespace(permissions=DEFAULTS, user=SimpleNamespace(pk=5),
                                            fingerprint='test', can_configure=False, previewing=False)
        client, result, _ = project(request, {'params': p, 'records': rows}, calculate(rows, p))
        self.assertEqual(result['zone_land']['unit'], 600)
        self.assertTrue(all(value.startswith('c-') for value in result['zone_land']['ids']))
        self.assertEqual(result['zone_land']['ids'], [client['records'][0]['id']])
        self.assertNotIn('remax', str(result['zone_land']).lower())

    def test_zonal_indicator_does_not_replace_adopted_unit_for_target_land(self):
        p = parameters({**params(), 'property_type': 'Terreno', 'land': 1212, 'built': 0})
        rows = candidates([record('comparable', 'Terreno', price=787800, land=1212),
                           record('small-a', 'Terreno', price=120000, land=150),
                           record('small-b', 'Terreno', price=127500, land=150)], p)
        result = calculate(rows, p)
        self.assertEqual(result['zone_land']['unit'], 800)
        self.assertEqual(result['new']['unit'], 650)
        self.assertEqual(result['new']['total'], 650 * 1212)
