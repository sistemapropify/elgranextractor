"""
Views para la API de matching.
"""

import logging
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.pagination import PageNumberPagination

from requerimientos.models import Requerimiento
from propifai.models import PropifaiProperty
from .models import MatchResult
from .serializers import (
    MatchResultSerializer,
    MatchingResultSerializer,
    MatchingEstadisticasSerializer,
    EjecutarMatchingSerializer,
    GuardarMatchingSerializer,
    RequerimientoSimpleSerializer,
)
from .engine import ejecutar_matching_requerimiento, guardar_resultados_matching

logger = logging.getLogger(__name__)


class MatchingPagination(PageNumberPagination):
    """Paginación personalizada para resultados de matching."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class MatchingViewSet(viewsets.ViewSet):
    """
    ViewSet para operaciones de matching.
    """
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    @action(detail=True, methods=['GET'])
    def ejecutar(self, request, pk=None):
        """
        GET /api/matching/{requerimiento_id}/ejecutar/
        
        Ejecuta el matching para un requerimiento y retorna resultados.
        """
        requerimiento = get_object_or_404(Requerimiento, pk=pk)
        
        # Parámetros opcionales
        limite = request.query_params.get('limite', 100)
        score_minimo = request.query_params.get('score_minimo', 0)
        
        try:
            limite = int(limite)
            score_minimo = float(score_minimo)
        except ValueError:
            return Response(
                {'error': 'Parámetros inválidos. limite y score_minimo deben ser números.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Obtener propiedades (con límite para performance)
        propiedades = PropifaiProperty.objects.all()[:limite]
        
        # Ejecutar matching
        resultados, estadisticas = ejecutar_matching_requerimiento(
            requerimiento.id,
            propiedades=propiedades
        )
        
        # Filtrar por score mínimo
        if score_minimo > 0:
            resultados = [r for r in resultados if r['score_total'] >= score_minimo]
            estadisticas['total_compatibles'] = len(resultados)
        
        # Serializar resultados
        resultados_serializer = MatchingResultSerializer(resultados, many=True)
        estadisticas_serializer = MatchingEstadisticasSerializer(estadisticas)
        
        return Response({
            'requerimiento': RequerimientoSimpleSerializer(requerimiento).data,
            'resultados': resultados_serializer.data,
            'estadisticas': estadisticas_serializer.data,
            'parametros': {
                'limite_propiedades': limite,
                'score_minimo': score_minimo,
                'total_resultados': len(resultados),
            }
        })
    
    @action(detail=True, methods=['GET'])
    def resumen(self, request, pk=None):
        """
        GET /api/matching/{requerimiento_id}/resumen/
        
        Retorna estadísticas del matching sin ejecutarlo nuevamente.
        Consulta los resultados guardados más recientes.
        """
        requerimiento = get_object_or_404(Requerimiento, pk=pk)
        
        # Obtener el último matching ejecutado para este requerimiento
        ultimo_matching = MatchResult.objects.filter(
            requerimiento=requerimiento
        ).order_by('-ejecutado_en').first()
        
        if not ultimo_matching:
            return Response({
                'mensaje': 'No se han ejecutado matchings para este requerimiento.',
                'requerimiento': RequerimientoSimpleSerializer(requerimiento).data,
            })
        
        # Calcular estadísticas desde los resultados guardados
        resultados = MatchResult.objects.filter(
            requerimiento=requerimiento,
            ejecutado_en=ultimo_matching.ejecutado_en
        )
        
        total_evaluadas = resultados.count() + resultados.filter(
            fase_eliminada__isnull=False
        ).count()  # Estimación
        
        compatibles = resultados.filter(fase_eliminada__isnull=True)
        total_compatibles = compatibles.count()
        
        # Calcular descartadas por campo
        descartadas_por_campo = {}
        for campo in ['tipo_propiedad', 'metodo_pago', 'distrito', 'presupuesto']:
            descartadas_por_campo[campo] = resultados.filter(
                fase_eliminada=campo
            ).count()
        
        # Score promedio
        if total_compatibles > 0:
            from django.db.models import Avg
            score_promedio = compatibles.aggregate(Avg('score_total'))['score_total__avg']
        else:
            score_promedio = 0
        
        # Propiedad top
        propiedad_top = compatibles.order_by('-score_total').first()
        propiedad_top_data = None
        if propiedad_top:
            propiedad_top_data = MatchResultSerializer(propiedad_top).data
        
        estadisticas = {
            'total_evaluadas': total_evaluadas,
            'total_descartadas': sum(descartadas_por_campo.values()),
            'total_compatibles': total_compatibles,
            'descartadas_por_campo': descartadas_por_campo,
            'score_promedio': score_promedio,
            'propiedad_top': propiedad_top_data,
            'fecha_ejecucion': ultimo_matching.ejecutado_en,
        }
        
        estadisticas_serializer = MatchingEstadisticasSerializer(estadisticas)
        
        return Response({
            'requerimiento': RequerimientoSimpleSerializer(requerimiento).data,
            'estadisticas': estadisticas_serializer.data,
            'fecha_ultimo_matching': ultimo_matching.ejecutado_en,
        })
    
    @action(detail=True, methods=['POST'])
    def guardar(self, request, pk=None):
        """
        POST /api/matching/{requerimiento_id}/guardar/
        
        Guarda los resultados de un matching en la base de datos.
        """
        requerimiento = get_object_or_404(Requerimiento, pk=pk)
        
        serializer = GuardarMatchingSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        resultados = serializer.validated_data['resultados']
        
        try:
            match_results = guardar_resultados_matching(requerimiento.id, resultados)
        except Exception as e:
            logger.error(f"Error al guardar resultados de matching: {e}")
            return Response(
                {'error': f'Error al guardar resultados: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        return Response({
            'mensaje': f'Se guardaron {len(match_results)} resultados de matching.',
            'total_guardados': len(match_results),
            'fecha_ejecucion': match_results[0].ejecutado_en if match_results else None,
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['GET'], url_path='historial/(?P<requerimiento_id>\d+)')
    def historial(self, request, requerimiento_id=None):
        """
        GET /api/matching/historial/{requerimiento_id}/
        
        Retorna el historial de matchings anteriores para un requerimiento.
        """
        requerimiento = get_object_or_404(Requerimiento, pk=requerimiento_id)
        
        # Agrupar por fecha de ejecución
        from django.db.models import Count, Avg, Max
        from django.db.models.functions import TruncDate
        
        historial = MatchResult.objects.filter(
            requerimiento=requerimiento
        ).annotate(
            fecha=TruncDate('ejecutado_en')
        ).values('fecha').annotate(
            total=Count('id'),
            compatibles=Count('id', filter=models.Q(fase_eliminada__isnull=True)),
            score_promedio=Avg('score_total', filter=models.Q(fase_eliminada__isnull=True)),
            score_maximo=Max('score_total', filter=models.Q(fase_eliminada__isnull=True)),
        ).order_by('-fecha')
        
        # Obtener detalles de cada ejecución
        detalles = []
        for item in historial:
            fecha = item['fecha']
            ejecuciones = MatchResult.objects.filter(
                requerimiento=requerimiento,
                ejecutado_en__date=fecha
            ).distinct('ejecutado_en').values('ejecutado_en').order_by('-ejecutado_en')
            
            detalles.append({
                'fecha': fecha,
                'total_ejecuciones': ejecuciones.count(),
                'total_resultados': item['total'],
                'total_compatibles': item['compatibles'],
                'score_promedio': item['score_promedio'] or 0,
                'score_maximo': item['score_maximo'] or 0,
                'ejecuciones': list(ejecuciones[:5]),  # Últimas 5 ejecuciones del día
            })
        
        return Response({
            'requerimiento': RequerimientoSimpleSerializer(requerimiento).data,
            'historial': detalles,
            'total_ejecuciones': MatchResult.objects.filter(
                requerimiento=requerimiento
            ).values('ejecutado_en').distinct().count(),
        })


class MatchResultViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para consultar resultados de matching guardados.
    """
    queryset = MatchResult.objects.all()
    serializer_class = MatchResultSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = MatchingPagination
    
    def get_queryset(self):
        """
        Filtra los resultados por requerimiento si se especifica.
        """
        queryset = super().get_queryset()
        
        requerimiento_id = self.request.query_params.get('requerimiento_id')
        if requerimiento_id:
            queryset = queryset.filter(requerimiento_id=requerimiento_id)
        
        score_minimo = self.request.query_params.get('score_minimo')
        if score_minimo:
            try:
                score_minimo = float(score_minimo)
                queryset = queryset.filter(score_total__gte=score_minimo)
            except ValueError:
                pass
        
        # Solo resultados compatibles por defecto
        solo_compatibles = self.request.query_params.get('solo_compatibles', 'true')
        if solo_compatibles.lower() == 'true':
            queryset = queryset.filter(fase_eliminada__isnull=True)
        
        return queryset.order_by('-ejecutado_en', '-score_total')


