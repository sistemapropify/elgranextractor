"""The mutable local ledger can live outside a synced document archive."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from .state import State


class StateLocationTests(unittest.TestCase):
    def test_configured_existing_ledger_preserves_archive_and_progress(self):
        with tempfile.TemporaryDirectory() as folder:
            archive=Path(folder)/'archive'
            destination=Path(folder)/'private/estado.sqlite3'
            original=State(archive)
            original.save_upload('geollaqta/040126/test/datos.json','digest',123)
            original.save_lot('04012600000001','040126',status='complete',uploaded=1)
            destination.parent.mkdir()
            target=sqlite3.connect(destination)
            try:
                original.db.backup(target)
            finally:
                target.close()
            original.close()
            with patch.dict('os.environ',{'CATASTRO_STATE_DB':str(destination)}),patch('catastro.state.data_dir',return_value=archive):
                state=State()
                try:
                    self.assertEqual(state.root,archive)
                    self.assertEqual(state.uploaded_hash('geollaqta/040126/test/datos.json'),'digest')
                    self.assertEqual(state.lot('04012600000001')['uploaded'],1)
                    self.assertEqual(state.db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
                finally:
                    state.close()

    def test_new_target_cannot_silently_hide_existing_progress(self):
        with tempfile.TemporaryDirectory() as folder:
            archive=Path(folder)/'archive'
            state=State(archive);state.close()
            destination=Path(folder)/'private/estado.sqlite3'
            with patch.dict('os.environ',{'CATASTRO_STATE_DB':str(destination)}),patch('catastro.state.data_dir',return_value=archive):
                with self.assertRaisesRegex(RuntimeError,'necesita migración'):
                    State()
            self.assertFalse(destination.exists())

    def test_explicit_test_archive_does_not_use_environment_ledger(self):
        with tempfile.TemporaryDirectory() as folder:
            archive=Path(folder)/'test-archive'
            destination=Path(folder)/'private/estado.sqlite3'
            with patch.dict('os.environ',{'CATASTRO_STATE_DB':str(destination)}):
                state=State(archive)
                try:
                    state.save_upload('test','digest',5)
                    self.assertEqual(state.uploaded_hash('test'),'digest')
                finally:
                    state.close()
            self.assertTrue((archive/'estado.sqlite3').exists())
            self.assertFalse(destination.exists())
