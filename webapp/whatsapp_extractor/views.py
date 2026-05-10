"""
Vistas de la app whatsapp_extractor.

Proporciona un dashboard de monitoreo para las extracciones automáticas
de requerimientos desde WhatsApp, incluyendo:
    - Dashboard con resumen de ejecuciones
    - Detalle de logs de extracción
    - Gestión de sesiones de grupos
    - APIs JSON para consumo desde templates
"""
import json
import logging
import os
from typing import Dict, Any, List

from django.core.paginator import Paginator
from django.views.generic import (
    TemplateView,
    DetailView,
    ListView,
    RedirectView,
    View,
    CreateView,
    FormView,
)
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.db.models import Count, Avg, Sum, Q
from django.utils import timezone
from django.conf import settings

from requerimientos.models import Requerimiento
from whatsapp_extractor.models import (
    WhatsappGroupSession,
    ExtractorLog,
    ArchivoExtraccionWhatsApp,
    EstadoExtraccionChoices,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  DASHBOARD PRINCIPAL
# ─────────────────────────────────────────────


class ExtractorDashboardView(TemplateView):
    """
    Dashboard principal del extractor WhatsApp.

    Muestra:
        - Resumen de la última ejecución
        - Histórico de ejecuciones (últimos 30)
        - Estado de los grupos configurados
        - Métricas acumuladas
    """
    template_name = 'whatsapp_extractor/dashboard.html'

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)

        # Último log
        ultimo_log = ExtractorLog.objects.order_by('-ejecucion_fecha').first()
        context['ultimo_log'] = ultimo_log

        # Últimos 30 logs
        context['ultimos_logs'] = ExtractorLog.objects.order_by(
            '-ejecucion_fecha'
        )[:30]

        # Grupos activos e inactivos
        context['grupos_activos'] = WhatsappGroupSession.objects.filter(
            activo=True
        )
        context['grupos_inactivos'] = WhatsappGroupSession.objects.filter(
            activo=False
        )

        # Archivos recientes
        context['archivos_recientes'] = ArchivoExtraccionWhatsApp.objects.order_by(
            '-fecha_subida'
        )[:10]

        # Métricas acumuladas
        context['total_ejecuciones'] = ExtractorLog.objects.count()
        context['total_requerimientos'] = ExtractorLog.objects.aggregate(
            total=Sum('requerimientos_nuevos')
        )['total'] or 0
        context['total_duplicados'] = ExtractorLog.objects.aggregate(
            total=Sum('requerimientos_duplicados')
        )['total'] or 0
        context['total_basura'] = ExtractorLog.objects.aggregate(
            total=Sum('requerimientos_basura_filtrados')
        )['total'] or 0
        context['total_archivos'] = ArchivoExtraccionWhatsApp.objects.count()

        # Total REAL de requerimientos acumulados en BD (no solo de logs)
        from requerimientos.models import Requerimiento
        context['total_requerimientos_bd'] = Requerimiento.objects.count()

        # Tasa de éxito promedio
        logs_con_datos = ExtractorLog.objects.filter(
            mensajes_extraidos_total__gt=0
        )
        if logs_con_datos.exists():
            total_extraidos = logs_con_datos.aggregate(
                total=Sum('mensajes_extraidos_total')
            )['total'] or 0
            total_nuevos = logs_con_datos.aggregate(
                total=Sum('requerimientos_nuevos')
            )['total'] or 0
            context['tasa_exito'] = round(
                (total_nuevos / total_extraidos * 100), 1
            ) if total_extraidos > 0 else 0
        else:
            context['tasa_exito'] = 0

        return context


# ─────────────────────────────────────────────
#  DETALLE DE LOG
# ─────────────────────────────────────────────


