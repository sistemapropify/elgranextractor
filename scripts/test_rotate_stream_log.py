import io
import tempfile
import unittest
from pathlib import Path

from rotate_stream_log import rotate_stream


class LogRotationTests(unittest.TestCase):
    def test_unbroken_stream_retains_recent_output_with_bounded_disk_usage(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'worker.log'
            payload = b'A' * 160000 + b'recent-worker-output'
            rotate_stream(io.BytesIO(payload), path, max_bytes=32768, backups=2)
            files = list(Path(directory).glob('worker.log*'))
            self.assertEqual(len(files), 3)
            self.assertTrue(all(file.stat().st_size <= 32768 for file in files))
            self.assertTrue(path.read_bytes().endswith(b'recent-worker-output'))

    def test_multibyte_text_survives_chunk_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'worker.log'
            payload = ('Evaluación de lotes · ' * 1000).encode('utf-8')
            rotate_stream(io.BytesIO(payload), path, max_bytes=65536)
            self.assertEqual(path.read_bytes(), payload)


if __name__ == '__main__':
    unittest.main()
