from contextlib import nullcontext
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.db import DataError, IntegrityError
from django.test import SimpleTestCase

from acm.views import (
    _ensure_acm_test_snapshot,
    _persist_snapshot_batch,
    _snapshot_decimal,
)


class ACMTestSnapshotTests(SimpleTestCase):
    def property(self, pk=1):
        return SimpleNamespace(
            pk=pk, portal='properati', tipo_propiedad='Casa', precio_usd=100,
            precio_final_venta=None, descripcion='Prueba', url_propiedad='https://example.test/1',
            coordenadas='-16.4,-71.5', departamento='Arequipa', provincia='Arequipa',
            distrito='Cayma', area_terreno=120, area_construida=80,
            numero_habitaciones=3, numero_banos=2, numero_cocheras=1,
            imagenes_propiedad='', estado_propiedad='en_publicacion',
        )

    @patch('acm.views.transaction.atomic', return_value=nullcontext())
    @patch('acm.views.PropiedadRaw.objects.iterator')
    @patch('acm.views.ACMTestProperty.objects')
    def test_snapshot_uses_sql_server_compatible_bulk_insert(self, objects, iterator, _atomic):
        objects.exists.return_value = False
        iterator.return_value = [self.property()]

        _ensure_acm_test_snapshot()

        objects.bulk_create.assert_called_once()
        _, kwargs = objects.bulk_create.call_args
        self.assertEqual(kwargs, {'batch_size': 100})

    def test_snapshot_drops_numeric_value_that_overflows_sql_column(self):
        value = _snapshot_decimal(
            '999999999999999999', max_digits=10, decimal_places=2,
            source_id='raw-9', field_name='area_terreno',
        )

        self.assertIsNone(value)

    def test_snapshot_rounds_valid_decimal_to_column_precision(self):
        value = _snapshot_decimal(
            '123.456', max_digits=10, decimal_places=2,
            source_id='raw-10', field_name='area_terreno',
        )

        self.assertEqual(value, Decimal('123.46'))

    @patch('acm.views.transaction.atomic', return_value=nullcontext())
    @patch('acm.views.ACMTestProperty.objects.bulk_create')
    def test_bad_batch_retries_rows_and_skips_only_corrupt_one(self, bulk_create, _atomic):
        valid = MagicMock(source_id='raw-1')
        corrupt = MagicMock(source_id='raw-2')
        bulk_create.side_effect = DataError('numeric overflow')
        corrupt.save.side_effect = DataError('numeric overflow')

        _persist_snapshot_batch([valid, corrupt])

        valid.save.assert_called_once_with(force_insert=True)
        corrupt.save.assert_called_once_with(force_insert=True)

    @patch('acm.views.transaction.atomic', return_value=nullcontext())
    @patch('acm.views.PropiedadRaw.objects.iterator')
    @patch('acm.views.ACMTestProperty.objects')
    def test_concurrent_snapshot_winner_is_accepted(self, objects, iterator, _atomic):
        objects.exists.side_effect = [False, False, True]
        iterator.return_value = [self.property()]
        objects.bulk_create.side_effect = IntegrityError('duplicate source_id')

        _ensure_acm_test_snapshot()

        self.assertEqual(objects.exists.call_count, 3)

    @patch('acm.views.transaction.atomic', return_value=nullcontext())
    @patch('acm.views.PropiedadRaw.objects.iterator')
    @patch('acm.views.ACMTestProperty.objects')
    def test_unrelated_integrity_error_is_not_hidden(self, objects, iterator, _atomic):
        objects.exists.side_effect = [False, False, False]
        iterator.return_value = [self.property()]
        objects.bulk_create.side_effect = IntegrityError('invalid data')

        with self.assertRaises(IntegrityError):
            _ensure_acm_test_snapshot()
