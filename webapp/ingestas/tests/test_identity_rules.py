"""Unit tests: run with unittest, no Django database or external dependencies."""
from copy import deepcopy
from decimal import Decimal
import random
import unittest
from unittest.mock import patch

try:
    from ingestas import identity_rules as rules
except ModuleNotFoundError:
    import identity_rules as rules


DESCRIPTION = ('Jardin posterior con limonero antiguo y estanque circular. '
               'Escalera helicoidal conecta biblioteca abovedada con terraza triangular. '
               'Carpinteria cedro tallado, vitrales artesanales azules y sotano ventilado. '
               'Dormitorio principal conserva balcon semicircular orientado al volcan.')
BOILERPLATE = ('Hermoso departamento en excelente ubicacion, ideal inversion. '
               'Amplio e iluminado con finos acabados de primera calidad. '
               'Cerca de centros comerciales, bancos, colegios y parques. '
               'Contactanos y agenda tu visita con nuestros asesores inmobiliarios.')


def row(pk, **changes):
    value = dict(pk=pk, fuente='remax', id_origen=f'listing-{pk}',
                 url=None, tipo_inmueble='Casa', tipo_operacion='Venta',
                 precio_usd=Decimal('300000'), area_terreno=Decimal('200'),
                 area_construida=Decimal('180'), latitud=Decimal('-16.4'),
                 longitud=Decimal('-71.5'), precision_ubicacion='exacta',
                 direccion_texto='Avenida Los Cedros 327',
                 descripcion=DESCRIPTION, titulo='Casa con biblioteca y jardin')
    value.update(changes)
    return value


