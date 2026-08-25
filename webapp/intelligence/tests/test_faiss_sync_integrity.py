"""Regresiones para la reconstrucción y auditoría del índice FAISS."""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from intelligence.services.faiss_index import FAISSIndexManager


class FAISSSyncIntegrityTests(SimpleTestCase):
    def tearDown(self):
        FAISSIndexManager._instances.clear()

    def test_hnsw_squared_l2_is_converted_to_cosine(self):
        self.assertEqual(FAISSIndexManager.distance_to_similarity(0.0), 1.0)
        self.assertEqual(FAISSIndexManager.distance_to_similarity(1.0), 0.5)
        self.assertEqual(FAISSIndexManager.distance_to_similarity(2.0), 0.0)
        self.assertEqual(FAISSIndexManager.distance_to_similarity(4.0), 0.0)

    def test_build_rejects_mismatched_document_mapping(self):
        manager = FAISSIndexManager('test-integrity')
        manager._faiss_available = True
        with self.assertRaisesRegex(ValueError, 'document IDs'):
            manager.build_index([b'not-used'], [])

    @patch('intelligence.models.IntelligenceDocument.objects')
    def test_audit_detects_missing_faiss_document(self, objects):
        embedding = b'\x00' * (384 * 4)
        objects.filter.return_value.values_list.return_value = [
            ('doc-a', embedding),
            ('doc-b', embedding),
        ]
        manager = FAISSIndexManager('audit-test')
        manager.is_loaded = True
        manager.id_map = {0: 'doc-a'}
        manager.index = MagicMock(ntotal=1, d=384)
        FAISSIndexManager._instances['audit-test'] = manager

        audit = FAISSIndexManager.verify_collection('audit-test', 384)

        self.assertFalse(audit['consistent'])
        self.assertEqual(audit['missing_ids'], 1)
        self.assertEqual(audit['extra_ids'], 0)