class ExtractorLogDetailView(DetailView):
    """Muestra el detalle de una ejecución específica."""
    model = ExtractorLog
    template_name = 'whatsapp_extractor/log_detail.html'
    context_object_name = 'log'

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        log = self.object

        # Calcular duración formateada
        context['duracion'] = log.duracion_formateada

        # Obtener grupos procesados
        grupos_ids = log.grupo_procesado_ids or []
        context['grupos_procesados'] = WhatsappGroupSession.objects.filter(
            id__in=grupos_ids
        )

        # Obtener requerimientos generados por este log de extracción
        from requerimientos.models import Requerimiento
        requerimientos_qs = Requerimiento.objects.filter(
            extractor_log=log
        ).order_by('-creado_en')

        # Paginación: 50 registros por página
        pagina = self.request.GET.get('pagina', 1)
        paginator = Paginator(requerimientos_qs, 50)
        try:
            page_obj = paginator.page(pagina)
        except Exception:
            page_obj = paginator.page(1)

        context['requerimientos'] = page_obj
        context['total_requerimientos'] = paginator.count
        context['paginator'] = paginator

        return context


# ─────────────────────────────────────────────
#  GESTIÓN DE GRUPOS
# ─────────────────────────────────────────────


class GrupoSessionListView(ListView):
    """Lista todas las sesiones de grupos WhatsApp configuradas."""
    model = WhatsappGroupSession
    template_name = 'whatsapp_extractor/grupo_list.html'
    context_object_name = 'grupos'
    paginate_by = 20

    def get_queryset(self):
        qs = WhatsappGroupSession.objects.all()
        # Filtro por estado
        estado = self.request.GET.get('estado')
        if estado == 'activos':
            qs = qs.filter(activo=True)
        elif estado == 'inactivos':
            qs = qs.filter(activo=False)
        return qs

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['filtro_actual'] = self.request.GET.get('estado', 'todos')
        return context


class GrupoSessionDetailView(DetailView):
    """Muestra el detalle de un grupo WhatsApp."""
    model = WhatsappGroupSession
    template_name = 'whatsapp_extractor/grupo_detail.html'
    context_object_name = 'grupo'

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        grupo = self.object

        # Obtener logs donde se procesó este grupo
        # NOTA: SQL Server no soporta __contains en JSONField.
        # Usamos extra() con CHARINDEX para buscar el ID en el JSON.
        context['logs_recientes'] = ExtractorLog.objects.extra(
            where=["CHARINDEX(CAST(%s AS VARCHAR), CAST(grupo_procesado_ids AS VARCHAR)) > 0"],
            params=[str(grupo.id)],
        ).order_by('-ejecucion_fecha')[:10]

        # Buscar si hay un log en ejecución activo para este grupo
        context['extractor_log_activo'] = ExtractorLog.objects.extra(
            where=[
                "CHARINDEX(CAST(%s AS VARCHAR), CAST(grupo_procesado_ids AS VARCHAR)) > 0",
                "estado = %s",
            ],
            params=[str(grupo.id), EstadoExtraccionChoices.RUNNING],
        ).order_by('-ejecucion_fecha').first()

        return context


class GrupoSessionCreateView(CreateView):
    """
    Formulario para crear un nuevo grupo WhatsApp.
    """
    model = WhatsappGroupSession
    template_name = 'whatsapp_extractor/grupo_form.html'
    fields = ['nombre_grupo', 'fuente_choice', 'activo']
    success_url = reverse_lazy('whatsapp_extractor:grupo_list')

    def form_valid(self, form):
        messages.success(
            self.request,
            f"Grupo '{form.instance.nombre_grupo}' creado correctamente"
        )
        return super().form_valid(form)


class GrupoSessionToggleView(RedirectView):
    """
    Activa o desactiva un grupo WhatsApp.

    Al desactivar un grupo, se excluye de las extracciones programadas.
    """
    def get_redirect_url(self, *args, **kwargs):
        grupo = get_object_or_404(WhatsappGroupSession, pk=kwargs['pk'])
        grupo.activo = not grupo.activo
        grupo.save(update_fields=['activo', 'actualizado_en'])

        estado = 'activado' if grupo.activo else 'desactivado'
        messages.success(
            self.request,
            f"Grupo '{grupo.nombre_grupo}' {estado} correctamente"
        )
        return reverse('whatsapp_extractor:grupo_detail', kwargs={'pk': grupo.pk})


