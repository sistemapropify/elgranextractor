"""
Views para la API de matching.
"""

import logging
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly
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
    PropuestaWhatsAppSerializer,
    PropuestaWhatsAppCreateSerializer,
    PropuestaWhatsAppStatusSerializer,
)
from .engine import ejecutar_matching_requerimiento, guardar_resultados_matching
from .models import PropuestaWhatsApp

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
        Además, GUARDA automáticamente los resultados en MatchResult
        para que persistan y se vean en el calendario.
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
        
        # Ejecutar matching (el motor cargará las propiedades desde la BD)
        resultados, estadisticas = ejecutar_matching_requerimiento(
            requerimiento.id
        )
        
        # Filtrar por score mínimo
        if score_minimo > 0:
            resultados = [r for r in resultados if r['score_total'] >= score_minimo]
            estadisticas['total_compatibles'] = len(resultados)
        
        # ── Guardar resultados automáticamente en MatchResult ──
        try:
            from .engine import guardar_resultados_matching
            guardar_resultados_matching(requerimiento.id, resultados)
            logger.info(f"Resultados de matching guardados para requerimiento #{requerimiento.id}")
        except Exception as e:
            logger.warning(f"No se pudieron guardar resultados de matching: {e}")
        
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


class PropuestaWhatsAppViewSet(viewsets.ViewSet):
    """
    ViewSet para gestionar propuestas enviadas por WhatsApp.
    """
    permission_classes = [AllowAny]

    @action(detail=False, methods=['POST'])
    def guardar(self, request):
        """
        POST /matching/api/propuesta/guardar/
        Guarda un registro de propuesta enviada por WhatsApp.
        """
        serializer = PropuestaWhatsAppCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        propuesta = PropuestaWhatsApp.objects.create(
            requerimiento_id=data['requerimiento_id'],
            propiedad_id=data.get('propiedad_id'),
            propiedad_code=data.get('propiedad_code', ''),
            propiedad_title=data.get('propiedad_title', ''),
            propiedad_price=data.get('propiedad_price'),
            propiedad_currency_id=data.get('propiedad_currency_id'),
            propiedad_district_id=data.get('propiedad_district_id'),
            agente_nombre=data.get('agente_nombre', ''),
            agente_telefono=data.get('agente_telefono', ''),
            mensaje_enviado=data.get('mensaje', ''),
            status=PropuestaWhatsApp.Status.ENVIADA,
        )

        return Response(
            PropuestaWhatsAppSerializer(propuesta).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['POST'])
    def actualizar_status(self, request, pk=None):
        """
        POST /matching/api/propuesta/<id>/actualizar-status/
        Actualiza el status de una propuesta.
        """
        propuesta = get_object_or_404(PropuestaWhatsApp, pk=pk)

        serializer = PropuestaWhatsAppStatusSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        nuevo_status = serializer.validated_data['status']
        propuesta.status = nuevo_status

        from django.utils import timezone
        if nuevo_status in ('respondida', 'interesado', 'no_interesado'):
            if not propuesta.respondido_en:
                propuesta.respondido_en = timezone.now()

        propuesta.save(update_fields=['status', 'respondido_en'])

        return Response(PropuestaWhatsAppSerializer(propuesta).data)

    @action(detail=False, methods=['GET'], permission_classes=[AllowAny])
    def listar(self, request):
        """
        GET /matching/api/propuesta/listar/
        Lista todas las propuestas, opcionalmente filtradas por agente.
        """
        queryset = PropuestaWhatsApp.objects.all().order_by('-enviado_en')

        agente_nombre = request.query_params.get('agente_nombre')
        if agente_nombre:
            queryset = queryset.filter(agente_nombre__icontains=agente_nombre)

        agente_telefono = request.query_params.get('agente_telefono')
        if agente_telefono:
            queryset = queryset.filter(agente_telefono=agente_telefono)

        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        requerimiento_id = request.query_params.get('requerimiento_id')
        if requerimiento_id:
            queryset = queryset.filter(requerimiento_id=requerimiento_id)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = PropuestaWhatsAppSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = PropuestaWhatsAppSerializer(queryset, many=True)
        return Response(serializer.data)


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


