from django.test import SimpleTestCase

from .formalization_detail_migration import (
    _boundary_rows,
    _detail_fields,
)


class FormalizationDetailMigrationTests(SimpleTestCase):
    def test_official_boundaries_populate_measurement_fields(self):
        fields = _detail_fields({
            'NOMPJV': 'PUEBLO TRADICIONAL: CHIGUATA',
            'SECTOR': 'ZONA: A',
            'MZNA': 'A',
            'LOTE': '1',
            'TIPO_USO': 'SERVICIOS COMUNALES',
            'PM_AREPRE': '139.71',
            'PM_LTEFRE': '15.32',
            'PM_LTEDER': '9.5',
            'PM_LTEIZQ': '9.38',
            'PM_LTEFON': '14.55',
        })
        self.assertEqual(fields['land_area'], 139.71)
        self.assertEqual(fields['front'], 15.32)
        self.assertEqual(fields['right'], 9.5)
        self.assertEqual(fields['left'], 9.38)
        self.assertEqual(fields['back'], 14.55)

    def test_boundary_segments_preserve_labels_and_multi_part_measures(self):
        rows = _boundary_rows({
            'FC_FRENTE': 'CALLE 28 DE JULIO',
            'PM_LTEFRE': '15.32',
            'FC_DERECHA': 'LOTE 2, LOTE 3',
            'PM_LTEDER': '5.1,5.2',
        }, 'entity-id', 'version-id', '2026-11-09')
        by_side = {row[2]: row for row in rows}
        self.assertEqual(by_side['front'][3], 15.32)
        self.assertEqual(by_side['right'][3], 10.3)
