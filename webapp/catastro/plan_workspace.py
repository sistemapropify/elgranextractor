"""RAM-only plan titles and notes for the local preview before D1 migration."""
from datetime import datetime, timezone
from threading import RLock
import re
import uuid


_lock = RLock()
_revision = 0
_items = {}
_notes = {}


def revision():
    with _lock:
        return _revision


def _key(value):
    if not isinstance(value, str) or not re.fullmatch(
            r'(?:source|source-version|dwg):[A-Za-z0-9][A-Za-z0-9_.:%-]{0,300}', value):
        raise ValueError('Identificador de plano no válido.')
    return value


def _expected(value):
    global _revision
    if type(value) is not int or value != _revision:
        raise ValueError('El estado local de planos cambió. Actualiza y vuelve a intentar.')


def annotations(keys):
    values = []
    for value in keys:
        value = _key(value)
        if value not in values:
            values.append(value)
    if len(values) > 200:
        raise ValueError('Consulta de notas fuera de límite.')
    with _lock:
        return {
            key: {
                **_items.get(key, {
                    'document_key': key,
                    'display_title': None,
                    'updated_at': None,
                    'updated_by': None,
                    'revision': 0,
                }),
                'note_count': len(_notes.get(key, [])),
            }
            for key in values
        }


def notes_for(key):
    key = _key(key)
    with _lock:
        return [dict(item) for item in reversed(_notes.get(key, []))]


def update_title(key, scope_ubigeo, title, expected_revision, actor):
    global _revision
    key = _key(key)
    if not re.fullmatch(r'[0-9]{6}', str(scope_ubigeo or '')):
        raise ValueError('UBIGEO no válido.')
    if not isinstance(title, str) or not title.strip() or len(title.strip()) > 300:
        raise ValueError('El título debe tener entre 1 y 300 caracteres.')
    with _lock:
        _expected(expected_revision)
        _revision += 1
        item = _items.setdefault(key, {'document_key': key})
        item.update(
            display_title=title.strip(),
            scope_ubigeo=scope_ubigeo,
            updated_at=datetime.now(timezone.utc).isoformat(),
            updated_by=str(actor)[:160],
            revision=_revision,
        )
        return {**item, 'revision': _revision}


def add_note(key, scope_ubigeo, note, expected_revision, actor):
    global _revision
    key = _key(key)
    if not re.fullmatch(r'[0-9]{6}', str(scope_ubigeo or '')):
        raise ValueError('UBIGEO no válido.')
    if not isinstance(note, str) or not note.strip() or len(note.strip()) > 4000:
        raise ValueError('La nota debe tener entre 1 y 4.000 caracteres.')
    with _lock:
        _expected(expected_revision)
        _revision += 1
        item = {
            'id': str(uuid.uuid4()),
            'document_key': key,
            'scope_ubigeo': scope_ubigeo,
            'note': note.strip(),
            'created_at': datetime.now(timezone.utc).isoformat(),
            'actor': str(actor)[:160],
            'revision': _revision,
        }
        _notes.setdefault(key, []).append(item)
        return dict(item)