def _obtener_resumen_calendario(limite=500, umbral_minimo=70):
    """
    Obtiene resumen de matching para el calendario.
    Optimizado: evita JOIN con PropifaiProperty para no depender de esa tabla.
    Usa datos de MatchResult + Requerimiento.
    
    Solo incluye requerimientos con porcentaje_match >= umbral_minimo (default: 70%).
    Los requerimientos sin MatchResult (score 0) NO se incluyen.
    """
    try:
        from django.db.models import Max
        from .models import MatchResult
        from requerimientos.models import Requerimiento
        
        # ── Solo requerimientos CON MatchResult ──
        resultados_con_match = MatchResult.objects.values(
            'requerimiento_id'
        ).annotate(
            max_score=Max('score_total')
        ).order_by('-max_score')
        
        req_ids_con_match = [r['requerimiento_id'] for r in resultados_con_match]
        
        if not req_ids_con_match:
            return []
        
        # Cargar requerimientos con match
        reqs_con_match = Requerimiento.objects.filter(id__in=req_ids_con_match)
        reqs_map = {r.id: r for r in reqs_con_match}
        
        # Cargar mejores matches
        mejores = MatchResult.objects.filter(
            requerimiento_id__in=req_ids_con_match
        ).order_by('requerimiento_id', '-score_total')
        
        mejores_por_req = {}
        for m in mejores:
            if m.requerimiento_id not in mejores_por_req:
                mejores_por_req[m.requerimiento_id] = m
        
        resumen = []
        for item in resultados_con_match:
            req_id = item['requerimiento_id']
            req = reqs_map.get(req_id)
            if not req:
                continue
            mejor = mejores_por_req.get(req_id)
            if mejor:
                score = float(mejor.score_total)
                # Solo incluir si supera el umbral mínimo
                if score >= umbral_minimo:
                    resumen.append({
                        'requerimiento_id': req_id,
                        'requerimiento_nombre': str(req),
                        'porcentaje_match': score,
                        'score_promedio': score,
                        'total_compatibles': 1,
                        'mejor_propiedad_id': mejor.propiedad_id,
                        'mejor_propiedad_codigo': None,
                        'mejor_propiedad_titulo': None,
                        'mejor_propiedad_distrito': None,
                        'mejor_propiedad_precio': None,
                        'mejor_propiedad_moneda_id': None,
                        'mejor_propiedad_tipo': None,
                        'fecha_ultimo_matching': mejor.ejecutado_en.isoformat() if mejor.ejecutado_en else None,
                    })
        
        resumen.sort(key=lambda x: x['porcentaje_match'], reverse=True)
        return resumen[:limite]
        
    except Exception as e:
        logger.warning(f"No se pudo obtener resumen de matching para calendario: {e}")
        return []


