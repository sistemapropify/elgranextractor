from django.test import SimpleTestCase

from intelligence.services.property_artifacts import (
    build_property_collection_artifact,
    normalize_property_item,
)


class PropertyArtifactTests(SimpleTestCase):
    def test_normalizes_property_and_preserves_source_id(self):
        item = {
            'source_id': 42,
            'collection_name': 'propiedadespropify',
            'field_values': {
                'code': 'P-42',
                'title': 'Terreno en Cerro Colorado',
                'price': '85000.00',
                'currency_name': 'Dolares',
                'district_name': 'Cerro Colorado',
                'property_type_name': 'Terreno',
                'land_area': '200',
            },
        }

        result = normalize_property_item(item)

        self.assertEqual(result['id'], '42')
        self.assertEqual(result['source']['source_id'], '42')
        self.assertEqual(result['price'], 85000.0)
        self.assertEqual(result['currency'], 'USD')
        self.assertEqual(result['area_m2'], 200.0)
        self.assertTrue(result['images'][0]['url'].endswith('/P-42.jpg'))

    def test_collection_count_matches_items_and_enables_compare(self):
        items = [
            {'source_id': 1, 'field_values': {'title': 'Uno'}},
            {'source_id': 2, 'field_values': {'title': 'Dos'}},
        ]

        artifact = build_property_collection_artifact(
            items, message_id='message-1', trace_id='trace-1',
            hydrate_media=False,
        )

        self.assertEqual(artifact['result_count'], len(artifact['items']))
        self.assertIn('cards', artifact['available_views'])
        self.assertIn('compare', artifact['available_views'])
        self.assertNotIn('map', artifact['available_views'])
        self.assertTrue(artifact['provenance']['grounded'])

    def test_items_without_source_id_are_discarded(self):
        artifact = build_property_collection_artifact(
            [{'field_values': {'title': 'Sin ID'}}],
            message_id='message-1',
            hydrate_media=False,
        )
        self.assertIsNone(artifact)
