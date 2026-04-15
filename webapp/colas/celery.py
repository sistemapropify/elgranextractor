"""
Configuración de Celery para el sistema de colas de tareas.

Este módulo configura Celery para usar la base de datos de Django como backend
y broker temporal, con planes de migración a Redis en el futuro.
"""

import os
from celery import Celery
from django.conf import settings

# Establecer el módulo de configuración de Django predeterminado
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

# Crear la aplicación Celery
app = Celery('gran_extractor')

# Configurar Celery usando la configuración de Django
app.config_from_object('django.conf:settings', namespace='CELERY')

# Configuración específica para usar base de datos como backend
app.conf.update(
    # Usar base de datos como broker (solución temporal)
    broker_url='memory://',
    result_backend='django-db',
    
    # Configuración de tareas
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='America/Lima',
    enable_utc=True,
    
    # Configuración de colas
    task_default_queue='default',
    task_queues={
        'default': {
            'exchange': 'default',
            'exchange_type': 'direct',
            'routing_key': 'default',
        },
        'capturas': {
            'exchange': 'capturas',
            'exchange_type': 'direct',
            'routing_key': 'capturas',
        },
        'analisis': {
            'exchange': 'analisis',
            'exchange_type': 'direct',
            'routing_key': 'analisis',
        },
        'notificaciones': {
            'exchange': 'notificaciones',
            'exchange_type': 'direct',
            'routing_key': 'notificaciones',
        },
    },
    
    # Rutas de tareas
    task_routes={
        'colas.tasks.revisar_fuente': {'queue': 'capturas'},
        'colas.tasks.procesar_captura': {'queue': 'capturas'},
        'colas.tasks.analizar_cambios': {'queue': 'analisis'},
        'colas.tasks.notificar_cambio': {'queue': 'notificaciones'},
        'colas.tasks.actualizar_frecuencias': {'queue': 'analisis'},
    },
    
    # Configuración de trabajadores
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    task_acks_late=True,
    worker_disable_rate_limits=True,
    
    # Configuración de beat (tareas periódicas)
    beat_schedule={
        'revisar-fuentes-activas-cada-hora': {
            'task': 'colas.tasks.revisar_fuentes_activas',
            'schedule': 3600.0,  # Cada hora
            'options': {'queue': 'capturas'},
        },
        'actualizar-frecuencias-diarias': {
            'task': 'colas.tasks.actualizar_frecuencias_automaticas',
            'schedule': 86400.0,  # Cada día
            'options': {'queue': 'analisis'},
        },
        'limpiar-capturas-antiguas': {
            'task': 'colas.tasks.limpiar_capturas_antiguas',
            'schedule': 43200.0,  # Cada 12 horas
            'options': {'queue': 'default'},
        },
        # Tareas RAG (SPEC-003)
        'sincronizar-colecciones-rag-cada-6-horas': {
            'task': 'intelligence.tasks.sincronizar_todas_colecciones_rag',
            'schedule': 21600.0,  # Cada 6 horas
            'options': {'queue': 'analisis'},
            'kwargs': {'force_full_sync': False}
        },
        'generar-embeddings-pendientes-cada-hora': {
            'task': 'intelligence.tasks.generar_embeddings_pendientes',
            'schedule': 3600.0,  # Cada hora
            'options': {'queue': 'analisis'},
            'kwargs': {'batch_size': 50}
        },
        'verificar-estado-rag-cada-12-horas': {
            'task': 'intelligence.tasks.verificar_estado_rag',
            'schedule': 43200.0,  # Cada 12 horas
            'options': {'queue': 'analisis'},
        },
        'limpiar-documentos-antiguos-cada-dia': {
            'task': 'intelligence.tasks.limpiar_documentos_antiguos',
            'schedule': 86400.0,  # Cada día
            'options': {'queue': 'default'},
            'kwargs': {'days_old': 30}
        },
    },
    
    # Configuración de resultados
    result_expires=86400,  # 24 horas
    task_track_started=True,
    task_time_limit=300,  # 5 minutos máximo por tarea
    task_soft_time_limit=240,  # 4 minutos antes de timeout suave
)

# Auto-descubrir tareas en todas las apps de Django
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)


@app.task(bind=True)
def debug_task(self):
    """Tarea de depuración para verificar que Celery funciona."""
    print(f'Request: {self.request!r}')


# Configuración para desarrollo
if settings.DEBUG:
    app.conf.update(
        worker_hijack_root_logger=False,
        worker_log_color=True,
        worker_log_format='[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
    )