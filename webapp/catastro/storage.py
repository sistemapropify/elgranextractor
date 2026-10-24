"""Private R2 transport. Credentials stay outside source code and responses."""
import datetime
import hashlib
import hmac
import os
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class StorageError(RuntimeError):
    def __init__(self, message, http_status=None):
        super().__init__(message)
        self.http_status = http_status


class PreconditionFailed(StorageError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def credentials(path=None):
    values = {}
    path = Path(path or os.environ.get('CATASTRO_R2_CREDENTIALS_FILE') or
                Path.home() / '.codex/secrets/prometeo-catastro-r2.env')
    if path.is_file():
        values = dict(line.strip().split('=', 1) for line in path.read_text().splitlines()
                      if line.strip() and not line.lstrip().startswith('#'))
    for key in ('R2_ACCOUNT_ID', 'R2_BUCKET', 'R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY'):
        if os.environ.get(key):
            values[key] = os.environ[key]
    if not all(values.get(k) for k in ('R2_ACCOUNT_ID', 'R2_BUCKET', 'R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY')):
        raise StorageError('Configura las credenciales privadas de R2 en este servidor.')
    # Derive the endpoint; never transmit keys to an arbitrary configured host.
    import re
    if not re.fullmatch('[a-fA-F0-9]{32}', values['R2_ACCOUNT_ID']):
        raise StorageError('La cuenta R2 configurada no es válida.')
    if not re.fullmatch('[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]', values['R2_BUCKET']):
        raise StorageError('El bucket configurado no es válido.')
    return values


class R2:
    DEFAULT_READ_LIMIT = 20_000_000
    MANIFEST_READ_LIMIT = 256 * 1024 * 1024

    def __init__(self, values=None, timeout=30):
        self.values = values or credentials()
        self.timeout = max(1, min(float(timeout), 30))
        self.bucket = self.values['R2_BUCKET']
        self.host = self.values['R2_ACCOUNT_ID'] + '.r2.cloudflarestorage.com'
        self.opener = build_opener(NoRedirect())

    def request(self, method, key, data=b'', content_type=None, *, condition=None,
                read_limit=None):
        if not key.startswith('geollaqta/') or '..' in key.split('/'):
            raise StorageError('Ruta catastral no válida.')
        now = datetime.datetime.now(datetime.timezone.utc)
        stamp, day = now.strftime('%Y%m%dT%H%M%SZ'), now.strftime('%Y%m%d')
        uri = '/' + quote(self.bucket + '/' + key, safe='/~')
        digest = hashlib.sha256(data).hexdigest()
        headers = {'host': self.host, 'x-amz-date': stamp, 'x-amz-content-sha256': digest}
        if content_type:
            headers['content-type'] = content_type
        if method == 'PUT':
            headers['x-amz-meta-sha256'] = digest
        if condition:
            name, value = condition
            if name not in ('if-match', 'if-none-match') or not isinstance(value, str) or '\n' in value or '\r' in value:
                raise StorageError('Condición de guardado no válida.')
            headers[name] = value
        signed = ';'.join(sorted(headers))
        canonical_headers = ''.join(k + ':' + headers[k] + '\n' for k in sorted(headers))
        canonical = '\n'.join([method, uri, '', canonical_headers, signed, digest])
        scope = day + '/auto/s3/aws4_request'
        to_sign = '\n'.join(['AWS4-HMAC-SHA256', stamp, scope, hashlib.sha256(canonical.encode()).hexdigest()])
        secret = ('AWS4' + self.values['R2_SECRET_ACCESS_KEY']).encode()
        for part in (day, 'auto', 's3', 'aws4_request'):
            secret = hmac.new(secret, part.encode(), hashlib.sha256).digest()
        signature = hmac.new(secret, to_sign.encode(), hashlib.sha256).hexdigest()
        headers['Authorization'] = ('AWS4-HMAC-SHA256 Credential=' + self.values['R2_ACCESS_KEY_ID'] +
                                    '/' + scope + ', SignedHeaders=' + signed + ', Signature=' + signature)
        req = Request('https://' + self.host + uri, method=method, headers=headers,
                      data=data if method == 'PUT' else None)
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                limit = self.DEFAULT_READ_LIMIT + 1 if read_limit is None else read_limit
                return response.read(limit), dict(response.headers)
        except HTTPError as exc:
            error = PreconditionFailed if exc.code == 412 else StorageError
            raise error('R2 respondió HTTP ' + str(exc.code) + '.', exc.code) from None
        except (URLError, TimeoutError, OSError):
            raise StorageError('No se pudo conectar con R2; la carga queda pendiente.') from None

    def put_verified(self, key, data, content_type):
        for attempt in range(3):
            try:
                self._put_verified(key, data, content_type)
                return
            except StorageError as exc:
                transient = 'conectar' in str(exc) or any('HTTP ' + code in str(exc) for code in ('429','500','502','503','504'))
                if not transient or attempt == 2:
                    raise
                time.sleep(attempt + 1)

    def _put_verified(self, key, data, content_type):
        self.request('PUT', key, data, content_type)
        _, headers = self.request('HEAD', key)
        headers = {k.lower(): v for k, v in headers.items()}
        if (headers.get('x-amz-meta-sha256') != hashlib.sha256(data).hexdigest()
                or int(headers.get('content-length', -1)) != len(data)):
            raise StorageError('R2 no confirmó la integridad del archivo cargado.')

    def get(self, key, max_bytes=None):
        maximum = self.DEFAULT_READ_LIMIT if max_bytes is None else int(max_bytes)
        if maximum < 1 or maximum > self.MANIFEST_READ_LIMIT:
            raise StorageError('Límite de lectura de R2 no válido.')
        data, headers = self.request('GET', key, read_limit=maximum + 1)
        if len(data) > maximum:
            raise StorageError('El archivo supera el límite de lectura.')
        return data, headers

    def get_manifest(self, key):
        """Read a validated lot manifest without applying the small-object limit."""
        return self.get(key, max_bytes=self.MANIFEST_READ_LIMIT)

    def put_conditional(self, key, data, etag=None):
        """Atomic replacement shared by all application instances."""
        return self.request('PUT', key, data, 'application/json',
                            condition=('if-match', etag) if etag else ('if-none-match', '*'))

    def list_prefixes(self, prefix, delimiter='/', max_pages=25):
        """List logical folders without reading every archived object."""
        if not prefix.startswith('geollaqta/') or '..' in prefix.split('/'):
            raise StorageError('Prefijo catastral no válido.')
        if not isinstance(delimiter, str) or delimiter not in ('/', ''):
            raise StorageError('Delimitador no válido.')
        if type(max_pages) is not int or not 1 <= max_pages <= 100:
            raise StorageError('Límite de páginas no válido.')
        import xml.etree.ElementTree as ET
        from urllib.parse import quote_plus
        folders, token, pages = [], None, 0
        while pages < max_pages:
            pages += 1
            now = datetime.datetime.now(datetime.timezone.utc)
            stamp, day = now.strftime('%Y%m%dT%H%M%SZ'), now.strftime('%Y%m%d')
            query_values = {'list-type': '2', 'prefix': prefix, 'max-keys': '1000'}
            if delimiter:
                query_values['delimiter'] = delimiter
            if token:
                query_values['continuation-token'] = token
            query = '&'.join(quote_plus(k) + '=' + quote_plus(v)
                             for k, v in sorted(query_values.items()))
            payload = hashlib.sha256(b'').hexdigest()
            headers = {'host': self.host, 'x-amz-date': stamp, 'x-amz-content-sha256': payload}
            signed = ';'.join(sorted(headers))
            canonical_headers = ''.join(k + ':' + headers[k] + '\n' for k in sorted(headers))
            canonical = '\n'.join(['GET', '/' + self.bucket, query, canonical_headers,
                                   signed, payload])
            scope = day + '/auto/s3/aws4_request'
            to_sign = '\n'.join(['AWS4-HMAC-SHA256', stamp, scope,
                                 hashlib.sha256(canonical.encode()).hexdigest()])
            secret = ('AWS4' + self.values['R2_SECRET_ACCESS_KEY']).encode()
            for part in (day, 'auto', 's3', 'aws4_request'):
                secret = hmac.new(secret, part.encode(), hashlib.sha256).digest()
            signature = hmac.new(secret, to_sign.encode(), hashlib.sha256).hexdigest()
            headers['Authorization'] = ('AWS4-HMAC-SHA256 Credential=' +
                self.values['R2_ACCESS_KEY_ID'] + '/' + scope +
                ', SignedHeaders=' + signed + ', Signature=' + signature)
            req = Request('https://' + self.host + '/' + self.bucket + '?' + query,
                          method='GET', headers=headers)
            try:
                with self.opener.open(req, timeout=self.timeout) as response:
                    body = response.read(20_000_001)
            except HTTPError as exc:
                raise StorageError('R2 respondió HTTP ' + str(exc.code) + '.', exc.code) from None
            except (URLError, TimeoutError, OSError):
                raise StorageError('No se pudo listar el archivo catastral en R2.') from None
            root = ET.fromstring(body)
            namespace = {'s': 'http://s3.amazonaws.com/doc/2006-03-01/'}
            folders.extend(element.findtext('s:Prefix', default='', namespaces=namespace)
                           for element in root.findall('s:CommonPrefixes', namespace))
            truncated = root.findtext('s:IsTruncated', default='false',
                                      namespaces=namespace).lower() == 'true'
            token = root.findtext('s:NextContinuationToken', default=None,
                                  namespaces=namespace)
            if not truncated or not token:
                return {'prefixes': folders, 'truncated': False, 'pages': pages}
        return {'prefixes': folders, 'truncated': True, 'pages': pages}
