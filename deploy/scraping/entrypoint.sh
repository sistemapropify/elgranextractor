#!/bin/sh
set -eu
python -m scrapi.worker_smoke
python manage.py migrate --check --noinput
exec python manage.py scraping_watchdog
