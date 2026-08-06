# -*- coding: utf-8 -*-
"""
Inicia un nuevo trabajo de scraping para Adondevivir.
Ejecutar desde webapp/: python start_scraping_job.py
"""
import os, sys, threading, time

# Forzar UTF-8 en stdout/stderr para evitar errores de encoding
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

import django
django.setup()

from django.utils import timezone
from ingestas.models import ScrapingJob
from colas.scraping_tasks import scraping_task_run

# Primero, reconciliar jobs huerfanos (jobs en running que ya no corresponden)
from ingestas.views import _reconcile_stale_scraping_jobs
_reconcile_stale_scraping_jobs()

# Crear nuevo job
job = ScrapingJob.objects.create(
    estado='running',
    iniciado_en=timezone.now(),
    parametros={'portales': ['adondevivir']},
)
print(f'[OK] Job #{job.id} creado para ADONDEVIVIR')

thread = threading.Thread(
    target=scraping_task_run,
    args=(job.id,),
    daemon=False,
    name=f'scraping-job-{job.id}',
)
thread.start()
print(f'[OK] Thread {thread.name} iniciado')
print(f'[INFO] Dashboard: http://127.0.0.1:8000/ingestas/scraping/dashboard/')

# Mantener vivo mientras el thread de scraping corra
while thread.is_alive():
    time.sleep(5)
