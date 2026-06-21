"""
URLs de la app whatsapp_extractor.

Define las rutas para el dashboard de monitoreo de extracciones
y la gestión de sesiones de grupos WhatsApp.
"""
from django.urls import path
from . import views

app_name = 'whatsapp_extractor'

urlpatterns = [
    # Dashboard principal de extracciones
    path(
        '',
        views.ExtractorDashboardView.as_view(),
        name='dashboard',
    ),
    # Detalle de una ejecución (log)
    path(
        'log/<int:pk>/',
        views.ExtractorLogDetailView.as_view(),
        name='log_detail',
    ),
    # Lista de grupos configurados
    path(
        'grupos/',
        views.GrupoSessionListView.as_view(),
        name='grupo_list',
    ),
    # Crear nuevo grupo
    path(
        'grupo/nuevo/',
        views.GrupoSessionCreateView.as_view(),
        name='grupo_create',
    ),
    # Detalle de un grupo
    path(
        'grupo/<int:pk>/',
        views.GrupoSessionDetailView.as_view(),
        name='grupo_detail',
    ),
    # Activar/desactivar grupo
    path(
        'grupo/<int:pk>/toggle/',
        views.GrupoSessionToggleView.as_view(),
        name='grupo_toggle',
    ),
    # Ejecutar extracción manual para un grupo
    path(
        'grupo/<int:pk>/extraer/',
        views.GrupoSessionExtraerView.as_view(),
        name='grupo_extraer',
    ),
    # API: últimas ejecuciones (JSON)
    path(
        'api/ultimos-logs/',
        views.UltimosLogsApiView.as_view(),
        name='api_ultimos_logs',
    ),
    # API: entradas de log detalladas (para terminal en vivo)
    path(
        'api/log-entries/',
        views.LogEntriesApiView.as_view(),
        name='api_log_entries',
    ),
    # API: estadísticas resumidas (JSON)
    path(
        'api/estadisticas/',
        views.EstadisticasApiView.as_view(),
        name='api_estadisticas',
    ),
    # Subir archivo de extracción WhatsApp
    path(
        'upload/',
        views.UploadExtractFileView.as_view(),
        name='upload_extract_file',
    ),
    # Gestión de archivos subidos
    path(
        'archivos/',
        views.FileManagementView.as_view(),
        name='file_management',
    ),
    # Detalle de un archivo
    path(
        'archivo/<int:pk>/',
        views.ArchivoDetailView.as_view(),
        name='archivo_detail',
    ),
    # Reprocesar un archivo (vía Celery)
    path(
        'archivo/<int:pk>/reprocesar/',
        views.ReprocesarArchivoView.as_view(),
        name='archivo_reprocesar',
    ),
    # Procesar un archivo manualmente (síncrono, sin Celery)
    path(
        'archivo/<int:pk>/procesar-manual/',
        views.ProcesarArchivoManualView.as_view(),
        name='archivo_procesar_manual',
    ),
    # Procesar con progreso en vivo (recomendado)
    path(
        'archivo/<int:pk>/procesar/',
        views.ProcesarArchivoConProgresoView.as_view(),
        name='archivo_progreso',
    ),
    # Pausar procesamiento
    path(
        'archivo/<int:pk>/pausar/',
        views.PausarProcesamientoView.as_view(),
        name='archivo_pausar',
    ),
    # Reanudar procesamiento
    path(
        'archivo/<int:pk>/reanudar/',
        views.ReanudarProcesamientoView.as_view(),
        name='archivo_reanudar',
    ),
    # Detener/cancelar procesamiento
    path(
        'archivo/<int:pk>/detener/',
        views.DetenerProcesamientoView.as_view(),
        name='archivo_detener',
    ),
    # API para requerimientos en tiempo real
    path(
        'api/requerimientos-en-tiempo-real/',
        views.RequerimientosEnTiempoRealApiView.as_view(),
        name='api_requerimientos_en_tiempo_real',
    ),
]
