"""Build-time only: install the reviewed Linux browser archive after hash verification."""
import hashlib
import json
import os
import tempfile
import urllib.request
import zipfile
from pathlib import Path

manifest = json.loads(Path('/build/browser.json').read_text())
destination = Path('/opt/camoufox')
destination.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory() as temp:
    archive = Path(temp) / 'browser.zip'
    digest = hashlib.sha256()
    with urllib.request.urlopen(manifest['url'], timeout=120) as response, archive.open('wb') as output:
        while chunk := response.read(1024 * 1024):
            digest.update(chunk)
            output.write(chunk)
    if digest.hexdigest() != manifest['sha256']:
        raise RuntimeError('Browser archive checksum mismatch')
    with zipfile.ZipFile(archive) as bundle:
        for info in bundle.infolist():
            target = (destination / info.filename).resolve()
            if destination not in target.parents and target != destination:
                raise RuntimeError('Invalid archive path')
        bundle.extractall(destination)
binary = destination / 'camoufox-bin'
if not binary.is_file() or not (destination / 'properties.json').is_file():
    raise RuntimeError('Browser release layout changed')
for name in ('camoufox', 'camoufox-bin', 'glxtest', 'vaapitest', 'pingsender', 'updater', 'crashreporter'):
    path = destination / name
    if path.exists():
        path.chmod(path.stat().st_mode | 0o555)
(destination / 'build-manifest.json').write_text(json.dumps(manifest))
# Camoufox 0.5 also resolves fonts and the fingerprint version through its
# active-install registry, even when executable_path is supplied explicitly.
from camoufox.pkgman import INSTALL_DIR
cache = Path(INSTALL_DIR)
(cache / 'browsers').mkdir(parents=True, exist_ok=True)
(cache / 'browsers' / 'pinned').symlink_to(destination, target_is_directory=True)
version, build = manifest['version'].split('-', 1)
(destination / 'version.json').write_text(json.dumps({'version': version, 'build': build, 'sha256': manifest['sha256']}))
(cache / '.0.5_FLAG').touch()
(cache / 'config.json').write_text(json.dumps({'active_version': 'browsers/pinned',
    'channel': 'official/stable', 'pinned': manifest['version']}))
