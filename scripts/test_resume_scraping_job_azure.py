"""Exercise the production recovery transaction without network or a real database."""
import contextlib
import importlib.machinery
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from resume_scraping_job_azure import REMOTE, wait_for_release


class RecoveryTests(unittest.TestCase):
    def test_only_exact_live_release_allows_recovery(self):
        old = io.BytesIO(b'{"revision":"old"}')
        current = io.BytesIO(json.dumps({'revision': 'a' * 40}).encode())
        with patch('resume_scraping_job_azure.urllib.request.urlopen',
                   side_effect=[old, current]), patch('resume_scraping_job_azure.time.sleep'):
            wait_for_release('a' * 40, attempts=2)
        with patch('resume_scraping_job_azure.urllib.request.urlopen',
                   return_value=io.BytesIO(b'{"revision":"old"}')):
            with self.assertRaisesRegex(RuntimeError, 'job left unchanged'):
                wait_for_release('a' * 40, attempts=1)

    def run_recovery(self, *, dry=True, state='error', portal='properati',
                     other_active=0, same_release=False, update_rows=1):
        params = {'portales': [portal], 'checkpoints': {'properati': 4},
                  'untouched': {'keep': True}}
        revision = 'a' * 40
        if same_release:
            params['release_recovery'] = {'revision': revision}
        calls = []

        class Cursor:
            rowcount = update_rows

            def execute(self, sql, args):
                calls.append((sql, args))
                if sql.startswith('SELECT estado'):
                    self.rows = [(state, json.dumps(params), 133)]
                elif sql.startswith('SELECT COUNT'):
                    self.rows = [(other_active,)]
                elif sql.startswith('SELECT TOP'):
                    self.rows = [(119,)]
                elif sql.startswith('SELECT status'):
                    self.rows = [('pending', 18), ('saved', 133)]
                return self

            def fetchone(self):
                return self.rows[0]

            def fetchall(self):
                return self.rows

        class Connection:
            commits = 0

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def cursor(self):
                return Cursor()

            def commit(self):
                self.commits += 1

        db = Connection()
        driver = types.ModuleType('pytds')
        driver.__spec__ = importlib.machinery.ModuleSpec('pytds', loader=None)
        driver.connect = lambda **kwargs: db
        certifi = types.ModuleType('certifi')
        certifi.where = lambda: 'trusted-ca.pem'
        with tempfile.TemporaryDirectory() as folder, patch.dict(sys.modules,
                {'pytds': driver, 'certifi': certifi}), patch.dict('os.environ',
                dict(DB_HOST='fake', DB_NAME='fake', DB_USER='fake', DB_PASSWORD='fake')):
            source = REMOTE.replace('/tmp/propifai-release-recovery-',
                                    Path(folder).as_posix() + '/recovery-')
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exec(compile(source, '<remote-recovery>', 'exec'), {'REQUEST': {
                    'job_id': 229, 'revision': revision, 'dry_run': dry}})
        return json.loads(output.getvalue()), calls, db

    def test_dry_run_keeps_job_untouched(self):
        result, calls, db = self.run_recovery()
        self.assertEqual(result['candidates'], {'pending': 18, 'saved': 133})
        self.assertEqual(result['action'], 'would_resume')
        self.assertFalse(any(sql.startswith(('UPDATE', 'INSERT')) for sql, _ in calls))
        self.assertEqual(db.commits, 0)

    def test_recovery_preserves_checkpoint_and_records_release_once(self):
        result, calls, db = self.run_recovery(dry=False)
        updates = [args for sql, args in calls if sql.startswith('UPDATE')]
        self.assertEqual(len(updates), 1)
        params = json.loads(updates[0][0])
        self.assertEqual(params['checkpoints'], {'properati': 4})
        self.assertEqual(params['untouched'], {'keep': True})
        self.assertEqual(params['release_recovery']['revision'], 'a' * 40)
        self.assertEqual(result['state'], 'idle')
        self.assertEqual(db.commits, 1)

    def test_rerun_or_active_job_never_queues_again(self):
        for arguments in ({'same_release': True}, {'state': 'running'},
                          {'state': 'idle'}, {'state': 'completed'}):
            with self.subTest(arguments=arguments):
                _, calls, db = self.run_recovery(dry=False, **arguments)
                self.assertFalse(any(sql.startswith('UPDATE') for sql, _ in calls))
                self.assertEqual(db.commits, 0)

    def test_foreign_portal_and_concurrent_extraction_are_refused(self):
        for arguments in ({'portal': 'remax'}, {'other_active': 1}, {'state': 'paused'}):
            with self.subTest(arguments=arguments), self.assertRaises(RuntimeError):
                self.run_recovery(dry=False, **arguments)

    def test_changed_row_never_commits(self):
        with self.assertRaisesRegex(RuntimeError, 'changed during recovery'):
            self.run_recovery(dry=False, update_rows=0)


if __name__ == '__main__':
    unittest.main()
