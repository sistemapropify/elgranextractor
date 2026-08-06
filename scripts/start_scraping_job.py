"""
Inicia un nuevo trabajo de scraping para Adondevivir.
Ejecutar: python manage.py runscript start_scraping_job
"""
import os, sys, threading

os.chdir(os.path.join(os.path.dirname(__file__), '..', 'webapp'))
sys.path.insert(0, os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

import django
django.setup()

from django.utils import timezone
from ingestas.models import ScrapingJob
from colas.scraping_tasks import scraping_task_run

job = ScrapingJob.objects.create(
    estado='running',
    iniciado_en=timezone.now(),
    parametros={'portales': ['adondevivir']},
)
print(f'Job #{job.id} creado')

thread = threading.Thread(
    target=scraping_task_run,
    args=(job.id,),
    daemon=True,
    name=f'scraping-job-{job.id}',
)
thread.start()
print(f'Thread {thread.name} iniciado')
print(f'Dashboard: http://127.0.0.1:8000/ingestas/scraping/dashboard/')
