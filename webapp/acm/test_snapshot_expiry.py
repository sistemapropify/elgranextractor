import json
import time
import zlib

from django.core import signing
from django.test import SimpleTestCase

from .access_data import cipher, unseal


class SnapshotExpiryTests(SimpleTestCase):
    def test_expired_authenticated_snapshot_is_identified_as_expired(self):
        token = cipher().encrypt_at_time(zlib.compress(json.dumps({'state': {}}).encode()),
                                         int(time.time()) - 1801).decode()
        with self.assertRaises(signing.SignatureExpired):
            unseal(token)

    def test_tampered_snapshot_is_not_labelled_as_expired(self):
        token = cipher().encrypt_at_time(zlib.compress(b'{"state":{}}'),
                                         int(time.time()) - 1801).decode()
        token = token[:-10] + ('A' if token[-10] != 'A' else 'B') + token[-9:]
        with self.assertRaises(signing.BadSignature) as error:
            unseal(token)
        self.assertNotIsInstance(error.exception, signing.SignatureExpired)

    def test_current_snapshot_still_decodes(self):
        token = cipher().encrypt(zlib.compress(b'{"state":{"value":123}}')).decode()
        self.assertEqual(unseal(token), {'state': {'value': 123}})
