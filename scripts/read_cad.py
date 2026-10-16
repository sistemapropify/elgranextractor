"""Background DWG reader used by the private plan workspace."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'webapp'))
from catastro.cad_reader import run_import

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--job-id', required=True)
    run_import(parser.parse_args().job_id)
