import os,tempfile
from pathlib import Path
from unittest.mock import patch
from django.test import SimpleTestCase
from .state import State
from .jobs import start_job


class CollectorWorkingDirectoryTests(SimpleTestCase):
    def test_new_working_drive_keeps_existing_ledger_and_remote_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'archive';working=Path(directory)/'working'
            with patch.dict(os.environ,{'CATASTRO_DATA_DIR':str(root),'CATASTRO_STATE_DB':str(root/'estado.sqlite3'),'CATASTRO_COLLECTOR_DATA_DIR':str(working),'CATASTRO_EXECUTION_MODE':'server'}):
                state=State();state.save_lot('04012603036035','040126',object_id=1,status='complete',uploaded=1,missing=0,reports=1,photos=1,bytes=100,error='');state.close()
                with patch('catastro.jobs.credentials'),patch('catastro.jobs.subprocess.Popen') as process:
                    process.return_value.pid=123
                    job=start_job('040126',workers=10)
                environment=process.call_args.kwargs['env']
                self.assertEqual(environment['CATASTRO_DATA_DIR'],str(working))
                self.assertEqual(Path(environment['CATASTRO_STATE_DB']),root/'estado.sqlite3')
                self.assertEqual(environment['CATASTRO_KEEP_LOCAL'],'0')
                with patch.dict(os.environ,environment):
                    state=State()
                    try:
                        self.assertEqual(state.lot('04012603036035')['uploaded'],1)
                        self.assertEqual(state.job(job)['workers'],10)
                    finally:state.close()
