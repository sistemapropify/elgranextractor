from django.test import SimpleTestCase

from scrapi.properati_scraper import extraer_coordenadas_desde_html


class ProperatiCoordinateExtractionTests(SimpleTestCase):
    def assert_coordinates(self, html):
        lat, lng = extraer_coordenadas_desde_html(html)
        self.assertAlmostEqual(lat, -16.3988, places=4)
        self.assertAlmostEqual(lng, -71.5369, places=4)

    def test_extracts_escaped_lat_lng(self):
        self.assert_coordinates(
            r'<script>state={\"lat\":\"-16.3988\",'
            r'\"label\":\"Arequipa\",\"lng\":\"-71.5369\"}</script>'
        )

    def test_extracts_reversed_coordinates(self):
        self.assert_coordinates(
            '<script>coordinates:{longitude:"-71.5369",'
            'accuracy:15,latitude:"-16.3988"}</script>'
        )

    def test_extracts_geojson(self):
        self.assert_coordinates(
            '<script>{"geometry":{"coordinates":'
            '[-71.5369,-16.3988]}}</script>'
        )

    def test_rejects_coordinates_outside_peru(self):
        self.assertEqual(
            extraer_coordenadas_desde_html(
                '<script>{"latitude":40.7128,"longitude":-74.0060}</script>'
            ),
            (None, None),
        )