class GrupoSessionExtraerView(RedirectView):
    """
    Ejecuta extracción manual para un grupo específico.

    Crea un ExtractorLog en estado 'running', agrega una entrada
    LogEntry inicial, y lanza la extracción en un hilo separado
    (threading) para no depender de Celery worker.
    Luego redirige al detalle del grupo con el log activo para
    que el usuario vea el progreso en vivo via polling JS.
    """
    def get_redirect_url(self, *args, **kwargs):
        grupo = get_object_or_404(WhatsappGroupSession, pk=kwargs['pk'])

        if not grupo.activo:
            messages.warning(
                self.request,
                f"El grupo '{grupo.nombre_grupo}' está inactivo. "
                "Actívalo primero."
            )
            return reverse('whatsapp_extractor:grupo_detail', kwargs={'pk': grupo.pk})

        try:
            # Crear log de ejecución en estado 'running'
            extractor_log = ExtractorLog.objects.create(
                estado=EstadoExtraccionChoices.RUNNING,
                grupo_procesado_ids=[grupo.id],
            )

            # Agregar entrada inicial
            from whatsapp_extractor.models import LogEntry
            LogEntry.objects.create(
                extractor_log=extractor_log,
                nivel='INFO',
                mensaje=f"Iniciando extracción manual para grupo '{grupo.nombre_grupo}'...",
            )

            # Lanzar extracción en un hilo separado (no bloquea la respuesta)
            import threading
            from whatsapp_extractor.tasks import extraer_requerimientos_whatsapp_daily

            hilo = threading.Thread(
                target=extraer_requerimientos_whatsapp_daily,
                kwargs={
                    'extractor_log_id': extractor_log.id,
                    'grupo_id': grupo.id,
                },
                daemon=True,
            )
            hilo.start()

            messages.success(
                self.request,
                f"Extracción iniciada para '{grupo.nombre_grupo}'. "
                "Los logs en vivo aparecerán abajo."
            )
        except Exception as e:
            logger.error(f"Error iniciando extracción manual: {e}")
            messages.error(
                self.request,
                f"Error al iniciar extracción: {str(e)}"
            )

        return reverse('whatsapp_extractor:grupo_detail', kwargs={'pk': grupo.pk})


# ─────────────────────────────────────────────
#  APIs JSON
# ─────────────────────────────────────────────


class UltimosLogsApiView(View):
    """
    API que retorna los últimos logs de extracción en formato JSON.

    Query params:
        - limite: cantidad de logs a retornar (default: 10)
    """
    def get(self, request, *args, **kwargs):
        limite = int(request.GET.get('limite', 10))
        limite = min(max(limite, 1), 50)  # Entre 1 y 50

        logs = ExtractorLog.objects.order_by('-ejecucion_fecha')[:limite]

        data = []
        for log in logs:
            data.append({
                'id': log.id,
                'fecha': log.ejecucion_fecha.isoformat(),
                'estado': log.estado,
                'estado_display': log.get_estado_display(),
                'mensajes_extraidos': log.mensajes_extraidos_total,
                'requerimientos_nuevos': log.requerimientos_nuevos,
                'duplicados': log.requerimientos_duplicados,
                'basura': log.requerimientos_basura_filtrados,
                'tiempo_segundos': log.tiempo_proceso_segundos,
                'duracion': log.duracion_formateada,
                'tasa_exito': log.tasa_exito,
            })

        return JsonResponse({'logs': data, 'total': len(data)})