# Vista para el dashboard
from django.views.generic import TemplateView
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from .engine import obtener_resumen_matching_masivo, ejecutar_matching_masivo


class MatchingDashboardView(TemplateView):
    """
    Vista para el dashboard visual de matching.
    """
    template_name = 'matching/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Obtener requerimientos para el selector
        requerimientos = Requerimiento.objects.all().order_by('-fecha', '-hora')[:50]
        context['requerimientos'] = requerimientos
        
        # Si hay un requerimiento_id en la URL, agregarlo al contexto
        requerimiento_id = self.request.GET.get('requerimiento_id')
        if requerimiento_id:
            try:
                requerimiento = Requerimiento.objects.get(id=requerimiento_id)
                context['requerimiento_seleccionado'] = requerimiento
            except Requerimiento.DoesNotExist:
                pass
        
        # Estadísticas generales
        context['total_matchings'] = MatchResult.objects.count()
        context['total_requerimientos'] = Requerimiento.objects.count()
        context['total_propiedades'] = PropifaiProperty.objects.count()
        
        return context


class MatchingMasivoView(TemplateView):
    """
    Vista para el matching masivo que muestra todos los requerimientos
    con sus porcentajes de matching en una grilla.
    """
    template_name = 'matching/masivo.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Obtener resumen de matching masivo (limitado a 500)
        resumen = obtener_resumen_matching_masivo()
        context['resumen'] = resumen
        
        # Crear diccionario de porcentajes por requerimiento_id para acceso rápido
        porcentajes_por_requerimiento = {
            item['requerimiento_id']: item['porcentaje_match'] for item in resumen
        }
        context['porcentajes_por_requerimiento'] = porcentajes_por_requerimiento
        
        # Obtener requerimientos paginados (solo los más recientes)
        requerimientos_qs = Requerimiento.objects.all().order_by('-fecha', '-hora')
        
        # Paginación directa sobre QuerySet (más eficiente)
        paginator = Paginator(requerimientos_qs, 50)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Crear diccionario con toda la información del resumen por requerimiento_id
        resumen_por_requerimiento = {item['requerimiento_id']: item for item in resumen}
        
        # Preparar lista de requerimientos con sus porcentajes y clases CSS solo para la página actual
        requerimientos_con_porcentajes = []
        for req in page_obj:
            info_resumen = resumen_por_requerimiento.get(req.id)
            if info_resumen:
                porcentaje = info_resumen['porcentaje_match']
                mejor_propiedad_id = info_resumen.get('mejor_propiedad_id')
                mejor_propiedad_codigo = info_resumen.get('mejor_propiedad_codigo')
                mejor_propiedad_distrito = info_resumen.get('mejor_propiedad_distrito')
                mejor_propiedad_precio = info_resumen.get('mejor_propiedad_precio')
                total_compatibles = info_resumen.get('total_compatibles', 0)
            else:
                porcentaje = 0.0
                mejor_propiedad_id = None
                mejor_propiedad_codigo = None
                mejor_propiedad_distrito = None
                mejor_propiedad_precio = None
                total_compatibles = 0
            
            # Determinar clases CSS según el porcentaje
            if porcentaje >= 80:
                row_class = "match-high-row"
                badge_class = "badge-match-high"
                progress_class = "match-high"
                estado_text = "Match Alto"
            elif porcentaje >= 50:
                row_class = "match-medium-row"
                badge_class = "badge-match-medium"
                progress_class = "match-medium"
                estado_text = "Match Medio"
            else:
                row_class = "match-low-row"
                badge_class = "badge-match-low"
                progress_class = "match-low"
                estado_text = "Match Bajo"
            
            requerimientos_con_porcentajes.append({
                'requerimiento': req,
                'porcentaje': porcentaje,
                'row_class': row_class,
                'badge_class': badge_class,
                'progress_class': progress_class,
                'estado_text': estado_text,
                'mejor_propiedad_id': mejor_propiedad_id,
                'mejor_propiedad_codigo': mejor_propiedad_codigo,
                'mejor_propiedad_distrito': mejor_propiedad_distrito,
                'mejor_propiedad_precio': mejor_propiedad_precio,
                'total_compatibles': total_compatibles,
                'tiene_propiedad_match': mejor_propiedad_id is not None,
            })
        
        context['page_obj'] = page_obj
        context['requerimientos_con_porcentajes'] = requerimientos_con_porcentajes
        
        # Estadísticas (usar counts eficientes)
        context['total_requerimientos'] = requerimientos_qs.count()
        
        # Contar propiedades Propifai - manejar error si la tabla no existe
        try:
            context['total_propiedades'] = PropifaiProperty.objects.count()
        except Exception as e:
            # Si hay error (tabla no existe, conexión fallida, etc.), usar 0
            print(f"Error al contar propiedades Propifai: {e}")
            context['total_propiedades'] = 0
        
        # Contar requerimientos con match alto (>80%) en el resumen
        match_alto_count = sum(1 for item in resumen if item['porcentaje_match'] >= 80)
        context['match_alto_count'] = match_alto_count
        
        return context


@method_decorator(csrf_exempt, name='dispatch')
class EjecutarMatchingMasivoView(TemplateView):
    """
    Vista para ejecutar matching masivo (AJAX).
    """
    template_name = 'matching/masivo.html'
    
    def post(self, request, *args, **kwargs):
        """
        Ejecuta matching masivo y retorna resultados en JSON.
        """
        try:
            # Parámetros opcionales
            limite_por_requerimiento = int(request.POST.get('limite_por_requerimiento', 10))
            
            # Ejecutar matching masivo
            resultados = ejecutar_matching_masivo(
                limite_por_requerimiento=limite_por_requerimiento
            )
            
            return JsonResponse({
                'success': True,
                'message': f'Matching masivo ejecutado exitosamente. Se procesaron {len(resultados)} requerimientos.',
                'resultados': resultados,
                'total_procesados': len(resultados)
            })
            
        except Exception as e:
            logger.error(f"Error en matching masivo: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