class MatchingCalendarView(TemplateView):
    """
    Vista calendario tipo Google Calendar para requerimientos y sus matches.
    
    Soporta 3 vistas: mes, semana, día.
    Muestra total de requerimientos por día y total de matches >= 90%.
    """
    template_name = 'matching/calendar.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        import json
        from datetime import datetime, timedelta, date
        import calendar
        
        # Obtener parámetros de vista
        view_mode = self.request.GET.get('view', 'month')
        year = int(self.request.GET.get('year', datetime.now().year))
        month = int(self.request.GET.get('month', datetime.now().month))
        day = int(self.request.GET.get('day', datetime.now().day))
        semana_seleccionada = self.request.GET.get('semana', '')
        
        # Fecha actual para navegación
        today = date.today()
        context['today'] = today
        context['current_year'] = year
        context['current_month'] = month
        context['current_day'] = day
        context['view_mode'] = view_mode
        context['semana_seleccionada'] = semana_seleccionada
        
        # ── Años disponibles (últimos 5, siguientes 2) ──
        context['years_disponibles'] = list(range(today.year - 5, today.year + 3))
        
        # ── Meses disponibles ──
        meses_nombres = [
            'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
            'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
        ]
        context['months_disponibles'] = [
            {'num': i + 1, 'nombre': meses_nombres[i]}
            for i in range(12)
        ]
        
        # ── Semanas del mes ──
        cal = calendar.Calendar()
        month_days = cal.monthdays2calendar(year, month)
        semanas_del_mes = []
        for idx, week in enumerate(month_days):
            dias_reales = [d[0] for d in week if d[0] > 0]
            if dias_reales:
                semanas_del_mes.append({
                    'num': idx + 1,
                    'inicio': f"{min(dias_reales):02d}/{month:02d}",
                    'fin': f"{max(dias_reales):02d}/{month:02d}",
                })
        context['semanas_del_mes'] = semanas_del_mes
        
        # ── Tipos de propiedad para filtros ──
        from requerimientos.models import TipoPropiedadChoices
        tipos_propiedad = [
            {'key': choice.value, 'label': choice.label}
            for choice in TipoPropiedadChoices
            if choice.value != 'no_especificado'
        ]
        context['tipos_propiedad'] = tipos_propiedad
        context['tipos_propiedad_json'] = json.dumps(tipos_propiedad)
        
        # Obtener resumen de matching masivo para todos los requerimientos
        # Optimizado: una sola consulta con select_related, sin N+1
        resumen = _obtener_resumen_calendario()
        resumen_por_req = {item['requerimiento_id']: item for item in resumen}
        
        # Filtrar requerimientos no deseados (no_especificado y compartido)
        condicion_excluir = ['no_especificado', 'compartido']
        
        if view_mode == 'month':
            # Construir grid del mes
            cal = calendar.Calendar()
            month_days = cal.monthdays2calendar(year, month)
            
            # ── Filtrar por semana seleccionada ──
            if semana_seleccionada:
                try:
                    semana_idx = int(semana_seleccionada) - 1
                    if 0 <= semana_idx < len(month_days):
                        month_days = [month_days[semana_idx]]
                except (ValueError, IndexError):
                    pass
            
            # Construir reqs_por_fecha como dict con key "YYYY-MM-DD"
            # Optimización: cargar todos los requerimientos en UNA consulta en lugar de N+1
            req_ids = list(resumen_por_req.keys())
            requerimientos = Requerimiento.objects.filter(
                id__in=req_ids
            ).exclude(condicion__in=condicion_excluir)
            reqs_map = {r.id: r for r in requerimientos}
            
            reqs_por_fecha = {}
            for req_id, info in resumen_por_req.items():
                r = reqs_map.get(req_id)
                if not r:
                    continue
                if r.fecha:
                    fecha_key = r.fecha.isoformat()  # "2026-05-15"
                    if fecha_key not in reqs_por_fecha:
                        reqs_por_fecha[fecha_key] = {'total': 0, 'con_match_alto': 0}
                    reqs_por_fecha[fecha_key]['total'] += 1
                    if info['porcentaje_match'] >= 90:
                        reqs_por_fecha[fecha_key]['con_match_alto'] += 1
            
            context['month_days'] = month_days
            context['reqs_por_fecha_json'] = json.dumps(reqs_por_fecha)
            context['month_name'] = calendar.month_name[month]
            
        elif view_mode == 'week':
            # Calcular inicio y fin de la semana
            week_start = date(year, month, day)
            week_start = week_start - timedelta(days=week_start.weekday())
            week_end = week_start + timedelta(days=6)
            
            # Obtener requerimientos de esa semana (excluyendo no_especificado y compartido)
            reqs_semana = Requerimiento.objects.filter(
                fecha__isnull=False,
                fecha__gte=week_start,
                fecha__lte=week_end
            ).exclude(
                condicion__in=condicion_excluir
            ).order_by('fecha', 'hora').distinct()
            
            # Agrupar por día con info de match serializada
            dias_semana = []
            for i in range(7):
                d = week_start + timedelta(days=i)
                reqs_dia = [r for r in reqs_semana if r.fecha == d]
                reqs_serializados = []
                # Obtener IDs de requerimientos con WhatsApp enviado
                from .models import PropuestaWhatsApp
                reqs_con_whatsapp = set(
                    PropuestaWhatsApp.objects.filter(
                        requerimiento_id__in=[r.id for r in reqs_dia]
                    ).values_list('requerimiento_id', flat=True)
                )
                for r in reqs_dia:
                    info = resumen_por_req.get(r.id, {})
                    # Formatear presupuesto con signo de moneda
                    presupuesto_monto = float(r.presupuesto_monto) if r.presupuesto_monto else None
                    presupuesto_display = ''
                    if presupuesto_monto and r.presupuesto_moneda:
                        signo = '$' if r.presupuesto_moneda == 'USD' else 'S/'
                        presupuesto_display = f'{signo}{presupuesto_monto:,.0f}'
                    # Lista de distritos (separados por coma)
                    distritos_raw = r.distritos or ''
                    distritos_list = [d.strip() for d in distritos_raw.split(',') if d.strip()]
                    # Buscar ID del agente por nombre
                    agente_nombre_limpio = (r.agente or '').replace('\n', ' ').replace('\r', ' ').strip()
                    agente_id = None
                    if agente_nombre_limpio:
                        try:
                            from agentes.models import Agente
                            agente_obj = Agente.objects.filter(
                                nombre_completo__icontains=agente_nombre_limpio
                            ).first()
                            if agente_obj:
                                agente_id = agente_obj.id
                        except Exception:
                            pass
                    reqs_serializados.append({
                        'id': r.id,
                        'hora': r.hora.isoformat() if r.hora else None,
                        'hora_display': r.hora.strftime('%H:%M') if r.hora else '--:--',
                        'tipo_propiedad': (r.get_tipo_propiedad_display() or r.tipo_propiedad or 'Propiedad').upper(),
                        'tipo_propiedad_key': r.tipo_propiedad or '',
                        'presupuesto_display': presupuesto_display,
                        'presupuesto_monto': presupuesto_monto,
                        'presupuesto_moneda': r.presupuesto_moneda or '',
                        'agente': agente_nombre_limpio,
                        'agente_id': agente_id,
                        'distritos': r.distritos[:50] if r.distritos else '',
                        'distritos_list': distritos_list,
                        'porcentaje_match': info.get('porcentaje_match', 0),
                        'mejor_propiedad_codigo': info.get('mejor_propiedad_codigo'),
                        'mejor_propiedad_precio': info.get('mejor_propiedad_precio'),
                        'mejor_propiedad_moneda_id': info.get('mejor_propiedad_moneda_id'),
                        'verificado': r.verificado,
                        'whatsapp_enviado': r.id in reqs_con_whatsapp,
                    })
                dias_semana.append({
                    'date_iso': d.isoformat(),
                    'date_display': d.strftime('%d'),
                    'day_name': d.strftime('%a'),
                    'is_today': d == today,
                    'requerimientos': reqs_serializados,
                    'total': len(reqs_dia),
                    'con_match_alto': sum(
                        1 for r in reqs_dia
                        if resumen_por_req.get(r.id, {}).get('porcentaje_match', 0) >= 90
                    ),
                })
            
            # Generar horas del día (7am a 11pm)
            horas_del_dia = []
            for h in range(7, 23):
                horas_del_dia.append(datetime(2000, 1, 1, h, 0).time())
            
            context['dias_semana'] = dias_semana
            context['dias_semana_json'] = json.dumps(dias_semana)
            context['horas_del_dia'] = horas_del_dia
            context['week_start'] = week_start
            context['week_end'] = week_end
            context['resumen_por_req'] = resumen_por_req
            
            # Navegación
            context['prev_week_start'] = week_start - timedelta(days=7)
            context['next_week_start'] = week_start + timedelta(days=7)
            
        elif view_mode == 'year':
            # ── VISTA AÑO: 12 meses, todos los días del año ──
            # Optimización: una sola consulta agregada en lugar de 365 queries
            from django.db.models import Count
            year_start = date(year, 1, 1)
            year_end = date(year, 12, 31)
            reqs_por_dia = (
                Requerimiento.objects.filter(
                    fecha__gte=year_start,
                    fecha__lte=year_end,
                )
                .exclude(condicion__in=condicion_excluir)
                .order_by()  # ← Limpia cualquier ordering por defecto (SQL Server no permite ORDER BY fuera de GROUP BY)
                .values('fecha')
                .annotate(total=Count('id'))
            )
            # Convertir a dict para lookup O(1): { '2026-05-15': 3 }
            reqs_count_map = {}
            for item in reqs_por_dia:
                if item['fecha']:
                    reqs_count_map[item['fecha'].isoformat()] = item['total']
            
            year_months = []
            total_anual = sum(reqs_count_map.values())
            for m in range(1, 13):
                cal_m = calendar.Calendar()
                month_weeks = cal_m.monthdays2calendar(year, m)
                month_data = {
                    'month_num': m,
                    'month_name': calendar.month_name[m][:3].upper(),  # ENE, FEB, etc.
                    'weeks': [],
                    'total_reqs': 0,
                }
                for week in month_weeks:
                    week_days = []
                    for day_num, weekday in week:
                        day_info = {
                            'day_num': day_num,
                            'weekday': weekday,
                            'is_current_month': day_num > 0,
                            'req_count': 0,
                            'date_iso': '',
                        }
                        if day_num > 0:
                            d = date(year, m, day_num)
                            day_info['date_iso'] = d.isoformat()
                            day_info['req_count'] = reqs_count_map.get(d.isoformat(), 0)
                            month_data['total_reqs'] += day_info['req_count']
                        week_days.append(day_info)
                    month_data['weeks'].append(week_days)
                year_months.append(month_data)
            
            context['year_months'] = year_months
            context['year_view'] = year
            context['total_anual'] = total_anual
            context['view_mode'] = 'year'
            
        elif view_mode == 'day':
            target_date = date(year, month, day)
            
            # Generar horas del día (6am a 11pm)
            horas_del_dia = []
            for h in range(6, 23):
                horas_del_dia.append(datetime(2000, 1, 1, h, 0).time())
            
            # Obtener requerimientos de ese día (excluyendo no_especificado y compartido)
            reqs_dia = Requerimiento.objects.filter(
                fecha=target_date
            ).exclude(
                condicion__in=condicion_excluir
            ).order_by('hora')
            
            reqs_serializados = []
            # Obtener IDs de requerimientos con WhatsApp enviado
            from .models import PropuestaWhatsApp
            reqs_con_whatsapp = set(
                PropuestaWhatsApp.objects.filter(
                    requerimiento_id__in=[r.id for r in reqs_dia]
                ).values_list('requerimiento_id', flat=True)
            )
            for r in reqs_dia:
                info = resumen_por_req.get(r.id, {})
                # Formatear presupuesto con signo de moneda
                presupuesto_monto = float(r.presupuesto_monto) if r.presupuesto_monto else None
                presupuesto_display = ''
                if presupuesto_monto and r.presupuesto_moneda:
                    signo = '$' if r.presupuesto_moneda == 'USD' else 'S/'
                    presupuesto_display = f'{signo}{presupuesto_monto:,.0f}'
                # Lista de distritos (separados por coma)
                distritos_raw = r.distritos or ''
                distritos_list = [d.strip() for d in distritos_raw.split(',') if d.strip()]
                # Buscar ID del agente por nombre
                agente_nombre_limpio = (r.agente or '').replace('\n', ' ').replace('\r', ' ').strip()
                agente_id = None
                if agente_nombre_limpio:
                    try:
                        from agentes.models import Agente
                        agente_obj = Agente.objects.filter(
                            nombre_completo__icontains=agente_nombre_limpio
                        ).first()
                        if agente_obj:
                            agente_id = agente_obj.id
                    except Exception:
                        pass
                reqs_serializados.append({
                    'id': r.id,
                    'hora': r.hora.isoformat() if r.hora else None,
                    'hora_display': r.hora.strftime('%H:%M') if r.hora else '--:--',
                    'tipo_display': (r.get_tipo_propiedad_display() or r.tipo_propiedad or 'Propiedad').upper(),
                    'tipo_propiedad_key': r.tipo_propiedad or '',
                    'presupuesto_display': presupuesto_display,
                    'presupuesto_monto': presupuesto_monto,
                    'presupuesto_moneda': r.presupuesto_moneda or '',
                    'agente': agente_nombre_limpio,
                    'agente_id': agente_id,
                    'distritos': r.distritos[:50] if r.distritos else '',
                    'distritos_list': distritos_list,
                    'porcentaje_match': info.get('porcentaje_match', 0),
                    'mejor_propiedad_codigo': info.get('mejor_propiedad_codigo'),
                    'mejor_propiedad_precio': info.get('mejor_propiedad_precio'),
                    'mejor_propiedad_moneda_id': info.get('mejor_propiedad_moneda_id'),
                    'verificado': r.verificado,
                    'whatsapp_enviado': r.id in reqs_con_whatsapp,
                })
            
            context['reqs_dia'] = reqs_serializados
            context['reqs_dia_json'] = json.dumps(reqs_serializados)
            context['target_date'] = target_date
            context['target_date_display'] = target_date.strftime('%A, %d %B %Y')
            context['total_reqs'] = len(reqs_serializados)
            context['total_match_alto'] = sum(
                1 for r in reqs_serializados
                if r['porcentaje_match'] >= 90
            )
            context['horas_del_dia'] = horas_del_dia
            
            # Navegación
            context['prev_date'] = target_date - timedelta(days=1)
            context['next_date'] = target_date + timedelta(days=1)
        
        # Estadísticas generales
        context['total_requerimientos'] = Requerimiento.objects.count()
        context['total_propiedades'] = PropifaiProperty.objects.count()
        
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
