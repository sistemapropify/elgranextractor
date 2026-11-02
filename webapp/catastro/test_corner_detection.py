from django.test import SimpleTestCase

from catastro.corner_detection import detect_corner_lots


class CornerDetectionTests(SimpleTestCase):
    def feature(self, lot_id, coordinates, sector='01', block='001'):
        return {
            'type': 'Feature',
            'id': lot_id,
            'properties': {
                'ID_LOTE': lot_id,
                'COD_SECT': sector,
                'COD_MZNA': block,
            },
            'geometry': {
                'type': 'Polygon',
                'coordinates': [coordinates],
            },
        }

    def test_detects_two_exterior_frontages_and_ignores_side_or_center_lot(self):
        block = self.feature(
            '04010100000001',
            [[0, 0], [20, 0], [20, 20], [0, 20], [0, 0]],
        )
        corner = self.feature(
            '04010100000002',
            [[0, 0], [5, 0], [5, 5], [0, 5], [0, 0]],
        )
        side = self.feature(
            '04010100000003',
            [[0, 5], [5, 5], [5, 15], [0, 15], [0, 5]],
        )
        center = self.feature(
            '04010100000004',
            [[5, 5], [15, 5], [15, 15], [5, 15], [5, 5]],
        )
        detected, skipped = detect_corner_lots(
            [corner, side, center],
            [block],
        )
        self.assertEqual(detected, ['04010100000002'])
        self.assertEqual(skipped, 0)

    def test_requires_separate_directions_not_only_long_single_frontage(self):
        block = self.feature(
            '04010100000001',
            [[0, 0], [30, 0], [30, 20], [0, 20], [0, 0]],
        )
        long_side = self.feature(
            '04010100000002',
            [[5, 0], [25, 0], [25, 10], [5, 10], [5, 0]],
        )
        detected, _ = detect_corner_lots([long_side], [block])
        self.assertEqual(detected, [])
