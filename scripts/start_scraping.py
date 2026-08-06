"""
Inicia un nuevo trabajo de scraping para Adondevivir.
Ejecutar: python manage.py runscript start_scraping
O directamente: python manage.py shell < scripts/start_scraping.py
"""
import os
import sys

# Asegurar que estamos en el directorio correcto
os.chdir(os.path.join(os.path.dirname(__file__), '..', 'webapp'))
sys.path.insert(0, os.getcwd())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

import django
django.setup()

from datetime import datetime
from ingestas.models import ScrapingJob
from colas.scraping_tasks import scraping_task_run
from django.utils import timezone

# Crear un nuevo job solo para Adondevivir
job = ScrapingJob.objects.create(
    estado='running',
    iniciado_en=timezone.now(),
    parametros={
        'portales': ['adondevivir'],
    }
)
print(f"✅ ScrapingJob #{job.id} creado para ADONDEVIVIR")

# Iniciar scraping en un thread
import threading
thread = threading.Thread(
    target=scraping_task_run,
    args=(job.id,),
    daemon=True,
    name=f'scraping-job-{job.id}',
)
thread.start()
print(f"🚀 Scraping iniciado en thread {thread.name}")
print(f"📊 Dashboard: http://127.0.0.1:8000/ingestas/scraping/dashboard/")
