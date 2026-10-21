"""Small Path-compatible RAM store for documents; never opens an OS file."""
from pathlib import PurePosixPath
from types import SimpleNamespace
from threading import RLock


class MemoryPath:
    def __init__(self, store=None, parts=()):
        self.store = store if store is not None else {'files': {}, 'dirs': {()}, 'lock': RLock(), 'bytes': 0}
        self.parts = parts

    def __truediv__(self, value):
        segments = PurePosixPath(str(value)).parts
        if any(p in ('..', '/') for p in segments):
            raise ValueError('Ruta de memoria no válida.')
        return MemoryPath(self.store, self.parts + segments)

    @property
    def name(self):
        return self.parts[-1] if self.parts else 'ram'

    def with_name(self, name):
        return MemoryPath(self.store, self.parts[:-1]) / name

    def mkdir(self, parents=False, exist_ok=False):
        with self.store['lock']:
            for i in range(len(self.parts)+1):
                self.store['dirs'].add(self.parts[:i])

    def is_file(self):
        return self.parts in self.store['files']

    def exists(self):
        return self.is_file() or self.parts in self.store['dirs']

    def read_bytes(self):
        with self.store['lock']:
            return self.store['files'][self.parts]

    def read_text(self, encoding='utf8'):
        return self.read_bytes().decode(encoding)

    def write_bytes(self, body):
        with self.store['lock']:
            previous = len(self.store['files'].get(self.parts, b''))
            if self.store['bytes'] - previous + len(body) > 512 * 1024 * 1024:
                raise RuntimeError('Se alcanzó el límite de RAM del recolector; avance confirmado en Cloudflare conservado.')
            self.store['files'][self.parts] = body
            self.store['bytes'] += len(body)-previous
        return len(body)

    def replace(self, destination):
        with self.store['lock']:
            if destination.parts in self.store['files']:
                self.store['bytes'] -= len(self.store['files'][destination.parts])
            self.store['files'][destination.parts] = self.store['files'].pop(self.parts)
        return destination

    def unlink(self, missing_ok=False):
        with self.store['lock']:
            if self.parts not in self.store['files']:
                if missing_ok:return
                raise FileNotFoundError(self.name)
            self.store['bytes'] -= len(self.store['files'].pop(self.parts))

    def stat(self):
        return SimpleNamespace(st_size=len(self.read_bytes()))

    def iterdir(self):
        with self.store['lock']:
            children = {p for p in set(self.store['files']) | self.store['dirs'] if p[:-1] == self.parts and p != self.parts}
        return iter(MemoryPath(self.store, p) for p in children)

    def rglob(self, pattern):
        with self.store['lock']:
            files = [p for p in self.store['files'] if p[:len(self.parts)] == self.parts]
        return iter(MemoryPath(self.store, p) for p in files)

    def rmdir(self):
        with self.store['lock']:
            if any(self.iterdir()):raise OSError('La carpeta de RAM no está vacía.')
            self.store['dirs'].discard(self.parts)
