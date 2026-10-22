"""Run on the extraction host with COFOPRI access, not inside the Azure web app."""
import argparse
import hashlib
import os
import socket
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'webapp'))
from catastro.external_worker import Control, run_once, ControlError
from catastro.storage import credentials


def source_available():
    for host in ('geoportal.cofopri.gob.pe','catastro.cofopri.gob.pe'):
        try:
            with socket.create_connection((host,443),timeout=5):
                pass
        except OSError:
            return False
    return True


def service_once(control, root):
    presence=control.call('claim',{'claim':False,'source_status':'unchecked'})
    if not presence.get('pending'):
        return None
    if not source_available():
        control.call('claim',{'claim':False,'source_status':'unavailable'})
        return None
    return run_once(control,root)


def main():
    parser = argparse.ArgumentParser(description='Recolector externo controlado por el dashboard catastral.')
    parser.add_argument('--url',required=True,help='Origen del dashboard, HTTPS en producción.')
    parser.add_argument('--once',action='store_true',help='Atender una ejecución y salir.')
    parser.add_argument('--wait-source',action='store_true',help='Esperar y reintentar si COFOPRI no acepta conexiones.')
    parser.add_argument('--token-file',type=Path,default=Path.home()/'.codex/secrets/prometeo-catastro-worker.token')
    parser.add_argument('--data-dir',type=Path,help='Directorio privado de reanudación; no comparte la cola local.')
    args = parser.parse_args()
    try:
        credentials()
        token = os.environ.get('CATASTRO_WORKER_TOKEN') or args.token_file.read_text().strip()
        control = Control(args.url,token)
        root = args.data_dir or Path.home()/'.codex/catastro-workers'/hashlib.sha256(args.url.rstrip('/').encode()).hexdigest()[:16]
        while True:
            try:
                result = service_once(control,root) if args.wait_source else run_once(control,root)
                if result:
                    print('Ejecución finalizada; avance comunicado al dashboard.',flush=True)
            except ControlError as error:
                if args.once:
                    raise
                print(str(error)+' Se conserva el avance y se reintentará.',flush=True)
            except RuntimeError as error:
                print(str(error),file=sys.stderr,flush=True)
                if args.once:
                    return 1
            if args.once:
                return 0
            time.sleep(15)
    except (OSError, ValueError, RuntimeError) as error:
        print('No se pudo iniciar el recolector: '+(str(error) if isinstance(error,(ValueError,RuntimeError)) else 'revisa los archivos de configuración.'),file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
