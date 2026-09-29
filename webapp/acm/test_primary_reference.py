from django.test import SimpleTestCase
from acm.components_engine import candidates, calculate
from acm.test_components import params, record


class PrimaryReferenceTests(SimpleTestCase):
    def test_accepted_group_uses_only_its_adjusted_prices(self):
        p={**params(),'reference_ids':['a','b']}
        rows=candidates([record('a',price=350000),record('b',price=380000),
                         record('c',price=5000000),record('soil','Terreno',price=150000)],p)
        result=calculate(rows,p)
        self.assertEqual(result['new']['total'],365000)
        self.assertEqual(result['usable_house_count'],2)
        self.assertEqual(result['recommended_ids'],['a','b'])
        self.assertFalse(next(d for d in result['breakdown'] if d['id']=='c')['usable'])

    def test_other_prices_do_not_change_result_and_remain_visible(self):
        p={**params(),'land':140,'built':150}
        raw=[record('chosen',price=370000,land=123.61,built=170.19),
             record('other',price=315000,land=78,built=78),
             record('soil','Terreno',price=126700,land=100)]
        first=calculate(candidates(raw,p),p)
        raw[1]['price']=5000000
        second=calculate(candidates(raw,p),p)
        self.assertEqual(first['built_reference_id'],'chosen')
        self.assertEqual(first['new']['total'],second['new']['total'])
        self.assertEqual(second['usable_house_count'],1)
        details={d['id']:d for d in second['breakdown']}
        self.assertEqual(set(details),{'chosen','other'})
        self.assertTrue(details['chosen']['recommended'])
        self.assertTrue(details['other']['reference_only'])
        self.assertFalse(details['other']['usable'])
        self.assertEqual(details['other']['weighted_contribution'],0)
        self.assertEqual(second['new']['total'],details['chosen']['target_estimate'])

    def test_area_match_beats_nearer_location_and_exclusion_reselects(self):
        p=params()
        raw=[record('area',lat=-16.402),record('near',land=160,built=215),
             record('soil','Terreno',price=150000)]
        rows=candidates(raw,p)
        self.assertEqual(calculate(rows,p)['built_reference_id'],'area')
        self.assertEqual(calculate(rows,p,['area'])['built_reference_id'],'near')

    def test_equal_surface_match_uses_distance_then_stable_id(self):
        p=params()
        rows=candidates([record('far',lat=-16.402),record('near'),
                         record('soil','Terreno',price=150000)],p)
        self.assertEqual(calculate(rows,p)['built_reference_id'],'near')
