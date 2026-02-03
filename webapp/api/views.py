"""
Vistas para la API REST del sistema de monitoreo web.

Este módulo define los endpoints de la API para interactuar con
el sistema de monitoreo web de bienes raíces en Arequipa.
"""

from django.utils import timezone
from django.db.models import Count, Avg, Sum, Q
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from datetime import timedelta
import logging

from .serializers import (
    FuenteWebSerializer, CapturaCrudaSerializer, EventoDeteccionSerializer,
    EstadisticasSerializer, TareaCelerySerializer, DescubrimientoRequestSerializer
)
from semillas.models import FuenteWeb
from captura.models import CapturaCruda, EventoDeteccion
from colas.tareas_descubrimiento import ejecutar_descubrimiento_automatico
from colas.tasks import revisar_fuente, ejecutar_prueba_sistema, generar_reporte_estadisticas

logger = logging.getLogger(__name__)


class FuenteWebViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar fuentes web.
    
    Permite listar, crear, actualizar y eliminar fuentes web,
    así como ejecutar acciones específicas sobre ellas.
    """
    queryset = FuenteWeb.objects.all().order_by('-fecha_creacion')
    serializer_class = FuenteWebSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nombre', 'url', 'descripcion', 'categoria']
    ordering_fields = ['nombre', 'fecha_creacion', 'frecuencia_revision_minutos', 'contador_exitos']
    
    def get_queryset(self):
        """Filtra el queryset basado en parámetros de consulta."""
        queryset = super().get_queryset()
        
        # Filtrar por estado
        estado = self.request.query_params.get('estado')
        if estado:
            queryset = queryset.filter(estado=estado)
        
        # Filtrar por categoría
        categoria = self.request.query_params.get('categoria')
        if categoria:
            queryset = queryset.filter(categoria=categoria)
        
        # Filtrar por actividad
        activa = self.request.query_params.get('activa')
        if activa is not None:
            queryset = queryset.filter(activa=activa.lower() == 'true')
        
        # Filtrar fuentes que necesitan revisión
        necesita_revision = self.request.query_params.get('necesita_revision')
        if necesita_revision is not None:
            if necesita_revision.lower() == 'true':
                # Fuentes activas cuya última captura fue hace más de su frecuencia
                ahora = timezone.now()
                queryset = [
                    fuente for fuente in queryset
                    if fuente.necesita_revision
                ]
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def revisar(self, request, pk=None):
        """Ejecuta una revisión inmediata de la fuente."""
        fuente = self.get_object()
        
        # Ejecutar tarea Celery para revisar la fuente
        tarea = revisar_fuente.delay(fuente.id, forzar_captura=True)
        
        return Response({
            'estado': 'en_proceso',
            'mensaje': f'Revisión de {fuente.nombre} iniciada',
            'task_id': tarea.id,
            'fuente_id': fuente.id,
            'fuente_nombre': fuente.nombre,
        }, status=status.HTTP_202_ACCEPTED)
    
    @action(detail=True, methods=['post'])
    def activar(self, request, pk=None):
        """Activa una fuente inactiva."""
        fuente = self.get_object()
        
        if fuente.activa:
            return Response({
                'estado': 'advertencia',
                'mensaje': f'La fuente {fuente.nombre} ya está activa',
            }, status=status.HTTP_200_OK)
        
        fuente.activa = True
        fuente.estado = 'activa'
        fuente.save()
        
        return Response({
            'estado': 'exito',
            'mensaje': f'Fuente {fuente.nombre} activada exitosamente',
            'fuente_id': fuente.id,
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def desactivar(self, request, pk=None):
        """Desactiva una fuente activa."""
        fuente = self.get_object()
        
        if not fuente.activa:
            return Response({
                'estado': 'advertencia',
                'mensaje': f'La fuente {fuente.nombre} ya está inactiva',
            }, status=status.HTTP_200_OK)
        
        fuente.activa = False
        fuente.save()
        
        return Response({
            'estado': 'exito',
            'mensaje': f'Fuente {fuente.nombre} desactivada exitosamente',
            'fuente_id': fuente.id,
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def estadisticas(self, request):
        """Obtiene estadísticas de todas las fuentes."""
        total = self.get_queryset().count()
        activas = self.get_queryset().filter(activa=True).count()
        inactivas = total - activas
        error = self.get_queryset().filter(estado='error').count()
        
        # Estadísticas por categoría
        por_categoria = self.get_queryset().values('categoria').annotate(
            count=Count('id')
        )
        
        categorias_dict = {item['categoria']: item['count'] for item in por_categoria}
        
        return Response({
            'total': total,
            'activas': activas,
            'inactivas': inactivas,
            'error': error,
            'por_categoria': categorias_dict,
            'tasa_activas': (activas / max(total, 1)) * 100,
        })
    
    @action(detail=False, methods=['get'])
    def necesidades_revision(self, request):
        """Lista fuentes que necesitan revisión."""
        fuentes = self.get_queryset().filter(activa=True, estado='activa')
        
        fuentes_necesitan = []
        for fuente in fuentes:
            if fuente.necesita_revision:
                fuentes_necesitan.append(FuenteWebSerializer(fuente).data)
        
        return Response({
            'total': len(fuentes_necesitan),
            'fuentes': fuentes_necesitan,
        })


class CapturaCrudaViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para consultar capturas crudas.
    
    Solo permite operaciones de lectura (listar, detalle).
    """
    queryset = CapturaCruda.objects.all().order_by('-fecha_captura')
    serializer_class = CapturaCrudaSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['fuente__nombre', 'estado', 'content_type']
    ordering_fields = ['fecha_captura', 'tamaño_bytes', 'tiempo_respuesta_ms']
    
    def get_queryset(self):
        """Filtra el queryset basado en parámetros de consulta."""
        queryset = super().get_queryset()
        
        # Filtrar por fuente
        fuente_id = self.request.query_params.get('fuente_id')
        if fuente_id:
            queryset = queryset.filter(fuente_id=fuente_id)
        
        # Filtrar por estado
        estado = self.request.query_params.get('estado')
        if estado:
            queryset = queryset.filter(estado=estado)
        
        # Filtrar por fecha
        fecha_desde = self.request.query_params.get('fecha_desde')
        fecha_hasta = self.request.query_params.get('fecha_hasta')
        
        if fecha_desde:
            queryset = queryset.filter(fecha_captura__gte=fecha_desde)
        if fecha_hasta:
            queryset = queryset.filter(fecha_captura__lte=fecha_hasta)
        
        # Limitar a las últimas 1000 capturas por defecto
        limite = int(self.request.query_params.get('limite', 1000))
        queryset = queryset[:limite]
        
        return queryset
    
    @action(detail=True, methods=['get'])
    def contenido(self, request, pk=None):
        """Obtiene el contenido HTML completo de una captura."""
        captura = self.get_object()
        
        # Para capturas muy grandes, podríamos paginar el contenido
        # pero por ahora devolvemos todo
        return Response({
            'id': captura.id,
            'fuente': captura.fuente.nombre,
            'fecha_captura': captura.fecha_captura,
            'contenido_html': captura.contenido_html,
            'tamaño_bytes': captura.tamaño_bytes,
            'hash_sha256': captura.hash_sha256,
        })
    
    @action(detail=False, methods=['get'])
    def estadisticas(self, request):
        """Obtiene estadísticas de capturas."""
        # Periodo por defecto: últimos 7 días
        fecha_limite = timezone.now() - timedelta(days=7)
        
        total = CapturaCruda.objects.filter(
            fecha_captura__gte=fecha_limite
        ).count()
        
        exitosas = CapturaCruda.objects.filter(
            fecha_captura__gte=fecha_limite,
            estado='exito'
        ).count()
        
        errores = CapturaCruda.objects.filter(
            fecha_captura__gte=fecha_limite,
            estado='error'
        ).count()
        
        # Tamaño promedio
        tamaño_promedio = CapturaCruda.objects.filter(
            fecha_captura__gte=fecha_limite,
            estado='exito'
        ).aggregate(Avg('tamaño_bytes'))['tamaño_bytes__avg'] or 0
        
        # Tiempo de respuesta promedio
        tiempo_promedio = CapturaCruda.objects.filter(
            fecha_captura__gte=fecha_limite,
            estado='exito',
            tiempo_respuesta_ms__isnull=False
        ).aggregate(Avg('tiempo_respuesta_ms'))['tiempo_respuesta_ms__avg'] or 0
        
        return Response({
            'periodo_dias': 7,
            'fecha_desde': fecha_limite,
            'total': total,
            'exitosas': exitosas,
            'errores': errores,
            'tasa_exito': (exitosas / max(total, 1)) * 100,
            'tamaño_promedio_kb': tamaño_promedio / 1024,
            'tiempo_promedio_ms': tiempo_promedio,
        })


class EventoDeteccionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para consultar eventos de detección.
    
    Solo permite operaciones de lectura (listar, detalle).
    """
    queryset = EventoDeteccion.objects.all().order_by('-fecha_deteccion')
    serializer_class = EventoDeteccionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['fuente__nombre', 'tipo_cambio', 'resumen_cambio']
    ordering_fields = ['fecha_deteccion', 'similitud_porcentaje', 'severidad']
    
    def get_queryset(self):
        """Filtra el queryset basado en parámetros de consulta."""
        queryset = super().get_queryset()
        
        # Filtrar por fuente
        fuente_id = self.request.query_params.get('fuente_id')
        if fuente_id:
            queryset = queryset.filter(fuente_id=fuente_id)
        
        # Filtrar por tipo de cambio
        tipo_cambio = self.request.query_params.get('tipo_cambio')
        if tipo_cambio:
            queryset = queryset.filter(tipo_cambio=tipo_cambio)
        
        # Filtrar por severidad
        severidad = self.request.query_params.get('severidad')
        if severidad:
            queryset = queryset.filter(severidad=severidad)
        
        # Filtrar por fecha
        fecha_desde = self.request.query_params.get('fecha_desde')
        fecha_hasta = self.request.query_params.get('fecha_hasta')
        
        if fecha_desde:
            queryset = queryset.filter(fecha_deteccion__gte=fecha_desde)
        if fecha_hasta:
            queryset = queryset.filter(fecha_deteccion__lte=fecha_hasta)
        
        # Filtrar solo cambios significativos
        solo_significativos = self.request.query_params.get('solo_significativos')
        if solo_significativos and solo_significativos.lower() == 'true':
            queryset = queryset.filter(severidad__in=['alto', 'critico'])
        
        # Limitar a los últimos 500 eventos por defecto
        limite = int(self.request.query_params.get('limite', 500))
        queryset = queryset[:limite]
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def resumen(self, request):
        """Obtiene un resumen de eventos recientes."""
        # Últimos 7 días por defecto
        dias = int(request.query_params.get('dias', 7))
        fecha_limite = timezone.now() - timedelta(days=dias)
        
        eventos = EventoDeteccion.objects.filter(
            fecha_deteccion__gte=fecha_limite
        )
        
        total = eventos.count()
        significativos = eventos.filter(severidad__in=['alto', 'critico']).count()
        
        # Por tipo de cambio
        por_tipo = eventos.values('tipo_cambio').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Por severidad
        por_severidad = eventos.values('severidad').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Por fuente (top 10)
        por_fuente = eventos.values('fuente__nombre').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        return Response({
            'periodo_dias': dias,
            'fecha_desde': fecha_limite,
            'total': total,
            'significativos': significativos,
            'tasa_significativos': (significativos / max(total, 1)) * 100,
            'por_tipo': list(por_tipo),
            'por_severidad': list(por_severidad),
            'por_fuente': list(por_fuente),
        })


class SistemaAPIView(APIView):
    """
    Vista para operaciones del sistema.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Obtiene información del sistema."""
        # Estadísticas básicas
        total_fuentes = FuenteWeb.objects.count()
        fuentes_activas = FuenteWeb.objects.filter(activa=True).count()
        
        total_capturas = CapturaCruda.objects.count()
        capturas_24h = CapturaCruda.objects.filter(
            fecha_captura__gte=timezone.now() - timedelta(hours=24)
        ).count()
        
        total_eventos = EventoDeteccion.objects.count()
        eventos_24h = EventoDeteccion.objects.filter(
            fecha_deteccion__gte=timezone.now() - timedelta(hours=24)
        ).count()
        
        return Response({
            'estado': 'operativo',
            'timestamp': timezone.now().isoformat(),
            'estadisticas': {
                'fuentes': {
                    'total': total_fuentes,
                    'activas': fuentes_activas,
                    'inactivas': total_fuentes - fuentes_activas,
                },
                'capturas': {
                    'total': total_capturas,
                    'ultimas_24h': capturas_24h,
                },
                'eventos': {
                    'total': total_eventos,
                    'ultimas_24h': eventos_24h,
                },
            },
            'version': '1.0.0',
            'entorno': 'produccion' if not settings.DEBUG else 'desarrollo',
        })
    
    def post(self, request):
        """Ejecuta una prueba del sistema."""
        tarea = ejecutar_prueba_sistema.delay()
        
        return Response({
            'estado': 'en_proceso',
            'mensaje': 'Prueba del sistema iniciada',
            'task_id': tarea.id,
        }, status=status.HTTP_202_ACCEPTED)


class DescubrimientoAPIView(APIView):
    """
    Vista para operaciones de descubrimiento de URLs.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Ejecuta un proceso de descubrimiento de URLs."""
        serializer = DescubrimientoRequestSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        data = serializer.validated_data
        
        # Determinar qué tipo de descubrimiento ejecutar
        from colas.tareas_descubrimiento import (
            descubrir_fuentes_por_categoria,
            explorar_sitio_especifico,
            analizar_sitemap,
            ejecutar_descubrimiento_automatico
        )
        
        tarea = None
        
        if data.get('categoria'):
            tarea = descubrir_fuentes_por_categoria.delay(
                categoria=data['categoria'],
                limite=data['limite']
            )
        elif data.get('consulta'):
            # Para consultas personalizadas, usar descubrimiento automático
            # con parámetros específicos (esto sería una mejora futura)
            tarea = ejecutar_descubrimiento_automatico.delay()
        elif data.get('url_sitio'):
            tarea = explorar_sitio_especifico.delay(
                url_sitio=data['url_sitio'],
                profundidad=1
            )
        elif data.get('url_sitemap'):
            tarea = analizar_sitemap.delay(
                url_sitemap=data['url_sitemap']
            )
        else:
            # Descubrimiento automático general
            tarea = ejecutar_descubrimiento_automatico.delay()
        
        return Response({
            'estado': 'en_proceso',
            'mensaje': 'Proceso de descubrimiento iniciado',
            'task_id': tarea.id if tarea else None,
            'parametros': data,
        }, status=status.HTTP_202_ACCEPTED)
    
    def get(self, request):
        """Obtiene estadísticas de descubrimiento."""
        from colas.tareas_descubrimiento import evaluar_fuentes_descubiertas
        
        tarea = evaluar_fuentes_descubiertas.delay()
        
        return Response({
            'estado': 'en_proceso',
            'mensaje': 'Evaluación de fuentes descubiertas iniciada',
            'task_id': tarea.id,
        }, status=status.HTTP_202_ACCEPTED)


class EstadisticasAPIView(APIView):
    """
    Vista para obtener estadísticas del sistema.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Obtiene estadísticas completas del sistema."""
        # Ejecutar tarea para generar reporte
        dias = int(request.query_params.get('dias', 7))
        tarea = generar_reporte_estadisticas.delay(dias)
        
        return Response({
            'estado': 'en_proceso',
            'mensaje': f'Generando reporte de estadísticas para {dias} días',
            'task_id': tarea.id,
            'dias': dias,
        }, status=status.HTTP_202_ACCEPTED)


class TareasAPIView(APIView):
    """
    Vista para consultar información de tareas Celery.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, task_id=None):
        """Obtiene información de una tarea específica o lista tareas recientes."""
        from celery.result import AsyncResult
        from colas.celery import app
        
        if task_id:
            # Obtener información de una tarea específica
            resultado = AsyncResult(task_id, app=app)
            
            info = {
                'id': task_id,
                'estado': resultado.state,
                'listo': resultado.ready(),
                'exitoso': resultado.successful(),
                'fallido': resultado.failed(),
            }
            
            if resultado.ready():
                info['resultado'] = resultado.result
                info['fecha_finalizacion'] = getattr(resultado, 'date_done', None)
                
                # Calcular tiempo de ejecución si está disponible
                if hasattr(resultado, 'date_done') and hasattr(resultado, 'date_started'):
                    if resultado.date_done and resultado.date_started:
                        tiempo_ejecucion = (resultado.date_done - resultado.date_started).total_seconds()
                        info['tiempo_ejecucion'] = tiempo_ejecucion
            
            return Response(info)
        else:
            # Listar tareas recientes (esto es una simplificación)
            # En producción se usaría un sistema de monitoreo como Flower
            return Response({
                'estado': 'info',
                'mensaje': 'Para listar tareas, use un sistema de monitoreo como Flower',
                'endpoint_monitoreo': '/flower/' if settings.DEBUG else 'No disponible en producción',
            })