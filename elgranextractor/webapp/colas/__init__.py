"""
App de colas para gestión de tareas asíncronas con Celery.

Esta app maneja todas las tareas en segundo plano del sistema,
incluyendo captura web, análisis de cambios y notificaciones.
"""

from .celery import app as celery_app

__all__ = ('celery_app',)