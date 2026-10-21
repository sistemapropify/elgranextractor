"""Inspect a user-provided plan entirely in RAM; names do not prove semantics."""
import hashlib


def inspect(body):
    if not body.lstrip().startswith(b'%PDF-') or len(body) > 12 * 1024 * 1024:
        raise ValueError('Se requiere un PDF de hasta 12 MB.')
    import fitz
    try:
        with fitz.open(stream=body, filetype='pdf') as document:
            if document.needs_pass or not 1 <= len(document) <= 100:
                raise ValueError('El PDF está protegido o excede las 100 páginas.')
            return {'pages':len(document), 'layers':sorted({str(v.get('name','')) for v in document.get_ocgs().values()}),
                    'sha256':hashlib.sha256(body).hexdigest()}
    except fitz.FileDataError:
        raise ValueError('No se pudo leer el PDF.') from None
