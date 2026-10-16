"""Install the pinned official GNU LibreDWG Windows reader, verifying its release hash."""
import hashlib
import io
import json
import os
from pathlib import Path
import zipfile
import requests

VERSION = '0.14'
SHA256 = '1ad7e15344d20b3426c3435b078d82fb84b35062815946b2cca9c5fc9810fea8'


def main():
    if os.name != 'nt':
        raise SystemExit('On Linux install the official GNU LibreDWG dwg2dxf executable and configure CATASTRO_DWG_CONVERTER.')
    url = f'https://github.com/LibreDWG/libredwg/releases/download/{VERSION}/libredwg-{VERSION}-win64.zip'
    response = requests.get(url, timeout=90)
    response.raise_for_status()
    if hashlib.sha256(response.content).hexdigest() != SHA256:
        raise SystemExit('Release checksum mismatch; nothing installed.')
    root = Path.home() / '.codex/tools/libredwg' / VERSION
    root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        for info in archive.infolist():
            if not (root / info.filename).resolve().is_relative_to(root.resolve()):
                raise SystemExit('Unsafe archive path; nothing extracted.')
        archive.extractall(root)
    license = requests.get(f'https://raw.githubusercontent.com/LibreDWG/libredwg/{VERSION}/COPYING', timeout=30)
    license.raise_for_status()
    (root / 'COPYING').write_bytes(license.content)
    (root / 'release.json').write_text(json.dumps({'version': VERSION, 'url': url, 'sha256': SHA256}), encoding='utf8')
    print('GNU LibreDWG reader installed and checksum verified.')


if __name__ == '__main__':
    main()
