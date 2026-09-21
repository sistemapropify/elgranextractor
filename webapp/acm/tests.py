from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.db import IntegrityError
from django.test import SimpleTestCase

from acm.views import _ensure_acm_test_snapshot


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
