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
    EstadisticasSerializer, TareaCelerySerializer, DescubrimientoRequestSerializer,
    PropiedadRawSerializer, PropifaiPropertySerializer
)
from semillas.models import FuenteWeb
from captura.models import CapturaCruda, EventoDeteccion
from ingestas.models import PropiedadRaw
from propifai.models import PropifaiProperty
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


class PropiedadRawViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar propiedades raw (PropiedadRaw).
    Permite listar, crear, actualizar y eliminar propiedades.
    """
    queryset = PropiedadRaw.objects.all().order_by('-fecha_ingesta')
    serializer_class = PropiedadRawSerializer
    permission_classes = [AllowAny]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['tipo_propiedad', 'condicion', 'departamento', 'provincia', 'distrito']
    ordering_fields = ['precio_usd', 'area_construida', 'area_terreno', 'fecha_ingesta']
    
    def get_queryset(self):
        """Filtra el queryset basado en parámetros de consulta."""
        queryset = super().get_queryset()
        
        # Filtrar por tipo de propiedad
        tipo_propiedad = self.request.query_params.get('tipo_propiedad')
        if tipo_propiedad:
            queryset = queryset.filter(tipo_propiedad=tipo_propiedad)
        
        # Filtrar por condición (venta/alquiler)
        condicion = self.request.query_params.get('condicion')
        if condicion:
            queryset = queryset.filter(condicion=condicion)
        
        # Filtrar por departamento
        departamento = self.request.query_params.get('departamento')
        if departamento:
            queryset = queryset.filter(departamento__icontains=departamento)
        
        # Filtrar por precio mínimo y máximo
        precio_min = self.request.query_params.get('precio_min')
        precio_max = self.request.query_params.get('precio_max')
        if precio_min:
            queryset = queryset.filter(precio_usd__gte=precio_min)
        if precio_max:
            queryset = queryset.filter(precio_usd__lte=precio_max)
        
        return queryset


class PropifaiPropertyViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar propiedades de Propifai (PropifaiProperty).
    Permite listar, crear, actualizar y eliminar propiedades.
    """
    queryset = PropifaiProperty.objects.using('propifai').all().order_by('-created_at')
    serializer_class = PropifaiPropertySerializer
    permission_classes = [AllowAny]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description', 'department', 'province', 'district']
    ordering_fields = ['price', 'built_area', 'land_area', 'created_at']
    
    def get_queryset(self):
        """Filtra el queryset basado en parámetros de consulta."""
        queryset = super().get_queryset()
        
        # Filtrar por tipo de propiedad (basado en título)
        tipo_propiedad = self.request.query_params.get('tipo_propiedad')
        if tipo_propiedad:
            queryset = queryset.filter(title__icontains=tipo_propiedad)
        
        # Filtrar por departamento
        departamento = self.request.query_params.get('departamento')
        if departamento:
            queryset = queryset.filter(department__icontains=departamento)
        
        # Filtrar por precio mínimo y máximo
        precio_min = self.request.query_params.get('precio_min')
        precio_max = self.request.query_params.get('precio_max')
        if precio_min:
            queryset = queryset.filter(price__gte=precio_min)
        if precio_max:
            queryset = queryset.filter(price__lte=precio_max)
        
        return queryset