class LogEntriesApiView(View):
    """
    API que retorna las entradas de log detalladas para un ExtractorLog.

    Query params:
        - extractor_log_id: ID del ExtractorLog (requerido si no se usa archivo_id)
        - archivo_id: ID del ArchivoExtraccionWhatsApp (alternativa a extractor_log_id,
                      busca el log más reciente para ese archivo)
        - since_id: opcional, solo entradas con ID > since_id (para polling incremental)
    """
    def get(self, request, *args, **kwargs):
        extractor_log_id = request.GET.get('extractor_log_id')
        archivo_id = request.GET.get('archivo_id')

        if not extractor_log_id and not archivo_id:
            return JsonResponse(
                {'error': 'extractor_log_id o archivo_id es requerido'}, status=400
            )

        if extractor_log_id:
            try:
                extractor_log_id = int(extractor_log_id)
            except (ValueError, TypeError):
                return JsonResponse(
                    {'error': 'extractor_log_id debe ser un entero'}, status=400
                )
            log = get_object_or_404(ExtractorLog, pk=extractor_log_id)
        else:
            # Buscar por archivo_id: obtener el ExtractorLog más reciente
            # que tenga el mismo nombre de archivo
            try:
                archivo_id = int(archivo_id)
            except (ValueError, TypeError):
                return JsonResponse(
                    {'error': 'archivo_id debe ser un entero'}, status=400
                )
            archivo = get_object_or_404(ArchivoExtraccionWhatsApp, pk=archivo_id)
            logs = ExtractorLog.objects.filter(
                archivo_subido=archivo.nombre_archivo_original
            ).order_by('-id')
            if not logs.exists():
                return JsonResponse({
                    'entries': [],
                    'total': 0,
                    'log_estado': None,
                    'log_id': None,
                    'archivo_id': archivo_id,
                })
            log = logs.first()

        entries = log.entries.all()
        since_id = request.GET.get('since_id')
        if since_id:
            try:
                entries = entries.filter(id__gt=int(since_id))
            except (ValueError, TypeError):
                pass

        entries = entries.order_by('timestamp', 'id')

        data = []
        for entry in entries:
            data.append({
                'id': entry.id,
                'timestamp': entry.timestamp.strftime('%H:%M:%S'),
                'nivel': entry.nivel,
                'mensaje': entry.mensaje,
                'detalles': entry.detalles,
            })

        return JsonResponse({
            'entries': data,
            'total': len(data),
            'log_estado': log.estado,
            'log_id': log.id,
            'log_mensajes_total': log.mensajes_extraidos_total,
            'log_mensajes_validos': log.mensajes_validos,
            'log_duplicados': log.requerimientos_duplicados,
        })


class RequerimientosEnTiempoRealApiView(View):
    """
    API que retorna los últimos N requerimientos creados para un ExtractorLog.

    Query params:
        - extractor_log_id: ID del ExtractorLog (requerido)
        - limit: cantidad de registros a devolver (default: 10, max: 50)
    """
    def get(self, request, *args, **kwargs):
        extractor_log_id = request.GET.get('extractor_log_id')
        if not extractor_log_id:
            return JsonResponse(
                {'error': 'extractor_log_id es requerido'}, status=400
            )

        try:
            extractor_log_id = int(extractor_log_id)
        except (ValueError, TypeError):
            return JsonResponse(
                {'error': 'extractor_log_id debe ser un entero'}, status=400
            )

        log = get_object_or_404(ExtractorLog, pk=extractor_log_id)

        limit = int(request.GET.get('limit', '10'))
        limit = min(limit, 50)  # Límite máximo

        # Obtener los últimos N requerimientos para este log
        requerimientos = Requerimiento.objects.filter(
            extractor_log=log
        ).order_by('-creado_en')[:limit]

        data = []
        for req in requerimientos:
            data.append({
                'id': req.id,
                'requerimiento': req.requerimiento,
                'fuente': req.fuente,
                'agente': req.agente,
                'fecha': req.fecha.strftime('%d/%m/%Y') if req.fecha else None,
                'hora': req.hora.strftime('%H:%M') if req.hora else None,
                'condicion': req.get_condicion_display(),
                'tipo_propiedad': req.get_tipo_propiedad_display(),
                'distritos': req.distritos,
                'presupuesto_monto': float(req.presupuesto_monto) if req.presupuesto_monto else None,
                'presupuesto_moneda': req.get_presupuesto_moneda_display(),
                'presupuesto_forma_pago': req.get_presupuesto_forma_pago_display(),
                'habitaciones': req.habitaciones,
                'banos': req.banos,
                'cochera': req.get_cochera_display(),
                'ascensor': req.get_ascensor_display(),
                'amueblado': req.get_amueblado_display(),
                'area_m2': float(req.area_m2) if req.area_m2 else None,
                'piso_preferencia': req.piso_preferencia,
                'caracteristicas_extra': req.caracteristicas_extra,
                'agente_telefono': req.agente_telefono,
                'creado_en': req.creado_en.strftime('%d/%m/%Y %H:%M') if req.creado_en else None,
            })

        return JsonResponse({
            'requerimientos': data,
            'total': len(data),
            'log_id': log.id,
            'log_estado': log.estado,
        })

class EstadisticasApiView(View):
    """
    API que retorna estadísticas resumidas del extractor.

    Returns:
        - total_ejecuciones
        - total_requerimientos_creados
        - total_duplicados
        - total_basura
        - grupos_activos
        - grupos_inactivos
        - ultima_ejecucion (dict o null)
    """
    def get(self, request, *args, **kwargs):
        ultimo_log = ExtractorLog.objects.order_by('-ejecucion_fecha').first()

        stats = {
            'total_ejecuciones': ExtractorLog.objects.count(),
            'total_requerimientos_creados': ExtractorLog.objects.aggregate(
                total=Sum('requerimientos_nuevos')
            )['total'] or 0,
            'total_duplicados': ExtractorLog.objects.aggregate(
                total=Sum('requerimientos_duplicados')
            )['total'] or 0,
            'total_basura': ExtractorLog.objects.aggregate(
                total=Sum('requerimientos_basura_filtrados')
            )['total'] or 0,
            'grupos_activos': WhatsappGroupSession.objects.filter(
                activo=True
            ).count(),
            'grupos_inactivos': WhatsappGroupSession.objects.filter(
                activo=False
            ).count(),
            'ultima_ejecucion': None,
        }

        if ultimo_log:
            stats['ultima_ejecucion'] = {
                'fecha': ultimo_log.ejecucion_fecha.isoformat(),
                'estado': ultimo_log.estado,
                'requerimientos_nuevos': ultimo_log.requerimientos_nuevos,
            }

        return JsonResponse(stats)


# ─────────────────────────────────────────────
#  SUBIR ARCHIVO DE EXTRACCIÓN
# ─────────────────────────────────────────────


class UploadExtractFileView(FormView):
    """
    Vista para subir un archivo .txt de exportación WhatsApp.

    El archivo se guarda en ArchivoExtraccionWhatsApp y luego
    se lanza la tarea Celery `procesar_archivo_extraccion` para
    procesarlo de forma asíncrona.
    """
    template_name = 'whatsapp_extractor/upload_extract_file.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, {
            'active_section': 'upload',
        })

    def post(self, request, *args, **kwargs):
        archivo_txt = request.FILES.get('archivo_txt')
        if not archivo_txt:
            messages.error(request, 'Debes seleccionar un archivo .txt')
            return render(request, self.template_name)

        if not archivo_txt.name.endswith('.txt'):
            messages.error(request, 'Solo se permiten archivos .txt')
            return render(request, self.template_name)

        try:
            # Guardar archivo físicamente en el sistema
            import os
            from django.conf import settings
            # MEDIA_ROOT puede ser None (cuando se usa Azure Blob Storage),
            # así que usamos BASE_DIR como fallback
            media_root = settings.MEDIA_ROOT or (settings.BASE_DIR / 'media')
            upload_dir = os.path.join(str(media_root), 'whatsapp_extracciones')
            os.makedirs(upload_dir, exist_ok=True)

            # Nombre único para evitar colisiones
            import uuid
            unique_name = f"{uuid.uuid4().hex}_{archivo_txt.name}"
            ruta_completa = os.path.join(upload_dir, unique_name)

            with open(ruta_completa, 'wb') as f:
                for chunk in archivo_txt.chunks():
                    f.write(chunk)

            # Calcular tamaño en KB
            tamanio_bytes = archivo_txt.size
            tamanio_kb = tamanio_bytes // 1024 if tamanio_bytes > 0 else 0

            # Guardar registro en BD
            # usuario_subida_id almacena el UUID como string (CharField) para
            # compatibilidad con la tabla SQL Server que tiene columna INT.
            usuario_actual = getattr(request, 'current_user', None)
            usuario_uuid = str(usuario_actual.id) if usuario_actual and usuario_actual.is_active else None
            archivo = ArchivoExtraccionWhatsApp(
                nombre_archivo_original=archivo_txt.name,
                ruta_almacenamiento=ruta_completa,
                tamanio_kb=tamanio_kb,
                usuario_subida_id=usuario_uuid,
            )
            archivo.save()

            # Lanzar tarea Celery de procesamiento
            from whatsapp_extractor.tasks import procesar_archivo_extraccion
            procesar_archivo_extraccion.delay(archivo.id)

            messages.success(
                request,
                f'Archivo "{archivo_txt.name}" subido correctamente. '
                'El procesamiento ha comenzado en segundo plano.'
            )
            return HttpResponseRedirect(
                reverse('whatsapp_extractor:file_management')
            )

        except Exception as e:
            logger.error(f'Error subiendo archivo: {e}', exc_info=True)
            messages.error(
                request,
                f'Error al subir el archivo: {str(e)}'
            )
            return render(request, self.template_name)