class IdentityRuleTests(unittest.TestCase):
    def test_sparse_data_and_bad_values_never_invent_pairs(self):
        self.assertEqual(rules.propose_pairs([]), [])
        self.assertEqual(rules.propose_pairs([{}, None, {'pk': 1}, {'id': 2}, {'pk': False}]), [])
        for value in (None, '', 'NaN', float('inf'), -10, 0, True):
            with self.subTest(value=value):
                self.assertEqual(rules.propose_pairs([row(1, precio_usd=value), row(2)]), [])

    def test_same_source_id_is_review_only_even_without_property_data(self):
        pair = rules.propose_pairs([{'id': 2, 'fuente': 'urbania', 'id_origen': 'ABC'},
                                    {'id': 1, 'fuente': 'urbania', 'id_origen': 'ABC'}])[0]
        self.assertEqual((pair['left_id'], pair['right_id'], pair['status']), (1, 2, 'possible'))
        self.assertEqual(pair['evidence'][0]['code'], 'identity.same_source_id')
        self.assertGreaterEqual(pair['score'], 95)

    def test_source_ids_do_not_cross_sources_or_change_case(self):
        base = {'pk': 1, 'fuente': 'remax', 'id_origen': 'AbC'}
        for change in ({'fuente': 'urbania'}, {'id_origen': 'abc'}, {'fuente': ''}):
            self.assertEqual(rules.propose_pairs([base, {**base, 'pk': 2, **change}]), [])
        for placeholder in ('', 'null', None, '0', 'sin id'):
            self.assertEqual(rules.propose_pairs([{'pk': 1, 'fuente': 'remax', 'id_origen': placeholder},
                                                 {'pk': 2, 'fuente': 'remax', 'id_origen': placeholder}]), [])

    def test_listing_url_removes_only_tracking(self):
        a = {'pk': 1, 'url': 'https://www.adondevivir.com/propiedades/clasificado/casa-123.html?utm_source=a&ref=one#foto'}
        b = {'pk': 2, 'url': 'https://adondevivir.com/propiedades/clasificado/casa-123.html?ref=one&fbclid=x'}
        self.assertEqual(rules.propose_pairs([a, b])[0]['evidence'][0]['code'], 'identity.same_detail_url')
        b['url'] = b['url'].replace('ref=one', 'ref=two')
        self.assertEqual(rules.propose_pairs([a, b]), [])

    def test_known_portal_detail_paths(self):
        for url in ('https://urbania.pe/inmueble/123',
                    'https://urbania.pe/inmueble/clasificado/veclapin-venta-de-departamento-150106939',
                    'https://urbania.pe/propiedades/clasificado/casa-123.html',
                    'https://www.properati.com.pe/detalle/abc123',
                    'https://www.remax.pe/web/property/123',
                    'https://www.remax.pe/web/search/property/1198201/',
                    'https://www.facebook.com/marketplace/item/123/'):
            with self.subTest(url=url):
                self.assertEqual(len(rules.propose_pairs([{'pk': 1, 'url': url}, {'pk': 2, 'url': url}])), 1)

    def test_common_unsafe_and_unknown_urls_are_not_identifiers(self):
        for url in ('https://urbania.pe/', 'https://urbania.pe/buscar/casas',
                    'https://www.remax.pe/web/search/all/propertys/list/',
                    'https://www.adondevivir.com/inmuebles-en-venta.html',
                    'https://urbania.pe.evil.test/inmueble/123',
                    'https://user:secret@urbania.pe/inmueble/123',
                    'https://urbania.pe:8443/inmueble/123',
                    'https://urbania.pe/inmueble/123#/another-property',
                    'https://unknown.test/inmueble/123',
                    'http://urbania.pe/inmueble/123', 'javascript:alert(1)',
                    'https://urbania.pe/inmueble/123?ref=%FF',
                    'https://urbania.pe:bad/inmueble/123'):
            with self.subTest(url=url):
                self.assertEqual(rules.propose_pairs([{'pk': 1, 'url': url}, {'pk': 2, 'url': url}]), [])

    def test_repeated_query_order_and_path_case_preserved(self):
        a = 'https://urbania.pe/inmueble/ABC?unit=1&unit=2'
        b = 'https://urbania.pe/inmueble/ABC?unit=2&unit=1'
        self.assertNotEqual(rules.canonical_detail_url(a), rules.canonical_detail_url(b))
        self.assertNotEqual(rules.canonical_detail_url(a), rules.canonical_detail_url(a.replace('ABC', 'abc')))

    def test_genuine_possible_house_duplicate_has_multiple_evidence(self):
        pairs = rules.propose_pairs([row(2, fuente='urbania', precio_usd=302000,
                                          area_terreno=201, latitud=-16.4001), row(1)])
        self.assertEqual(len(pairs), 1)
        codes = {e['code'] for e in pairs[0]['evidence']}
        self.assertTrue({'address.same_numbered', 'price.close', 'area.close',
                         'text.distinctive_overlap', 'location.declared_exact_nearby'} <= codes)
        self.assertEqual(pairs[0]['status'], 'possible')
        self.assertLess(pairs[0]['score'], 95)

    def test_proximity_alone_and_shared_building_do_not_match(self):
        first = row(1, tipo_inmueble='Departamento')
        second = row(2, tipo_inmueble='Departamento', fuente='urbania')
        self.assertEqual(rules.propose_pairs([first, second]), [])
        first['direccion_texto'] += ' departamento 301'
        second['direccion_texto'] += ' departamento 302'
        self.assertEqual(rules.propose_pairs([first, second]), [])

    def test_same_explicit_unit_and_independent_details_can_be_possible(self):
        first = row(1, tipo_inmueble='Departamento', direccion_texto='Los Cedros 327 Dpto. 301')
        second = row(2, tipo_inmueble='Departamento', fuente='urbania',
                     direccion_texto='Los Cedros 327 departamento 301')
        pair = rules.propose_pairs([first, second])[0]
        self.assertIn('unit.same_explicit', {e['code'] for e in pair['evidence']})

    def test_floorplan_area_in_title_is_not_a_unit(self):
        self.assertEqual(rules.propose_pairs([
            row(1, tipo_inmueble='Departamento', titulo='Departamento 180 m2'),
            row(2, tipo_inmueble='Departamento', titulo='Departamento 180 m2')]), [])

    def test_unit_number_does_not_substitute_for_street_number(self):
        self.assertEqual(rules.propose_pairs([
            row(1, tipo_inmueble='Departamento', direccion_texto='Los Cedros dpto 301'),
            row(2, tipo_inmueble='Departamento', direccion_texto='Los Cedros dpto 301')]), [])

    def test_room_count_in_title_is_not_an_explicit_unit(self):
        for rooms in ('habitaciones', 'habitación', 'recámaras', 'rooms', 'baños', 'pisos'):
            with self.subTest(rooms=rooms):
                self.assertEqual(rules.propose_pairs([
                    row(1, tipo_inmueble='Departamento', titulo='Departamento 3 ' + rooms),
                    row(2, tipo_inmueble='Departamento', titulo='Departamento 3 ' + rooms)]), [])

    def test_date_in_street_name_is_not_street_number(self):
        self.assertEqual(rules.propose_pairs([
            row(1, direccion_texto='Av. 28 de Julio'),
            row(2, direccion_texto='Av. 28 de Julio')]), [])
        self.assertEqual(len(rules.propose_pairs([
            row(1, direccion_texto='Av. 28 de Julio 327'),
            row(2, direccion_texto='Av. 28 de Julio 327')])), 1)

    def test_conflicting_units_mentioned_in_description_reject_fuzzy_match(self):
        rows = [row(1, tipo_inmueble='Oficina', direccion_texto='Los Cedros 327 oficina 301'),
                row(2, tipo_inmueble='Oficina', direccion_texto='Los Cedros 327 oficina 301',
                    descripcion=DESCRIPTION + ' Tambien se ofrece oficina 302.')]
        self.assertEqual(rules.propose_pairs(rows), [])

    def test_boilerplate_alone_never_suffices(self):
        rows = [row(1, descripcion=BOILERPLATE), row(2, descripcion=BOILERPLATE)]
        self.assertEqual(rules.propose_pairs(rows), [])

    def test_project_boilerplate_recurring_across_corpus_is_removed(self):
        rows = [row(i, direccion_texto=f'Los Cedros {100 + i}') for i in range(40)]
        rows[1]['direccion_texto'] = rows[0]['direccion_texto']
        self.assertEqual(rules.propose_pairs(rows), [])

    def test_approximate_location_does_not_support_fuzzy_identity(self):
        for precision in ('aproximada', 'desconocida', None, ''):
            self.assertEqual(rules.propose_pairs([row(1), row(2, precision_ubicacion=precision)]), [])
        pairs = rules.propose_pairs([row(1, id_origen='same', precision_ubicacion='aproximada'),
                                     row(2, id_origen='same', latitud=None, longitud=None)])
        self.assertEqual(len(pairs), 1)

    def test_missing_location_address_and_area_do_not_match(self):
        for changes in ({'latitud': None}, {'longitud': 0}, {'direccion_texto': ''},
                        {'direccion_texto': 'Cayma Arequipa'}, {'area_terreno': None},
                        {'area_construida': 'NaN'}, {'direccion_texto': 'Altura Los Cedros 327'}):
            with self.subTest(changes=changes):
                self.assertEqual(rules.propose_pairs([row(1, **changes), row(2, **changes)]), [])

    def test_kind_operation_price_area_and_distance_conflicts_reject(self):
        for changes in ({'tipo_inmueble': 'Terreno'}, {'tipo_operacion': 'Alquiler'},
                        {'precio_usd': 350000}, {'area_terreno': 250},
                        {'area_construida': 210}, {'latitud': -16.402},
                        {'direccion_texto': 'Avenida Los Cedros 329'}):
            with self.subTest(changes=changes):
                self.assertEqual(rules.propose_pairs([row(1), row(2, **changes)]), [])

    def test_adjacent_spatial_cells_are_considered(self):
        latitude = -18236 * 100 / rules._METRES_PER_DEGREE
        first = row(1, latitud=latitude - .00001)
        second = row(2, latitud=latitude + .00001)
        self.assertEqual(len(rules.propose_pairs([first, second])), 1)

    def test_exact_identifier_conflicts_are_visible_review_only(self):
        pairs = rules.propose_pairs([row(1, id_origen='same'),
                                     row(2, id_origen='same', tipo_operacion='Alquiler')])
        self.assertEqual(pairs[0]['status'], 'possible')
        self.assertIn('identity.conflict', {e['code'] for e in pairs[0]['evidence']})

    def test_input_order_and_purity(self):
        rows = [row(20), row(2), row('abc', id_origen='one'), row('def', id_origen='one')]
        before = deepcopy(rows)
        expected = rules.propose_pairs(rows)
        random.Random(37).shuffle(rows)
        self.assertEqual(rules.propose_pairs(rows), expected)
        self.assertEqual(sorted(rows, key=lambda x: str(x['pk'])), sorted(before, key=lambda x: str(x['pk'])))

    def test_ambiguous_repeated_record_ids_are_not_silently_chosen(self):
        self.assertEqual(rules.propose_pairs([row(1), row(1), row(2)]), [])

    def test_5130_dense_records_have_bounded_comparison_work(self):
        rows = [row(i) for i in range(5130)]
        with patch.object(rules, '_compare', wraps=rules._compare) as comparison:
            self.assertEqual(rules.propose_pairs(rows), [])
        self.assertLess(comparison.call_count, len(rows) * rules.MAX_NEIGHBORS_PER_BLOCK)

    def test_shared_advertisement_group_is_sparse_not_all_pairs(self):
        rows = [{'pk': i, 'fuente': 'urbania', 'id_origen': 'same'} for i in range(5130)]
        pairs = rules.propose_pairs(rows)
        self.assertEqual(len(pairs), len(rows) - 1)
        self.assertTrue(all(pair['left_id'] == 0 and pair['status'] == 'possible' for pair in pairs))


if __name__ == '__main__':
    unittest.main()
