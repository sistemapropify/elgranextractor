from django.test import SimpleTestCase

from .migration_audit import audit_district


class FakeAuditGateway:
    def __init__(self, identities, geometry, attributes, media):
        self.identities = identities
        self.geometry = geometry
        self.attributes = attributes
        self.media = media
        self.revision = 77

    def read_many(self, queries):
        results = []
        for query in queries:
            sql = query['sql']
            if "s.field='$geometry'" in sql:
                results.append(self.geometry)
            elif 'current_attributes' in sql:
                results.append([self.attributes])
            elif 'GROUP BY m.kind' in sql:
                results.append(self.media)
            else:
                results.append(self.identities)
        return results


class MigrationAuditTests(SimpleTestCase):
    def test_complete_district_passes_the_publication_gate(self):
        gateway = FakeAuditGateway(
            identities=[
                {'source_feature_id': 'a', 'entity_id': 'e1'},
                {'source_feature_id': 'b', 'entity_id': 'e2'},
            ],
            geometry=[{'source_feature_id': 'a'}, {'source_feature_id': 'b'}],
            attributes={
                'entities': 2, 'missing_current_attributes': 0,
                'with_land_area': 2, 'with_built_area': 2,
                'with_front': 2, 'with_floors': 2,
            },
            media=[{'kind': 'source_manifest', 'count': 2}],
        )
        audit = audit_district(gateway, '040126', ['a', 'b'], revision=77)
        self.assertEqual(audit['status'], 'passed')
        self.assertEqual(audit['linked_lots'], 2)
        self.assertEqual(audit['errors'], [])
        self.assertEqual(audit['warnings'], [])

    def test_missing_geometry_and_current_attributes_block_publication(self):
        gateway = FakeAuditGateway(
            identities=[
                {'source_feature_id': 'a', 'entity_id': 'e1'},
                {'source_feature_id': 'b', 'entity_id': 'e2'},
            ],
            geometry=[{'source_feature_id': 'a'}],
            attributes={
                'entities': 2, 'missing_current_attributes': 1,
                'with_land_area': 1, 'with_built_area': 1,
                'with_front': 1, 'with_floors': 1,
            },
            media=[],
        )
        audit = audit_district(gateway, '040126', ['a', 'b'])
        self.assertEqual(audit['status'], 'failed')
        self.assertEqual(audit['missing_geometry'], 1)
        self.assertEqual(audit['missing_current_attributes'], 1)
        self.assertGreaterEqual(len(audit['errors']), 2)

    def test_optional_coverage_gaps_are_warnings_not_verified_data(self):
        gateway = FakeAuditGateway(
            identities=[
                {'source_feature_id': 'a', 'entity_id': 'e1'},
                {'source_feature_id': 'b', 'entity_id': 'e2'},
            ],
            geometry=[{'source_feature_id': 'a'}, {'source_feature_id': 'b'}],
            attributes={
                'entities': 2, 'missing_current_attributes': 0,
                'with_land_area': 1, 'with_built_area': 2,
                'with_front': 0, 'with_floors': 2,
            },
            media=[],
        )
        audit = audit_district(gateway, '040126', ['a', 'b'])
        self.assertEqual(audit['status'], 'warnings')
        self.assertEqual(audit['errors'], [])
        self.assertTrue(any('área de terreno' in value for value in audit['warnings']))
