"""Run without Django/SQL: python -m unittest scrapi.test_properati_location."""
import unittest
from scrapi.properati_location import map_object, precision_from_html


class ProperatiLocationTests(unittest.TestCase):
    def test_actual_approximate_map_structure(self):
        html = '''mapData: {showMap:true, adLocationData:{coordinates:{
        latitude:"-16.39968347",longitude:"-71.55393413"}},
        visibility:"approximate",enableApproximateArea:true}'''
        self.assertEqual(precision_from_html(html), 'aproximada')

    def test_actual_exact_map_structure(self):
        html = '''mapData: {showMap:true, adLocationData:{coordinates:{
        latitude:"-16.3536697",longitude:"-71.56275149999999"}},
        visibility:"accurate",enableApproximateArea:true}'''
        self.assertEqual(precision_from_html(html), 'exacta')

    def test_json_quoted_visibility(self):
        self.assertEqual(precision_from_html('{"mapData":{"visibility":"approximate"}}'), 'aproximada')

    def test_notice_overrides_map_visibility(self):
        html = '''<div id="location-map"><div class="location-map__info-map">
        El anunciante prefiere no mostrar la direcci&oacute;n <span>exacta</span>
        </div></div><script>mapData:{visibility:"accurate"}</script>'''
        self.assertEqual(precision_from_html(html), 'aproximada')

    def test_missing_map_is_unknown(self):
        self.assertEqual(precision_from_html('<h1>Just a moment</h1>'), 'desconocida')
        self.assertEqual(precision_from_html('coordinates:{latitude:-16,longitude:-71}'), 'desconocida')

    def test_map_is_scoped_away_from_recommendations(self):
        html = 'recommended:{latitude:-12,longitude:-77},mapData:{adLocationData:{coordinates:{latitude:-16,longitude:-71}},visibility:"accurate"},other:{latitude:-13}'
        block = map_object(html)
        self.assertNotIn('-12', block)
        self.assertNotIn('-13', block)
        self.assertIn('visibility:"accurate"', block)

    def test_braces_in_map_address(self):
        self.assertEqual(map_object('mapData:{address:"Casa {A}",visibility:"accurate"},other:{}'),
                         '{address:"Casa {A}",visibility:"accurate"}')

    def test_rendered_exact_block_does_not_need_button(self):
        html = '<div id="location-map"><div class="location-map__location-address-map">Cerro Colorado</div><div id="map"></div></div>'
        self.assertEqual(precision_from_html(html), 'exacta')


if __name__ == '__main__':
    unittest.main()
