from django.test import SimpleTestCase
from .property_quality import annotate_map_quality


def prop(i=1, **kwargs):
    return dict(id=i, source_key='remax', price=100000, currency_symbol='$',
                property_type='Casa', operation_type='Venta', land_area_m2=150,
                built_area_m2=200, district='Cayma', location_precision='Exacta',
                lat=-16.4, lng=-71.5, **kwargs)


class MapQualityTests(SimpleTestCase):
    def test_expensive_house_is_not_statistical_outlier(self):
        row=prop();row.update(price=1500000,land_area_m2=498,built_area_m2=268)
        annotate_map_quality([row])
        self.assertEqual(row['quality_status'],'clear')

    def test_incomplete_and_small_land_are_visible_alerts(self):
        row=prop();row.update(land_area_m2=20,built_area_m2=None)
        annotate_map_quality([row])
        self.assertEqual({a['code'] for a in row['quality_alerts']},{'small_house_land','built_missing'})

    def test_extreme_apartment_and_excluded_not_used_in_peers(self):
        rows=[prop(i) for i in range(8)]
        for row,price in zip(rows,[100000,105000,110000,115000,120000,125000,130000,1000000]):
            row.update(property_type='Departamento',price=price,built_area_m2=100)
        summary=annotate_map_quality(rows)
        self.assertEqual(summary['outlier'],1)
        self.assertEqual(rows[-1]['quality_status'],'outlier')
        rows[-1]['quality_excluded']=True
        annotate_map_quality(rows)
        self.assertEqual(rows[-1]['quality_status'],'excluded')
        self.assertFalse(any(a['category']=='outlier' for r in rows for a in r['quality_alerts']))

    def test_legacy_area_is_not_treated_as_explicit(self):
        row=prop();row['_quality_input']={'land':None,'built':None,'legacy_area':True}
        annotate_map_quality([row])
        self.assertTrue(any(a['code']=='built_missing' for a in row['quality_alerts']))
        self.assertNotIn('_quality_input',row)

    def test_currency_and_rental_separate(self):
        rows=[prop(i) for i in range(8)]
        for r in rows:r.update(property_type='Departamento',operation_type='Alquiler',price=999999)
        self.assertEqual(annotate_map_quality(rows)['outlier'],0)