class PropiedadesExternasSimuladasAPIView(APIView):
    """
    Endpoint que simula la API externa de propiedades.
    Devuelve datos de prueba en el formato esperado por services_api.py.
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Devuelve propiedades simuladas con validación de token Bearer."""
        from django.conf import settings
        
        # Obtener el token del header Authorization
        auth_header = request.headers.get('Authorization', '')
        expected_token = getattr(settings, 'API_EXTERNA_KEY', 'test-key-simulada')
        
        # Verificar si el token es válido
        if not auth_header.startswith('Bearer '):
            # Si no hay token Bearer, devolver 401
            return Response(
                {
                    "detail": "Given token not valid for any token type",
                    "code": "token_not_valid",
                    "messages": [
                        {
                            "token_class": "AccessToken",
                            "token_type": "access",
                            "message": "Token is invalid or expired"
                        }
                    ]
                },
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        token = auth_header.split('Bearer ')[1].strip()
        
        # Validar el token (en este caso simulado, comparamos con API_EXTERNA_KEY)
        if token != expected_token:
            return Response(
                {
                    "detail": "Given token not valid for any token type",
                    "code": "token_not_valid",
                    "messages": [
                        {
                            "token_class": "AccessToken",
                            "token_type": "access",
                            "message": "Token is invalid or expired"
                        }
                    ]
                },
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Si el token es válido, devolver las propiedades simuladas
        propiedades_simuladas = [
            {
                "id": 1001,
                "title": "Casa en Miraflores con jardín y piscina",
                "property_id": "EXT-1001",
                "property_type": "Casa",
                "description": "Hermosa casa en zona residencial con jardín amplio y piscina.",
                "price_usd": 250000,
                "department": "Lima",
                "province": "Lima",
                "district": "Miraflores",
                "address": "Av. Larco 123",
                "built_area": 180,
                "land_area": 300,
                "bedrooms": 4,
                "bathrooms": 3,
                "parking": 2,
                "latitude": -12.120,
                "longitude": -77.030,
                "url": "https://www.ejemplo.com/propiedad/1001",
                "main_image": "https://images.unsplash.com/photo-1518780664697-55e3ad937233",
                "publication_date": "2026-02-20",
                "docs": [
                    {"id": 1, "name": "Plano arquitectónico", "url": "https://ejemplo.com/docs/1.pdf"},
                    {"id": 2, "name": "Certificado de propiedad", "url": "https://ejemplo.com/docs/2.pdf"}
                ]
            },
            {
                "id": 1002,
                "title": "Departamento moderno en San Isidro con vista al mar",
                "property_id": "EXT-1002",
                "property_type": "Departamento",
                "description": "Departamento moderno en edificio con amenities, vista al mar.",
                "price_usd": 150000,
                "department": "Lima",
                "province": "Lima",
                "district": "San Isidro",
                "address": "Calle Los Pinos 456",
                "built_area": 95,
                "land_area": 0,
                "bedrooms": 3,
                "bathrooms": 2,
                "parking": 1,
                "latitude": -12.098,
                "longitude": -77.050,
                "url": "https://www.ejemplo.com/propiedad/1002",
                "main_image": "https://images.unsplash.com/photo-1545324418-cc1a3fa10c00",
                "publication_date": "2026-02-18",
                "docs": [
                    {"id": 3, "name": "Reglamento interno", "url": "https://ejemplo.com/docs/3.pdf"},
                    {"id": 4, "name": "Estado de cuenta", "url": "https://ejemplo.com/docs/4.pdf"}
                ]
            },
            {
                "id": 1003,
                "title": "Terreno plano en Cayma para proyecto residencial",
                "property_id": "EXT-1003",
                "property_type": "Terreno",
                "description": "Terreno plano ideal para proyecto residencial o comercial.",
                "price_usd": 80000,
                "department": "Arequipa",
                "province": "Arequipa",
                "district": "Cayma",
                "address": "Carretera a Yura Km 5",
                "built_area": 0,
                "land_area": 500,
                "bedrooms": 0,
                "bathrooms": 0,
                "parking": 0,
                "latitude": -16.398,
                "longitude": -71.535,
                "url": "https://www.ejemplo.com/propiedad/1003",
                "main_image": "https://images.unsplash.com/photo-1542601906990-b4d3fb778b09",
                "publication_date": "2026-02-15",
                "docs": [
                    {"id": 5, "name": "Estudio de suelos", "url": "https://ejemplo.com/docs/5.pdf"},
                    {"id": 6, "name": "Permiso municipal", "url": "https://ejemplo.com/docs/6.pdf"}
                ]
            },
        ]
        
        # Formato de respuesta esperado por services_api.py (con clave 'results')
        response_data = {
            "results": propiedades_simuladas,
            "count": len(propiedades_simuladas),
            "next": None,
            "previous": None,
        }
        
        return Response(response_data)


class ComparablesAPIView(APIView):
    """
    Endpoint para buscar propiedades comparables basadas en ubicación y características.
    Similar a la función buscar_comparables en acm/views.py pero adaptada para API REST.
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        """
        Busca propiedades comparables.
        
        Parámetros esperados en el cuerpo JSON:
        - lat: latitud del punto de referencia (obligatorio)
        - lng: longitud del punto de referencia (obligatorio)
        - radio: radio de búsqueda en metros (opcional, default 500)
        - tipo_propiedad: tipo de propiedad (opcional)
        - metros_construccion: área construida aproximada (opcional)
        - metros_terreno: área de terreno aproximada (opcional)
        - habitaciones: número de habitaciones (opcional)
        - banos: número de baños (opcional)
        """
        from acm.utils import haversine, calcular_precio_m2
        from propifai.mapeo_ubicaciones import DEPARTAMENTOS, PROVINCIAS, DISTRITOS
        import json
        
        try:
            data = request.data
            
            # Validar parámetros obligatorios
            lat = data.get('lat')
            lng = data.get('lng')
            if lat is None or lng is None:
                return Response(
                    {'error': 'Los parámetros lat y lng son obligatorios'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                lat = float(lat)
                lng = float(lng)
            except (ValueError, TypeError):
                return Response(
                    {'error': 'lat y lng deben ser números válidos'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validar coordenadas
            if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
                return Response(
                    {'error': 'Coordenadas inválidas'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            radio = float(data.get('radio', 500))
            tipo_propiedad = data.get('tipo_propiedad', '').strip()
            
            # Obtener propiedades locales (PropiedadRaw)
            propiedades_locales = PropiedadRaw.objects.exclude(
                coordenadas__isnull=True
            ).exclude(
                coordenadas=''
            )
            
            # Filtrar por tipo si se especifica
            if tipo_propiedad:
                from django.db.models import Q
                propiedades_locales = propiedades_locales.filter(
                    Q(tipo_propiedad__icontains=tipo_propiedad) |
                    Q(atributos_extras__tipo_propiedad__icontains=tipo_propiedad) |
                    Q(atributos_extras__tipo__icontains=tipo_propiedad)
                )
            
            # Convertir a lista para procesar
            propiedades_list = list(propiedades_locales)
            
            # Obtener propiedades de Propifai (si está disponible)
            propiedades_propifai_list = []
            try:
                from propifai.models import PropifaiProperty
                
                # Diccionario de coordenadas aproximadas por distrito (para Arequipa y Lima principalmente)
                COORDENADAS_APROXIMADAS = {
                    # Arequipa
                    'Yanahuara': (-16.3889, -71.5350),
                    'Cayma': (-16.4000, -71.5300),
                    'Cerro Colorado': (-16.3800, -71.5200),
                    'Sachaca': (-16.4200, -71.5400),
                    'Hunter': (-16.4100, -71.5250),
                    'Mariano Melgar': (-16.4050, -71.5150),
                    'Miraflores': (-16.3950, -71.5450),
                    'Paucarpata': (-16.4300, -71.5100),
                    'Sabandia': (-16.4400, -71.5500),
                    'Socabaya': (-16.4500, -71.5200),
                    'Tiabaya': (-16.4600, -71.5300),
                    'Alto Selva Alegre': (-16.3850, -71.5100),
                    'Jacobo Hunter': (-16.4150, -71.5200),
                    'Jose Luis Bustamante y Rivero': (-16.3900, -71.5000),
                    # Lima
                    'Miraflores': (-12.1189, -77.0339),
                    'San Isidro': (-12.0975, -77.0428),
                    'San Borja': (-12.1000, -77.0083),
                    'Surco': (-12.1333, -77.0000),
                    'La Molina': (-12.0833, -76.9500),
                    'Jesus Maria': (-12.0833, -77.0500),
                    'Lince': (-12.0833, -77.0333),
                    'Magdalena': (-12.1000, -77.0667),
                    'Pueblo Libre': (-12.0667, -77.0667),
                    'San Miguel': (-12.0833, -77.1000),
                    'Callao': (-12.0500, -77.1333),
                }
                
                # Obtener TODAS las propiedades de Propifai primero
                propiedades_propifai = PropifaiProperty.objects.using('propifai').all()
                
                # Filtrar por tipo si se especifica
                if tipo_propiedad:
                    propiedades_propifai = propiedades_propifai.filter(
                        Q(title__icontains=tipo_propiedad)
                    )
                
                # Convertir a lista y procesar
                todas_propifai = list(propiedades_propifai)
                
                for prop in todas_propifai:
                    # Verificar si tiene coordenadas válidas usando las propiedades latitude/longitude
                    if prop.latitude is not None and prop.longitude is not None:
                        propiedades_propifai_list.append(prop)
                    else:
                        # Intentar obtener coordenadas aproximadas por distrito
                        distrito_nombre = None
                        if prop.district:
                            # Obtener nombre del distrito desde el mapeo
                            distrito_id = str(prop.district)
                            distrito_nombre = DISTRITOS.get(distrito_id, distrito_id)
                        
                        # Buscar coordenadas aproximadas para este distrito
                        if distrito_nombre and distrito_nombre in COORDENADAS_APROXIMADAS:
                            prop_lat, prop_lng = COORDENADAS_APROXIMADAS[distrito_nombre]
                            # Crear una copia del objeto con coordenadas aproximadas
                            class PropiedadConCoordenadas:
                                def __init__(self, original, lat, lng):
                                    self.__dict__ = original.__dict__.copy()
                                    self._latitude = lat
                                    self._longitude = lng
                                
                                @property
                                def latitude(self):
                                    return self._latitude
                                
                                @property
                                def longitude(self):
                                    return self._longitude
                            
                            prop_con_coords = PropiedadConCoordenadas(prop, prop_lat, prop_lng)
                            propiedades_propifai_list.append(prop_con_coords)
            
            except Exception as e:
                # Si hay error al obtener propiedades de Propifai, continuar solo con locales
                print(f"Error obteniendo propiedades de Propifai: {e}")
                pass
            
            # Combinar ambas listas
            todas_propiedades = propiedades_list + propiedades_propifai_list
            
            # Filtrar por distancia usando Haversine
            propiedades_cercanas = []
            for prop in todas_propiedades:
                # Determinar coordenadas según el tipo de propiedad
                if hasattr(prop, 'lat') and hasattr(prop, 'lng'):
                    # Propiedad local (PropiedadRaw)
                    prop_lat = prop.lat
                    prop_lng = prop.lng
                    if prop_lat is None or prop_lng is None:
                        continue
                    
                    # Calcular distancia
                    distancia = haversine(lat, lng, prop_lat, prop_lng)
                    if distancia > radio:
                        continue
                    
                    # Calcular precio por m² para propiedades locales
                    precio_m2_info = calcular_precio_m2(prop)
                    
                    # Obtener ubicación
                    distrito = prop.distrito or ''
                    provincia = prop.provincia or ''
                    departamento = prop.departamento or ''
                    
                    # Crear diccionario para propiedad local
                    propiedad_dict = {
                        'id': prop.id,
                        'lat': prop_lat,
                        'lng': prop_lng,
                        'tipo': prop.tipo_propiedad or 'No especificado',
                        'precio': float(prop.precio_usd) if prop.precio_usd else None,
                        'precio_final': float(prop.precio_final_venta) if prop.precio_final_venta else None,
                        'metros_construccion': float(prop.area_construida) if prop.area_construida else None,
                        'metros_terreno': float(prop.area_terreno) if prop.area_terreno else None,
                        'habitaciones': prop.numero_habitaciones,
                        'baños': prop.numero_banos,
                        'estado': prop.get_estado_propiedad_display() if prop.estado_propiedad else 'En Publicación',
                        'distrito': distrito,
                        'provincia': provincia,
                        'departamento': departamento,
                        'imagen_url': prop.primera_imagen() if hasattr(prop, 'primera_imagen') else None,
                        'precio_m2': precio_m2_info.get('precio_m2'),
                        'precio_m2_final': precio_m2_info.get('precio_m2_final'),
                        'distancia_metros': round(distancia, 2),
                        'fuente': 'local',
                        'es_propify': False,
                    }
                    
                else:
                    # Propiedad de Propifai
                    prop_lat = prop.latitude
                    prop_lng = prop.longitude
                    if prop_lat is None or prop_lng is None:
                        continue
                    
                    # Calcular distancia
                    distancia = haversine(lat, lng, prop_lat, prop_lng)
                    if distancia > radio:
                        continue
                    
                    # Obtener nombres mapeados de ubicación
                    departamento_id = str(prop.department) if prop.department else ''
                    provincia_id = str(prop.province) if prop.province else ''
                    distrito_id = str(prop.district) if prop.district else ''
                    
                    departamento_nombre = DEPARTAMENTOS.get(departamento_id, departamento_id)
                    provincia_nombre = PROVINCIAS.get(provincia_id, provincia_id)
                    distrito_nombre = DISTRITOS.get(distrito_id, distrito_id)
                    
                    # Calcular precio por m² aproximado para Propifai
                    precio_m2 = None
                    precio_m2_final = None
                    
                    # Intentar calcular con built_area primero, luego land_area como alternativa
                    area_para_calculo = None
                    if prop.built_area and float(prop.built_area) > 0:
                        area_para_calculo = float(prop.built_area)
                    elif prop.land_area and float(prop.land_area) > 0:
                        area_para_calculo = float(prop.land_area)
                    
                    if prop.price and area_para_calculo:
                        try:
                            precio_m2 = float(prop.price) / area_para_calculo
                            precio_m2_final = precio_m2
                        except (ValueError, ZeroDivisionError):
                            pass
                    
                    # Determinar tipo de propiedad
                    tipo_propiedad_valor = 'Propiedad'
                    if hasattr(prop, 'tipo_propiedad'):
                        tipo_propiedad_valor = prop.tipo_propiedad or 'Propiedad'
                    elif prop.title:
                        titulo_lower = prop.title.lower()
                        if any(tipo in titulo_lower for tipo in ['casa', 'house']):
                            tipo_propiedad_valor = 'Casa'
                        elif any(tipo in titulo_lower for tipo in ['departamento', 'apartamento', 'apartment']):
                            tipo_propiedad_valor = 'Departamento'
                        elif any(tipo in titulo_lower for tipo in ['terreno', 'land', 'lote']):
                            tipo_propiedad_valor = 'Terreno'
                        elif any(tipo in titulo_lower for tipo in ['oficina', 'office', 'local']):
                            tipo_propiedad_valor = 'Oficina'
                    
                    propiedad_dict = {
                        'id': prop.id,
                        'lat': prop_lat,
                        'lng': prop_lng,
                        'tipo': tipo_propiedad_valor,
                        'precio': float(prop.price) if prop.price else None,
                        'precio_final': float(prop.price) if prop.price else None,
                        'metros_construccion': float(prop.built_area) if prop.built_area else None,
                        'metros_terreno': float(prop.land_area) if prop.land_area else None,
                        'habitaciones': prop.bedrooms,
                        'baños': prop.bathrooms,
                        'estado': 'En Publicación',
                        'distrito': distrito_nombre,
                        'provincia': provincia_nombre,
                        'departamento': departamento_nombre,
                        'imagen_url': prop.imagen_url if hasattr(prop, 'imagen_url') else None,
                        'precio_m2': precio_m2,
                        'precio_m2_final': precio_m2_final,
                        'distancia_metros': round(distancia, 2),
                        'fuente': 'propifai',
                        'es_propify': True,
                        'codigo': prop.code if hasattr(prop, 'code') else None,
                        'titulo': prop.title if hasattr(prop, 'title') else None,
                    }
                
                propiedades_cercanas.append(propiedad_dict)
            
            # Ordenar por distancia (más cercano primero)
            propiedades_cercanas.sort(key=lambda x: x['distancia_metros'])
            
            # Aplicar filtros adicionales si se proporcionan
            metros_construccion = data.get('metros_construccion')
            if metros_construccion:
                try:
                    metros_construccion = float(metros_construccion)
                    propiedades_cercanas = [p for p in propiedades_cercanas
                                           if p['metros_construccion'] is None
                                           or abs(p['metros_construccion'] - metros_construccion) / metros_construccion <= 0.3]
                except (ValueError, TypeError):
                    pass
            
            metros_terreno = data.get('metros_terreno')
            if metros_terreno:
                try:
                    metros_terreno = float(metros_terreno)
                    propiedades_cercanas = [p for p in propiedades_cercanas
                                           if p['metros_terreno'] is None
                                           or abs(p['metros_terreno'] - metros_terreno) / metros_terreno <= 0.3]
                except (ValueError, TypeError):
                    pass
            
            habitaciones = data.get('habitaciones')
            if habitaciones:
                try:
                    habitaciones = int(habitaciones)
                    propiedades_cercanas = [p for p in propiedades_cercanas
                                           if p['habitaciones'] is None
                                           or p['habitaciones'] == habitaciones]
                except (ValueError, TypeError):
                    pass
            
            banos = data.get('banos')
            if banos:
                try:
                    banos = float(banos)
                    propiedades_cercanas = [p for p in propiedades_cercanas
                                           if p['baños'] is None
                                           or p['baños'] == banos]
                except (ValueError, TypeError):
                    pass
            
            return Response({
                'status': 'ok',
                'total': len(propiedades_cercanas),
                'radio_metros': radio,
                'punto_referencia': {'lat': lat, 'lng': lng},
                'propiedades': propiedades_cercanas,
            })
        
        except Exception as e:
            print(f"Error en ComparablesAPIView: {e}")
            import traceback
            traceback.print_exc()
            return Response(
                {'error': 'Error interno del servidor', 'detalle': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )