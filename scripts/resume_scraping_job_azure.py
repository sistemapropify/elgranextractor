"""One authorized recovery after a verified release; never submits a challenge answer."""
import argparse
import base64
import json
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request


REMOTE = r'''
import importlib.util, json, os, subprocess, sys, urllib.request
from pathlib import Path
root = Path('/tmp/propifai-release-recovery-' + str(REQUEST['job_id']))
root.mkdir(exist_ok=True)
sys.path.insert(0, str(root / 'libs'))
if not importlib.util.find_spec('pytds'):
    bootstrap = root / 'pip.pyz'
    with urllib.request.urlopen('https://bootstrap.pypa.io/pip/pip.pyz', timeout=20) as response:
        bootstrap.write_bytes(response.read())
    installed = subprocess.run([sys.executable, str(bootstrap), 'install', '--quiet',
        '--disable-pip-version-check', '--target', str(root / 'libs'),
        'python-tds', 'pyOpenSSL<26', 'certifi'], capture_output=True, timeout=60)
    if installed.returncode:
        raise RuntimeError('Recovery SQL client installation failed')
import pytds, certifi
with pytds.connect(dsn=os.environ['DB_HOST'].removeprefix('tcp:').split(',')[0],
        database=os.environ['DB_NAME'], user=os.environ['DB_USER'], password=os.environ['DB_PASSWORD'],
        port=1433, cafile=certifi.where(), validate_host=True, autocommit=False,
        timeout=20, login_timeout=12, disable_connect_retry=True) as db:
    cursor = db.cursor()
    cursor.execute('SELECT estado,parametros,procesadas FROM scraping_jobs WITH (UPDLOCK,ROWLOCK) WHERE id=%s',
                   (REQUEST['job_id'],))
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError('Requested job does not exist')
    state, raw, processed = row
    params = json.loads(raw or '{}')
    if params.get('portales') != ['properati'] or params.get('native_verification') or params.get('execution_scope') == 'local_interactive':
        raise RuntimeError('Recovery is restricted to the authorized portable Properati job')
    previous = params.get('release_recovery') or {}
    if previous.get('revision') == REQUEST['revision'] or state in ('running', 'idle', 'completed'):
        print(json.dumps({'job_id':REQUEST['job_id'], 'state':state, 'action':'already_requested_or_active', 'saved':processed}))
    elif state not in ('error', 'stopped'):
        raise RuntimeError('Job is not in a recoverable terminal state')
    else:
        cursor.execute("SELECT COUNT(*) FROM scraping_jobs WHERE id<>%s AND (estado='idle' OR (estado IN ('running','paused') AND (lease_expires_at>SYSUTCDATETIME() OR (lease_expires_at IS NULL AND heartbeat_at>DATEADD(minute,-3,SYSUTCDATETIME())))))", (REQUEST['job_id'],))
        if cursor.fetchone()[0]:
            raise RuntimeError('Another extraction is active; refusing duplicate browser execution')
        cursor.execute("SELECT TOP 1 id FROM scraping_ejecuciones_portal WHERE job_id=%s AND portal='properati' ORDER BY id DESC", (REQUEST['job_id'],))
        run = cursor.fetchone()
        if run is None:
            raise RuntimeError('The job has no preserved portal run')
        cursor.execute('SELECT status,COUNT(*) FROM scraping_candidates WHERE run_id=%s GROUP BY status', (run[0],))
        candidates = dict(cursor.fetchall())
        result = {'job_id':REQUEST['job_id'], 'saved':processed, 'candidates':candidates,
            'checkpoint':(params.get('checkpoints') or {}).get('properati'), 'run_id':run[0]}
        if REQUEST['dry_run']:
            result.update(action='would_resume', state=state)
        else:
            backup = root / ('job-before-' + REQUEST['revision'] + '.json')
            backup.write_text(json.dumps({'state':state,'parameters':params,'saved':processed}), encoding='utf-8')
            backup.chmod(0o600)
            params['release_recovery'] = {'revision':REQUEST['revision'], 'previous_state':state}
            cursor.execute("UPDATE scraping_jobs SET estado='idle',execution_token=NULL,lease_expires_at=NULL,completado_en=NULL,mensaje_error=NULL,portal_actual=NULL,parametros=%s WHERE id=%s AND estado=%s",
                (json.dumps(params), REQUEST['job_id'], state))
            if cursor.rowcount != 1:
                raise RuntimeError('The job changed during recovery')
            context = json.dumps({'revision':REQUEST['revision'],'preserved_run_id':run[0],'saved':processed})
            cursor.execute('INSERT INTO scraping_logs (job_id,nivel,mensaje,evento,contexto,portal,propiedad_id,timestamp) VALUES (%s,%s,%s,%s,%s,%s,NULL,SYSDATETIMEOFFSET())',
                (REQUEST['job_id'],'warning','Version de verificacion publicada; reanudando desde la cola guardada.','recovery.requested',context,'properati'))
            db.commit()
            result.update(action='queued_after_verified_deployment', state='idle')
        print(json.dumps(result))
'''


def wait_for_release(revision, attempts=12):
    url = 'https://acm.propifai.com/static/js/scraping-verification-release.json?revision=' + revision
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=15) as response:
                marker = json.load(response)
            if marker.get('revision') == revision:
                return
        except (urllib.error.URLError, TimeoutError, ValueError):
            pass
        if attempt + 1 < attempts:
            time.sleep(5)
    raise RuntimeError('The public service is not serving the requested release; job left unchanged')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job-id', type=int, required=True)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if args.job_id <= 0 or not re.fullmatch('[0-9a-f]{40}', args.revision):
        parser.error('A positive job ID and full release commit SHA are required')
    if not args.dry_run:
        wait_for_release(args.revision)
    cli = shutil.which('az')
    if not cli:
        raise RuntimeError('Azure CLI is required for the existing authenticated identity')
    token = subprocess.run([cli, 'account', 'get-access-token', '--resource',
        'https://management.azure.com/', '--query', 'accessToken', '-o', 'tsv',
        '--only-show-errors'], check=True, capture_output=True, text=True, timeout=30).stdout.strip()
    request = {'job_id': args.job_id, 'revision': args.revision, 'dry_run': args.dry_run}
    code = 'REQUEST = ' + repr(request) + chr(10) + REMOTE
    encoded = base64.b64encode(code.encode()).decode()
    body = json.dumps({'command': 'bash -lc "echo ' + encoded + ' | base64 -d | python3"',
                       'dir': '/home/site/wwwroot'}).encode()
    endpoint = 'https://granextractorservice-emehaffsf8e2c7eg.scm.brazilsouth-01.azurewebsites.net/api/command'
    call = urllib.request.Request(endpoint, data=body, headers={
        'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(call, timeout=120) as response:
        result = json.load(response)
    if result.get('ExitCode') != 0:
        # SQL passwords, CAPTCHA answers and raw SDK errors never enter CI logs.
        raise RuntimeError('Server-side recovery failed; job left unchanged or transaction rolled back')
    payload = json.loads(result.get('Output', '').strip().splitlines()[-1])
    print(json.dumps(payload))


if __name__ == '__main__':
    main()