# ─────────────────────────────────────────────
#  GESTIÓN DE ARCHIVOS
# ─────────────────────────────────────────────


class FileManagementView(ListView):
    """
    Vista para listar y gestionar los archivos de extracción subidos.

    Muestra todos los archivos con su estado de procesamiento,
    permitiendo al usuario ver el detalle de cada uno.
    """
    model = ArchivoExtraccionWhatsApp
    template_name = 'whatsapp_extractor/file_management.html'
    context_object_name = 'archivos'
    paginate_by = 20

    def get_queryset(self):
        qs = ArchivoExtraccionWhatsApp.objects.all()

        # Filtro por estado de procesamiento
        estado = self.request.GET.get('estado')
        if estado == 'procesados':
            qs = qs.filter(procesado=True)
        elif estado == 'pendientes':
            qs = qs.filter(procesado=False)

        # Búsqueda por nombre
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(nombre_archivo_original__icontains=q)

        return qs.order_by('-fecha_subida')

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['filtro_actual'] = self.request.GET.get('estado', 'todos')
        context['busqueda'] = self.request.GET.get('q', '')
        context['total_archivos'] = ArchivoExtraccionWhatsApp.objects.count()
        context['archivos_pendientes'] = ArchivoExtraccionWhatsApp.objects.filter(
            procesado=False
        ).count()
        context['archivos_procesados'] = ArchivoExtraccionWhatsApp.objects.filter(
            procesado=True
        ).count()
        return context


class ArchivoDetailView(DetailView):
    """
    Muestra el detalle de un archivo de extracción específico.
    """
    model = ArchivoExtraccionWhatsApp
    template_name = 'whatsapp_extractor/archivo_detail.html'
    context_object_name = 'archivo'

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        archivo = self.object

        # Buscar logs relacionados
        context['logs_relacionados'] = ExtractorLog.objects.filter(
            archivo_subido=archivo.nombre_archivo_original
        ).order_by('-ejecucion_fecha')

        return context


class ReprocesarArchivoView(RedirectView):
    """
    Vuelve a procesar un archivo de extracción (vía Celery).
    """
    def get_redirect_url(self, *args, **kwargs):
        archivo = get_object_or_404(
            ArchivoExtraccionWhatsApp, pk=kwargs['pk']
        )

        try:
            from whatsapp_extractor.tasks import procesar_archivo_extraccion
            procesar_archivo_extraccion.delay(archivo.id)

            messages.success(
                self.request,
                f'Reprocesamiento iniciado para "{archivo.nombre_archivo_original}"'
            )
        except Exception as e:
            logger.error(f'Error reprocesando archivo: {e}', exc_info=True)
            messages.error(
                self.request,
                f'Error al reprocesar: {str(e)}'
            )

        return reverse('whatsapp_extractor:file_management')


class ProcesarArchivoManualView(View):
    """
    Procesa un archivo de extracción de forma síncrona (sin Celery).

    Útil cuando el worker de Celery no está corriendo y se necesita
    procesar el archivo de inmediato.
    """
    def post(self, request, *args, **kwargs):
        archivo = get_object_or_404(
            ArchivoExtraccionWhatsApp, pk=kwargs['pk']
        )

        try:
            from whatsapp_extractor.tasks import procesar_archivo_extraccion
            resultado = procesar_archivo_extraccion(archivo.id)

            if resultado.get('success'):
                messages.success(
                    request,
                    f'Archivo "{archivo.nombre_archivo_original}" procesado correctamente: '
                    f'{resultado.get("mensajes_validos", 0)} válidos, '
                    f'{resultado.get("mensajes_duplicados", 0)} duplicados'
                )
            else:
                messages.error(
                    request,
                    f'Error procesando archivo: {resultado.get("error", "Error desconocido")}'
                )
        except Exception as e:
            logger.error(f'Error procesando archivo manualmente: {e}', exc_info=True)
            messages.error(
                request,
                f'Error al procesar archivo: {str(e)}'
            )

        return HttpResponseRedirect(
            reverse('whatsapp_extractor:archivo_detail', kwargs={'pk': archivo.pk})
        )


class ProcesarArchivoConProgresoView(View):
    """
    Procesa un archivo de extracción y muestra el progreso en vivo.

    Estrategia:
    - POST: Inicia el procesamiento en un hilo separado (para no bloquear),
            luego redirige a la página de progreso.
    - GET:  Muestra la página de progreso que hace polling a LogEntriesApiView
            para mostrar logs y barra de progreso en tiempo real.

    La página de progreso detecta automáticamente cuando el log cambia a
    'Completado' o 'Error' y redirige al detalle del archivo.
    """
    template_name = 'whatsapp_extractor/progreso_procesamiento.html'

    def get(self, request, *args, **kwargs):
        """Muestra la página de progreso para un extractor_log ya iniciado."""
        archivo = get_object_or_404(
            ArchivoExtraccionWhatsApp, pk=kwargs['pk']
        )
        extractor_log_id = request.GET.get('extractor_log_id')

        # Obtener el log activo si existe
        log_activo = None
        if extractor_log_id:
            try:
                log_activo = ExtractorLog.objects.get(pk=extractor_log_id)
            except ExtractorLog.DoesNotExist:
                pass
        else:
            # Buscar el log más reciente para este archivo
            log_activo = ExtractorLog.objects.filter(
                archivo_subido=archivo.nombre_archivo_original
            ).order_by('-id').first()

        # Total de requerimientos acumulados en BD
        from requerimientos.models import Requerimiento
        total_requerimientos = Requerimiento.objects.count()

        context = {
            'archivo': archivo,
            'extractor_log_id': extractor_log_id,
            'log_activo': log_activo,
            'total_requerimientos': total_requerimientos,
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        """Inicia el procesamiento en un hilo separado y redirige a progreso."""
        archivo = get_object_or_404(
            ArchivoExtraccionWhatsApp, pk=kwargs['pk']
        )

        if archivo.procesado:
            messages.info(request, 'Este archivo ya fue procesado.')
            return HttpResponseRedirect(
                reverse('whatsapp_extractor:archivo_detail', kwargs={'pk': archivo.pk})
            )

        # Crear el ExtractorLog ANTES de iniciar el hilo para que la página
        # de progreso pueda encontrarlo inmediatamente al cargar el GET
        from whatsapp_extractor.models import ExtractorLog, LogEntry
        extractor_log = ExtractorLog.objects.create(
            archivo_subido=archivo.nombre_archivo_original,
            estado='running',
            mensajes_extraidos_total=0,
            mensajes_validos=0,
            requerimientos_duplicados=0,
        )
        LogEntry.objects.create(
            extractor_log=extractor_log,
            nivel='INFO',
            mensaje='Iniciando procesamiento del archivo...',
            detalles={},
        )

        # Iniciar procesamiento en un hilo separado, pasando el extractor_log_id
        import threading
        from whatsapp_extractor.tasks import procesar_archivo_extraccion

        def _ejecutar_procesamiento():
            """Wrapper que ejecuta el procesamiento y captura errores."""
            try:
                procesar_archivo_extraccion(archivo.id, extractor_log_id=extractor_log.id)
            except Exception as e:
                logger.error(f'Error en hilo de procesamiento: {e}', exc_info=True)

        hilo = threading.Thread(target=_ejecutar_procesamiento, daemon=True)
        hilo.start()

        # Redirigir a la página de progreso con el extractor_log_id
        return HttpResponseRedirect(
            reverse('whatsapp_extractor:archivo_progreso', kwargs={'pk': archivo.pk}) +
            f'?extractor_log_id={extractor_log.id}'
        )


class PausarProcesamientoView(View):
    """
    Pausa el procesamiento de un archivo cambiando el estado del ExtractorLog a 'paused'.
    El hilo de procesamiento debe verificar periódicamente si debe pausarse.
    """
    def post(self, request, *args, **kwargs):
        archivo = get_object_or_404(
            ArchivoExtraccionWhatsApp, pk=kwargs['pk']
        )

        # Buscar el log en ejecución más reciente
        log_activo = ExtractorLog.objects.filter(
            archivo_subido=archivo.nombre_archivo_original,
            estado=EstadoExtraccionChoices.RUNNING
        ).order_by('-id').first()

        if not log_activo:
            messages.warning(request, 'No hay un procesamiento activo para pausar.')
            return HttpResponseRedirect(
                reverse('whatsapp_extractor:archivo_progreso', kwargs={'pk': archivo.pk})
            )

        log_activo.estado = EstadoExtraccionChoices.PAUSED
        log_activo.save(update_fields=['estado'])

        from whatsapp_extractor.models import LogEntry
        LogEntry.objects.create(
            extractor_log=log_activo,
            nivel='WARNING',
            mensaje='⏸️ Procesamiento pausado por el usuario',
            detalles={'accion': 'pausar'},
        )

        messages.success(request, 'Procesamiento pausado correctamente.')
        return HttpResponseRedirect(
            reverse('whatsapp_extractor:archivo_progreso', kwargs={'pk': archivo.pk})
        )


class ReanudarProcesamientoView(View):
    """
    Reanuda un procesamiento pausado.
    """
    def post(self, request, *args, **kwargs):
        archivo = get_object_or_404(
            ArchivoExtraccionWhatsApp, pk=kwargs['pk']
        )

        log_pausado = ExtractorLog.objects.filter(
            archivo_subido=archivo.nombre_archivo_original,
            estado=EstadoExtraccionChoices.PAUSED
        ).order_by('-id').first()

        if not log_pausado:
            messages.warning(request, 'No hay un procesamiento pausado para reanudar.')
            return HttpResponseRedirect(
                reverse('whatsapp_extractor:archivo_progreso', kwargs={'pk': archivo.pk})
            )

        log_pausado.estado = EstadoExtraccionChoices.RUNNING
        log_pausado.save(update_fields=['estado'])

        from whatsapp_extractor.models import LogEntry
        LogEntry.objects.create(
            extractor_log=log_pausado,
            nivel='INFO',
            mensaje='▶️ Procesamiento reanudado por el usuario',
            detalles={'accion': 'reanudar'},
        )

        messages.success(request, 'Procesamiento reanudado.')
        return HttpResponseRedirect(
            reverse('whatsapp_extractor:archivo_progreso', kwargs={'pk': archivo.pk})
        )


class DetenerProcesamientoView(View):
    """
    Detiene (cancela) el procesamiento de un archivo.
    Marca el log como 'error' con mensaje de cancelación.
    """
    def post(self, request, *args, **kwargs):
        archivo = get_object_or_404(
            ArchivoExtraccionWhatsApp, pk=kwargs['pk']
        )

        log_activo = ExtractorLog.objects.filter(
            archivo_subido=archivo.nombre_archivo_original,
            estado__in=[EstadoExtraccionChoices.RUNNING, EstadoExtraccionChoices.PAUSED]
        ).order_by('-id').first()

        if not log_activo:
            messages.warning(request, 'No hay un procesamiento activo para detener.')
            return HttpResponseRedirect(
                reverse('whatsapp_extractor:archivo_progreso', kwargs={'pk': archivo.pk})
            )

        log_activo.estado = EstadoExtraccionChoices.ERROR
        log_activo.mensaje_error = 'Procesamiento cancelado por el usuario'
        log_activo.save(update_fields=['estado', 'mensaje_error'])

        from whatsapp_extractor.models import LogEntry
        LogEntry.objects.create(
            extractor_log=log_activo,
            nivel='ERROR',
            mensaje='🛑 Procesamiento detenido por el usuario',
            detalles={'accion': 'detener'},
        )

        messages.success(request, 'Procesamiento detenido.')
        return HttpResponseRedirect(
            reverse('whatsapp_extractor:archivo_detail', kwargs={'pk': archivo.pk})
        )
