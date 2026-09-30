"""Pure unittest regressions; execute with python -B -m unittest discover here."""
import copy
from decimal import Decimal
import unittest

from ingestas.spatial_rules import assess_location, EPS


def box(south=-16.5, west=-71.6, north=-16.3, east=-71.4):
    return [[south, west], [south, east], [north, east], [north, west]]


def zone(pk=1, level='zona', parent=None, coordinates=None, **overrides):
    return dict(id=pk, nivel=level, parent_id=parent,
                coordenadas=box() if coordinates is None else coordinates,
                activo=True, nombre_zona='Zona ' + str(pk), **overrides)


def row(lat=-16.4, lng=-71.5, precision='exacta', **overrides):
    return dict(latitud=lat, longitud=lng, precision_ubicacion=precision,
                distrito='Cayma', **overrides)


class SpatialRulesTests(unittest.TestCase):
    def codes(self, result):
        return {entry['code'] for entry in result['evidence']}

    def test_project_lat_lng_order_and_declared_exact_caveat(self):
        result = assess_location(row(), [zone()])
        self.assertEqual(result['status'], 'exact_zone')
        self.assertEqual(result['selected_zone_id'], 1)
        self.assertEqual(result['matching_zone_ids'], [1])
        self.assertIn('location.declared_exact', self.codes(result))
        swapped = assess_location(row(lat=-71.5, lng=-16.4), [zone()])
        self.assertEqual(swapped['status'], 'exact_unzoned')

    def test_open_closed_and_reversed_rings_agree(self):
        polygon = box()
        for points in (polygon, polygon + polygon[:1], list(reversed(polygon))):
            with self.subTest(points=points):
                self.assertEqual(assess_location(row(), [zone(coordinates=points)])['status'], 'exact_zone')

    def test_decimal_and_serialized_row_coordinates(self):
        self.assertEqual(assess_location(row(Decimal('-16.4'), '-71.5'), [zone()])['status'], 'exact_zone')

    def test_missing_nonfinite_bool_and_out_of_range_coordinates(self):
        for lat, lng in ((None, -71.5), ('', -71.5), ('nan', -71.5), (float('inf'), -71.5),
                         (True, -71.5), (-91, -71.5), (-16.4, 181)):
            with self.subTest(lat=lat, lng=lng):
                result = assess_location(row(lat, lng), [zone()])
                self.assertEqual(result['status'], 'missing')
                self.assertIsNone(result['selected_zone_id'])

    def test_non_exact_never_gets_selected_zone(self):
        for precision in ('aproximada', 'desconocida', None, '', 'exact'):
            result = assess_location(row(precision=precision), [zone()])
            self.assertEqual(result['status'], 'approximate_reference')
            self.assertEqual(result['matching_zone_ids'], [1])
            self.assertIsNone(result['selected_zone_id'])

    def test_approximate_still_exposes_boundary_and_bad_geometry(self):
        result = assess_location(row(lat=-16.5, precision='aproximada'), [zone(), zone(2, coordinates=[])])
        self.assertEqual(result['status'], 'approximate_reference')
        self.assertIn('zone.boundary', self.codes(result))
        self.assertIn('zone.invalid_geometry', self.codes(result))

    def test_all_edges_vertices_and_numerical_nearness_are_ambiguous(self):
        for lat, lng in ((-16.5, -71.5), (-16.3, -71.5), (-16.4, -71.6),
                         (-16.4, -71.4), (-16.5, -71.6), (-16.5 - EPS / 2, -71.5)):
            with self.subTest(lat=lat, lng=lng):
                result = assess_location(row(lat, lng), [zone()])
                self.assertEqual(result['status'], 'ambiguous')
                self.assertIn('zone.boundary', self.codes(result))

    def test_tolerance_does_not_swallow_points_clearly_inside_or_outside(self):
        self.assertEqual(assess_location(row(-16.5 + EPS * 4), [zone()])['status'], 'exact_zone')
        self.assertEqual(assess_location(row(-16.5 - EPS * 4), [zone()])['status'], 'exact_unzoned')

    def test_shared_border_records_both_matches(self):
        zones = [zone(1, coordinates=box(east=-71.5)), zone(2, coordinates=box(west=-71.5))]
        result = assess_location(row(), zones)
        self.assertEqual(result['status'], 'ambiguous')
        self.assertEqual(result['matching_zone_ids'], [1, 2])

    def test_hierarchy_selects_smallest_level_not_area_or_price(self):
        zones = [zone(1), zone(2, 'subzona', 1, box(-16.46, -71.56, -16.34, -71.44)),
                 zone(3, 'cuadrante', 2, box(-16.42, -71.52, -16.38, -71.48))]
        result = assess_location(row(precio_usd=999999999), list(reversed(zones)))
        self.assertEqual(result['status'], 'exact_zone')
        self.assertEqual(result['selected_zone_id'], 3)
        self.assertEqual(result['matching_zone_ids'], [1, 2, 3])

    def test_same_level_overlap_is_ambiguous_even_with_different_prices(self):
        result = assess_location(row(), [zone(1, precio_promedio_m2=1), zone(2, precio_promedio_m2=50000)])
        self.assertEqual(result['status'], 'ambiguous')
        self.assertIn('zone.same_level_overlap', self.codes(result))

    def test_unrelated_nested_polygons_are_not_assumed_to_be_related(self):
        result = assess_location(row(), [zone(1), zone(2, 'subzona', None)])
        self.assertEqual(result['status'], 'ambiguous')
        self.assertIn('zone.parent_missing', self.codes(result))

    def test_missing_inactive_and_wrong_level_parent_are_ambiguous(self):
        inactive = zone(1)
        inactive['activo'] = False
        for zones in ([zone(2, 'subzona', 99)], [inactive, zone(2, 'subzona', 1)],
                      [zone(1, 'distrito'), zone(2, 'cuadrante', 1)]):
            self.assertEqual(assess_location(row(), zones)['status'], 'ambiguous')

    def test_polygon_must_be_fully_nested_not_merely_match_the_same_point(self):
        zones = [zone(1), zone(2, 'subzona', 1, box(-16.45, -71.55, -16.2, -71.45))]
        result = assess_location(row(), zones)
        self.assertEqual(result['status'], 'ambiguous')
        self.assertIn('zone.inconsistent_nesting', self.codes(result))

    def test_concave_parent_detects_child_edge_leaving_with_all_vertices_inside(self):
        # U-shaped parent: child corners are inside but its upper edge crosses the gap.
        parent = [[0, 0], [0, 6], [6, 6], [6, 4], [2, 4], [2, 2], [6, 2], [6, 0]]
        child = [[1, 1], [1, 5], [5, 5], [5, 1]]
        result = assess_location(row(1.5, 1.5), [zone(1, coordinates=parent), zone(2, 'subzona', 1, child)])
        self.assertEqual(result['status'], 'ambiguous')
        self.assertIn('zone.inconsistent_nesting', self.codes(result))

    def test_nested_shared_edges_allowed_for_interior_point(self):
        zones = [zone(1), zone(2, 'subzona', 1, box(-16.5, -71.6, -16.35, -71.45))]
        self.assertEqual(assess_location(row(), zones)['status'], 'exact_zone')

    def test_administrative_areas_never_become_microzones(self):
        zones = [zone(1, 'provincia'), zone(2, 'distrito', 1)]
        result = assess_location(row(), zones)
        self.assertEqual(result['status'], 'exact_unzoned')
        self.assertEqual(result['matching_zone_ids'], [])
        self.assertIsNone(result['selected_zone_id'])

    def test_administrative_parent_can_omit_polygon(self):
        parent = zone(1, 'distrito', coordinates=[])
        zones = [parent, zone(2, parent=1)]
        result = assess_location(row(), zones)
        self.assertEqual(result['status'], 'exact_zone')
        self.assertEqual(result['selected_zone_id'], 2)
        self.assertIn('zone.administrative_geometry_absent', self.codes(result))

    def test_present_administrative_parent_must_contain_child(self):
        zones = [zone(1, 'distrito', coordinates=box(-16.45, -71.55, -16.35, -71.45)), zone(2, parent=1)]
        self.assertEqual(assess_location(row(), zones)['status'], 'ambiguous')

    def test_malformed_polygons_never_assign(self):
        polygons = [[], [[-16.4, -71.5]], [[-16.4, -71.5]] * 3,
                    [[-16.5, -71.6], [-16.3, -71.4], [-16.5, -71.4], [-16.3, -71.6]],
                    box() + [box()[1]], [[-16.5, -71.5], [-16.4, -71.5], [-16.3, -71.5]],
                    [[float('nan'), -71.5], [-16.3, -71.4], [-16.5, -71.4]],
                    [[True, -71.5], [-16.3, -71.4], [-16.5, -71.4]],
                    [[100, -71.5], [-16.3, -71.4], [-16.5, -71.4]], 'not a ring']
        for polygon in polygons:
            with self.subTest(polygon=polygon):
                result = assess_location(row(), [zone(coordinates=polygon)])
                self.assertEqual(result['status'], 'invalid_zone')
                self.assertIsNone(result['selected_zone_id'])

    def test_internal_duplicate_and_backtracking_edges_are_rejected(self):
        for polygon in ([[0, 0], [0, 4], [2, 4], [0, 4], [4, 0]],
                        [[0, 0], [0, 4], [0, 2], [4, 4], [4, 0]]):
            self.assertEqual(assess_location(row(1, 1), [zone(coordinates=polygon)])['status'], 'invalid_zone')

    def test_invalid_distant_bounded_ring_does_not_poison_local_zone(self):
        distant = [[0, 0], [1, 1], [0, 1], [1, 0]]
        self.assertEqual(assess_location(row(), [zone(1), zone(2, coordinates=distant)])['status'], 'exact_zone')

    def test_invalid_unbounded_ring_prevents_false_coverage_claim(self):
        result = assess_location(row(), [zone(1), zone(2, coordinates=[])])
        self.assertEqual(result['status'], 'invalid_zone')

    def test_duplicate_ids_are_rejected_and_string_parent_ids_resolve(self):
        self.assertEqual(assess_location(row(), [zone(1), zone('1')])['status'], 'invalid_zone')
        result = assess_location(row(), [zone(1), zone(2, 'subzona', '1')])
        self.assertEqual(result['status'], 'exact_zone')
        self.assertEqual(result['selected_zone_id'], 2)

    def test_inactive_bad_zones_are_ignored(self):
        inactive = zone(2, coordinates=[])
        inactive['activo'] = False
        self.assertEqual(assess_location(row(), [zone(1), inactive])['status'], 'exact_zone')

    def test_cycle_is_not_assigned(self):
        zones = [zone(1, parent=2), zone(2, 'subzona', 1)]
        self.assertEqual(assess_location(row(), zones)['status'], 'ambiguous')

    def test_inputs_are_unchanged_and_geometry_cache_tracks_content(self):
        listing, zones = row(), [zone()]
        before = copy.deepcopy((listing, zones))
        first = assess_location(listing, zones)
        self.assertEqual((listing, zones), before)
        zones[0]['coordenadas'] = box(0, 0, 1, 1)
        second = assess_location(listing, zones)
        self.assertEqual(first['status'], 'exact_zone')
        self.assertEqual(second['status'], 'exact_unzoned')

    def test_polygon_with_straight_extra_vertex_is_valid(self):
        polygon = box()
        polygon.insert(1, [-16.5, -71.5])
        self.assertEqual(assess_location(row(), [zone(coordinates=polygon)])['status'], 'exact_zone')


if __name__ == '__main__':
    unittest.main()
