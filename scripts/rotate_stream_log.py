"""Keep background-worker stdout/stderr bounded, including streams without newlines."""
import codecs
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def rotate_stream(source, path, max_bytes=5 * 1024 * 1024, backups=3):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(path, maxBytes=max_bytes, backupCount=backups, encoding='utf-8')
    decoder = codecs.getincrementaldecoder('utf-8')('replace')
    try:
        while True:
            chunk = source.read1(min(8192, max_bytes // 4))
            text = decoder.decode(chunk, final=not chunk)
            if text:
                if handler.stream.tell() + len(text.encode('utf-8')) > max_bytes:
                    handler.doRollover()
                handler.stream.write(text)
                handler.stream.flush()
            if not chunk:
                break
    finally:
        handler.close()


if __name__ == '__main__':
    rotate_stream(sys.stdin.buffer, sys.argv[1])
