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

# Cache en memoria para todos los matches (evita refetch en cada pipeline click)
_all_matches_cache = None
_all_matches_cache_client_id = None


def _get_cached_all_matches(client):
    """
    Obtiene todos los matches de Propify API, con caché en memoria.
    La API no soporta filtrar por property_id, así que obtenemos todo
    y filtramos en Python. El caché se invalida si cambia el cliente.
    """
    global _all_matches_cache, _all_matches_cache_client_id
    client_id = id(client)
    if _all_matches_cache is not None and _all_matches_cache_client_id == client_id:
        return _all_matches_cache

    all_matches = []
    page_num = 1
    page_size = 500
    while True:
        page_data = client.get_matches(page=page_num, page_size=page_size)
        if not page_data or not page_data.get('results'):
            break
        all_matches.extend(page_data['results'])
        if not page_data.get('next'):
            break
        page_num += 1

    _all_matches_cache = all_matches
    _all_matches_cache_client_id = client_id
    return all_matches


from .engine import ejecutar_matching_requerimiento, guardar_resultados_matching
from .models import PropuestaWhatsApp
from .pipeline_requerimiento import obtener_pipeline_requerimiento, obtener_pipeline_con_ramas

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
    
    @action(detail=True, methods=['GET'])
    def pipeline(self, request, pk=None):
        """
        GET /api/matching/{requerimiento_id}/pipeline/

        Retorna el pipeline de vida del requerimiento con las 4 etapas
        y los lapsos de tiempo entre cada una.
        """
        try:
            data = obtener_pipeline_requerimiento(pk)
            return Response(data)
        except Exception as e:
            logger.error(f"Error al obtener pipeline para req #{pk}: {e}")
            return Response(
                {'error': f'Error al obtener pipeline: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['GET'])
    def pipeline_ramas(self, request, pk=None):
        """
        GET /api/matching/{requerimiento_id}/pipeline-ramas/

        Retorna el pipeline multi-rama de un requerimiento.
        Muestra el nodo principal (📝 → 🎯) y todas las ramas de propuestas
        que se han enviado, cada una con su propia decisión.
        """
        try:
            data = obtener_pipeline_con_ramas(pk)
            return Response(data)
        except Exception as e:
            logger.error(f"Error al obtener pipeline con ramas para req #{pk}: {e}")
            return Response(
                {'error': f'Error al obtener pipeline con ramas: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['GET'])
    def pipeline_matches(self, request, pk=None):
        """
        GET /api/matching/{requerimiento_id}/pipeline-matches/

        Retorna los matches de un requerimiento para mostrar en pipeline horizontal,
        con el requerimiento como nodo principal y cada match como una rama.
        Estructura idéntica al pipeline de propuestas pero para matches.

        Adaptado de pipeline_ramas().
        """
        try:
            from .propify_api import get_propify_client
            client = get_propify_client()

            # Obtener datos del requerimiento
            req_data = client.get_requirement_detail(pk)
            if not req_data:
                return Response({'error': 'Requerimiento no encontrado'}, status=404)

            # Obtener matches de este requerimiento
            matches_data = client.get_matches(page=1, page_size=50, requirement_id=pk)
            matches = matches_data.get('results', []) if matches_data else []

            # Ordenar por score descendente
            matches.sort(key=lambda m: float(m.get('score', 0) or 0), reverse=True)

            # Enriquecer cada match con datos del requerimiento
            # Incluir fecha de creación de la propiedad y URL de imagen
            ramas = []
            for m in matches:
                prop_code = m.get('property_code', '')
                prop_created_at = ''
                prop_image_url = ''

                # Obtener datos adicionales de la propiedad desde API Propify
                prop_responsable = ''
                prop_id = m.get('property')
                if prop_id:
                    try:
                        prop_data = client.get_property_detail(prop_id)
                        if prop_data:
                            created = prop_data.get('created_at', '')
                            if created:
                                prop_created_at = created[:10]
                            resp_name = prop_data.get('created_by_name') or prop_data.get('responsible_name') or ''
                            if resp_name:
                                prop_responsable = resp_name
                            first_img = None
                            imgs = prop_data.get('images') or prop_data.get('property_images') or []
                            if imgs:
                                first_img = imgs[0]
                                if isinstance(first_img, dict):
                                    prop_image_url = first_img.get('url', '') or first_img.get('image', '')
                                else:
                                    prop_image_url = str(first_img)
                            if not prop_image_url and prop_code:
                                base_url = "https://propifymedia01.blob.core.windows.net/media"
                                prop_image_url = f"{base_url}/{prop_code}.jpg"
                    except Exception:
                        pass

                ramas.append({
                    'match_id': m.get('id'),
                    'propiedad_code': prop_code,
                    'propiedad_title': m.get('property_title', ''),
                    'propiedad_district': m.get('property_district_name', ''),
                    'propiedad_price': m.get('property_price'),
                    'propiedad_currency_name': m.get('property_currency_name', ''),
                    'propiedad_created_at': prop_created_at,
                    'propiedad_image_url': prop_image_url,
                    'propiedad_responsable': prop_responsable,
                    'score': float(m.get('score', 0) or 0),
                    'computed_at': m.get('computed_at', ''),
                })

            # Construir etapa_requerimiento (formato pipeline)
            from datetime import datetime
            try:
                fecha_req_str = req_data.get('created_at', '')
                if fecha_req_str:
                    fecha_dt = datetime.fromisoformat(fecha_req_str.replace('Z', '+00:00'))
                    fecha_display = fecha_dt.strftime('%d/%m')
                else:
                    fecha_display = '—'
            except Exception:
                fecha_display = '—'

            etapa_requerimiento = {
                'tipo': 'requerimiento',
                'label': req_data.get('code', f'#{pk}'),
                'icono': '📝',
                'fecha_display': fecha_display,
                'estado': 'ok',
            }

            # Formatear fecha completa del requerimiento (DD/MM HH:MM como en pipeline propuestas)
            try:
                if fecha_req_str:
                    fecha_req_dt = datetime.fromisoformat(fecha_req_str.replace('Z', '+00:00'))
                    req_fecha_display = fecha_req_dt.strftime('%d/%m %H:%M')
                    req_created_at_iso = fecha_req_dt.isoformat()
                else:
                    req_fecha_display = '—'
                    req_created_at_iso = ''
            except Exception:
                req_fecha_display = '—'
                req_created_at_iso = ''

            data = {
                'requerimiento_id': pk,
                'requerimiento_code': req_data.get('code', f'#{pk}'),
                'requerimiento_asignado': req_data.get('assigned_to_name', ''),
                'requerimiento_operacion': req_data.get('operation_type_name', ''),
                'requerimiento_tipo': req_data.get('property_type_name', ''),
                'requerimiento_created_at': req_created_at_iso,
                'etapa_requerimiento': etapa_requerimiento,
                'ramas': ramas,
                'total_ramas': len(ramas),
            }

            return Response(data)

        except Exception as e:
            logger.error(f"Error al obtener pipeline matches para req #{pk}: {e}")
            return Response(
                {'error': f'Error al obtener matches: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['GET'])
    def pipeline_requerimientos(self, request, pk=None):
        """
        GET /api/matching/{property_id}/pipeline-requerimientos/

        Retorna el pipeline property→requirements.
        La propiedad es el nodo principal, cada requirement es una rama.
        Inverso lógico de pipeline_matches().

        NOTA: La API Propify NO soporta filtrar por propiedad en el endpoint
        requirement-matches. Solo soporta requirement_id. Por eso se obtienen
        todos los matches y se filtran localmente, con caché para performance.
        """
        try:
            from .propify_api import get_propify_client
            client = get_propify_client()

            # Validar que pk sea un entero positivo
            try:
                pk = int(pk)
            except (TypeError, ValueError):
                return Response({
                    'property_id': pk,
                    'property_code': '',
                    'property_title': '',
                    'property_district': '',
                    'property_price': None,
                    'property_currency_name': '',
                    'property_created_at': '',
                    'property_responsable': '',
                    'etapa_propiedad': {
                        'tipo': 'propiedad',
                        'label': f'#{pk}',
                        'icono': '🏠',
                        'fecha_display': '—',
                        'estado': 'ok',
                    },
                    'ramas': [],
                    'total_ramas': 0,
                })

            # Obtener datos de la propiedad
            prop_data = client.get_property_detail(pk)
            if not prop_data:
                return Response({
                    'property_id': pk,
                    'property_code': '',
                    'property_title': '',
                    'property_district': '',
                    'property_price': None,
                    'property_currency_name': '',
                    'property_created_at': '',
                    'property_responsable': '',
                    'etapa_propiedad': {
                        'tipo': 'propiedad',
                        'label': f'#{pk}',
                        'icono': '🏠',
                        'fecha_display': '—',
                        'estado': 'ok',
                    },
                    'ramas': [],
                    'total_ramas': 0,
                })

            # Obtener todos los matches y filtrar por property_id en Python
            # La API Propify NO soporta filter por property_id, solo por requirement_id.
            # Cacheamos para no repetir llamadas en cada pipeline click.
            all_matches = _get_cached_all_matches(client)
            matches = [m for m in all_matches if m.get('property') == pk]

            # Ordenar por score descendente
            matches.sort(key=lambda m: float(m.get('score', 0) or 0), reverse=True)

            # Cache de requerimientos para no repetir llamadas
            req_cache = {}

            def _get_req_info(req_id):
                if not req_id:
                    return {}
                if req_id not in req_cache:
                    try:
                        req_cache[req_id] = client.get_requirement_detail(req_id) or {}
                    except Exception:
                        req_cache[req_id] = {}
                return req_cache[req_id]

            ramas = []
            for m in matches:
                req_id = m.get('requirement')
                req_info = _get_req_info(req_id)

                ramas.append({
                    'match_id': m.get('id'),
                    'requirement_id': req_id,
                    'requirement_code': req_info.get('code', f'#{req_id}') if req_info else '',
                    'requirement_assigned': req_info.get('assigned_to_name', ''),
                    'requirement_operation': req_info.get('operation_type_name', ''),
                    'requirement_property_type': req_info.get('property_type_name', ''),
                    'requirement_created_at': req_info.get('created_at', ''),
                    'score': float(m.get('score', 0) or 0),
                    'computed_at': m.get('computed_at', ''),
                })

            # Construir etapa_propiedad
            from datetime import datetime
            prop_created_at = prop_data.get('created_at', '')
            try:
                if prop_created_at:
                    fecha_dt = datetime.fromisoformat(prop_created_at.replace('Z', '+00:00'))
                    fecha_display = fecha_dt.strftime('%d/%m')
                else:
                    fecha_display = '—'
            except Exception:
                fecha_display = '—'

            etapa_propiedad = {
                'tipo': 'propiedad',
                'label': prop_data.get('code', f'#{pk}'),
                'icono': '🏠',
                'fecha_display': fecha_display,
                'estado': 'ok',
            }

            data = {
                'property_id': pk,
                'property_code': prop_data.get('code', ''),
                'property_title': prop_data.get('title', ''),
                'property_district': prop_data.get('district_name', ''),
                'property_price': prop_data.get('price'),
                'property_currency_name': prop_data.get('currency_name', ''),
                'property_created_at': prop_created_at,
                'property_responsable': prop_data.get('created_by_name', ''),
                'etapa_propiedad': etapa_propiedad,
                'ramas': ramas,
                'total_ramas': len(ramas),
            }

            return Response(data)

        except Exception as e:
            logger.error(f"Error al obtener pipeline requerimientos para prop #{pk}: {e}")
            return Response(
                {'error': f'Error al obtener requerimientos: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['GET'])
    def guardados(self, request, pk=None):
        """
        GET /api/matching/{requerimiento_id}/guardados/
        
        Retorna los resultados de matching guardados (MatchResult) para un
        requerimiento, SIN re-ejecutar el motor. Solo los no eliminados
        con score >= 60%, ordenados por score descendente (máximo 3).
        Filtra por propiedad_id DISTINTA para evitar duplicados.
        Útil para el modal de calendario donde los scores deben coincidir
        exactamente con lo que muestran las tarjetas.
        """
        requerimiento = get_object_or_404(Requerimiento, pk=pk)
        
        # Obtener resultados ordenados por score
        todos = MatchResult.objects.filter(
            requerimiento=requerimiento,
            fase_eliminada__isnull=True,
            score_total__gte=60.0
        ).order_by('-score_total')
        
        # Filtrar hasta 3 propiedades DISTINTAS
        resultados = []
        prop_ids_vistos = set()
        for m in todos:
            if m.propiedad_id not in prop_ids_vistos and len(resultados) < 3:
                prop_ids_vistos.add(m.propiedad_id)
                resultados.append(m)
        
        return Response({
            'requerimiento': RequerimientoSimpleSerializer(requerimiento).data,
            'resultados': MatchResultSerializer(resultados, many=True).data,
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

    @action(detail=True, methods=['POST'])
    def actualizar_mensaje(self, request, pk=None):
        """
        POST /matching/api/propuesta/<id>/actualizar-mensaje/
        Actualiza el mensaje_enviado de una propuesta (después de generar links).
        """
        propuesta = get_object_or_404(PropuestaWhatsApp, pk=pk)
        mensaje = request.data.get('mensaje', '')
        if mensaje:
            propuesta.mensaje_enviado = mensaje
            propuesta.save(update_fields=['mensaje_enviado'])
        return Response({'status': 'ok'})

    @action(detail=True, methods=['GET'])
    def pipeline(self, request, pk=None):
        """
        GET /matching/api/propuesta/<id>/pipeline/

        Retorna el pipeline de vida para esta propuesta ESPECÍFICA.
        Cada propuesta tiene su propio pipeline independiente,
        con su propio match, su propio envio y su propia decision.
        """
        try:
            from .pipeline_requerimiento import obtener_pipeline_propuesta
            data = obtener_pipeline_propuesta(pk)
            return Response(data)
        except Exception as e:
            logger.error(f"Error al obtener pipeline de propuesta #{pk}: {e}")
            return Response(
                {'error': f'Error al obtener pipeline: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['GET'], permission_classes=[AllowAny])
    def verificar_enviado(self, request):
        """
        GET /matching/api/propuesta/verificar-enviado/?requerimiento_id=X&propiedad_id=Y
        Retorna si ya se envió una propuesta para este requerimiento+propiedad.
        """
        req_id = request.query_params.get('requerimiento_id')
        prop_id = request.query_params.get('propiedad_id')

        if not req_id or not prop_id:
            return Response({'error': 'requerimiento_id y propiedad_id requeridos'}, status=400)

        try:
            exists = PropuestaWhatsApp.objects.filter(
                requerimiento_id=int(req_id),
                propiedad_id=int(prop_id)
            ).exists()
            return Response({'ya_enviado': exists})
        except Exception as e:
            return Response({'error': str(e)}, status=500)

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
        
        # ── Filtro por agente ──
        agente_filter = self.request.GET.get('agente', '').strip()
        context['agente_filter'] = agente_filter
        
        # Obtener requerimientos paginados (solo los más recientes)
        requerimientos_qs = Requerimiento.objects.all().order_by('-fecha', '-hora')
        
        # Aplicar filtro por agente si está presente
        if agente_filter:
            requerimientos_qs = requerimientos_qs.filter(agente__icontains=agente_filter)
        
        # Paginación directa sobre QuerySet (más eficiente)
        paginator = Paginator(requerimientos_qs, 50)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # ── Agentes disponibles para el filtro ──
        import json
        from django.db.models import Count
        agentes_nombres = (
            Requerimiento.objects.exclude(condicion__in=['no_especificado', 'compartido'])
            .exclude(agente='')
            .values('agente')
            .annotate(total=Count('id'))
            .order_by('-total')
            .values_list('agente', flat=True)
        )[:100]
        context['agentes_json'] = json.dumps(list(agentes_nombres))
        
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


def _obtener_multiples_matches_calendario(limite=500, umbral_minimo=60.0):
    """
    Obtiene hasta 3 MatchResult por requerimiento con score >= umbral_minimo.
    Retorna un dict {req_id: {mejor_match_info, matches: [...]}}.
    """
    try:
        from .models import MatchResult
        from requerimientos.models import Requerimiento
        
        # Obtener todos los MatchResult no eliminados sobre el umbral
        todos = MatchResult.objects.filter(
            fase_eliminada__isnull=True,
            score_total__gte=umbral_minimo
        ).order_by('requerimiento_id', '-score_total')
        
        # Agrupar hasta 3 propiedades DISTINTAS por req_id (mejor score)
        resumen_por_req = {}
        for m in todos:
            rid = m.requerimiento_id
            if rid not in resumen_por_req:
                resumen_por_req[rid] = []
            # Solo agregar si es una propiedad DISTINTA a las ya agregadas
            prop_ids_existentes = {x['propiedad_id'] for x in resumen_por_req[rid]}
            if m.propiedad_id not in prop_ids_existentes and len(resumen_por_req[rid]) < 3:
                match_info = {
                    'score_total': float(m.score_total),
                    'propiedad_id': m.propiedad_id,
                }
                resumen_por_req[rid].append(match_info)
        
        # Construir resultado final: un dict por req_id con mejores scores
        resultado = {}
        for rid, matches in resumen_por_req.items():
            mejor = matches[0]
            try:
                req = Requerimiento.objects.get(id=rid)
                req_nombre = str(req)
            except Requerimiento.DoesNotExist:
                req_nombre = f'Requerimiento #{rid}'
            
            resultado[rid] = {
                'requerimiento_id': rid,
                'requerimiento_nombre': req_nombre,
                'porcentaje_match': mejor['score_total'],
                'total_compatibles': len(matches),
                'matches': matches,
            }
        
        # Ordenar por mejor score, limitar
        items = sorted(resultado.values(), key=lambda x: x['porcentaje_match'], reverse=True)
        items = items[:limite]
        
        # Reconstruir dict ordenado
        return {item['requerimiento_id']: item for item in items}
        
    except Exception as e:
        logger.warning(f"No se pudieron obtener matches multiples para calendario: {e}")
        return {}


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
        
        # ── Totals para stats bar ──
        context['total_requerimientos'] = Requerimiento.objects.exclude(
            condicion__in=['no_especificado', 'compartido']
        ).count()
        context['total_propiedades'] = PropifaiProperty.objects.count()
        
        # ── Agentes para filtro autocomplete ──
        from django.db.models import Count
        agentes_nombres_raw = (
            Requerimiento.objects.exclude(condicion__in=['no_especificado', 'compartido'])
            .exclude(agente='')
            .values('agente')
            .annotate(total=Count('id'))
            .order_by('-total')
            .values_list('agente', flat=True)
        )[:100]
        # Limpiar nombres (quitar saltos de línea y espacios extra)
        agentes_limpios = []
        for nombre in agentes_nombres_raw:
            nombre_limpio = (nombre or '').replace('\n', ' ').replace('\r', ' ').strip()
            if nombre_limpio and nombre_limpio not in agentes_limpios:
                agentes_limpios.append(nombre_limpio)
        context['agentes_json'] = json.dumps(agentes_limpios)
        
        # ── Tipos de propiedad para filtros ──
        from requerimientos.models import TipoPropiedadChoices
        tipos_propiedad = [
            {'key': choice.value, 'label': choice.label}
            for choice in TipoPropiedadChoices
            if choice.value != 'no_especificado'
        ]
        context['tipos_propiedad'] = tipos_propiedad
        context['tipos_propiedad_json'] = json.dumps(tipos_propiedad)
        
        # reqs_del_mes_json por defecto (vacío para vistas que no son month)
        context['reqs_del_mes_json'] = json.dumps([])
        
        # Obtener resumen de matching con múltiples matches por requerimiento
        # Hasta 3 matches por req con score >= 60%
        resumen_por_req = _obtener_multiples_matches_calendario()
        
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
            
            # ── reqs_por_fecha: contar TOTAL de requerimientos y cuántos tienen match ──
            # Query 1: Obtener TODOS los requerimientos del mes (no solo los que tienen match)
            # para contar el total real por día
            primer_dia = date(year, month, 1)
            if month == 12:
                ultimo_dia = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                ultimo_dia = date(year, month + 1, 1) - timedelta(days=1)
            
            todos_reqs_mes = Requerimiento.objects.filter(
                fecha__gte=primer_dia,
                fecha__lte=ultimo_dia
            ).exclude(
                condicion__in=condicion_excluir
            ).values('id', 'fecha')
            
            # IDs de requerimientos que tienen al menos un match (score >= 60%)
            req_ids_con_match = set(resumen_por_req.keys())
            
            reqs_por_fecha = {}
            for r in todos_reqs_mes:
                if not r['fecha']:
                    continue
                fecha_key = r['fecha'].isoformat()
                if fecha_key not in reqs_por_fecha:
                    reqs_por_fecha[fecha_key] = {'total': 0, 'con_match': 0}
                reqs_por_fecha[fecha_key]['total'] += 1
                if r['id'] in req_ids_con_match:
                    reqs_por_fecha[fecha_key]['con_match'] += 1
            
            # ── Datos de reqs del mes para filtros client-side ──
            reqs_del_mes_qs = Requerimiento.objects.filter(
                fecha__gte=primer_dia,
                fecha__lte=ultimo_dia
            ).exclude(
                condicion__in=condicion_excluir
            ).values('id', 'fecha', 'agente', 'tipo_propiedad')
            
            reqs_del_mes_list = []
            for r in reqs_del_mes_qs:
                # Limpiar el nombre del agente (quitando saltos de línea)
                agente_limpio = (r['agente'] or '').replace('\n', ' ').replace('\r', ' ').strip()
                reqs_del_mes_list.append({
                    'id': r['id'],
                    'fecha': r['fecha'].isoformat() if r['fecha'] else None,
                    'agente': agente_limpio,
                    'tipo_propiedad': r['tipo_propiedad'] or '',
                    'has_match': r['id'] in req_ids_con_match,
                })
            
            context['month_days'] = month_days
            context['reqs_por_fecha_json'] = json.dumps(reqs_por_fecha)
            context['reqs_del_mes_json'] = json.dumps(reqs_del_mes_list)
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
                    matches_del_req = info.get('matches', []) if info else []
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
                        'porcentaje_match': info.get('porcentaje_match', 0) if info else 0,
                        'mejor_propiedad_codigo': matches_del_req[0].get('propiedad_code') if matches_del_req else None,
                        'mejor_propiedad_precio': matches_del_req[0].get('propiedad_price') if matches_del_req else None,
                        'mejor_propiedad_moneda_id': matches_del_req[0].get('propiedad_currency_id') if matches_del_req else None,
                        'matches': matches_del_req,  # NUEVO: lista completa de hasta 3 matches
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


# ===================================================================
# Vistas para tracking de respuestas WhatsApp (links en mensajes)
# ===================================================================

def responder_propuesta(request, pk):
    """
    GET /matching/propuesta/<pk>/responder/?decision=interesado|rechazado
    Actualiza el status de una propuesta WhatsApp y redirige a la página de respuesta.
    """
    propuesta = get_object_or_404(PropuestaWhatsApp, pk=pk)
    decision = request.GET.get('decision', '').strip().lower()

    if decision == 'interesado':
        propuesta.status = PropuestaWhatsApp.Status.INTERESADO
    elif decision == 'rechazado':
        propuesta.status = PropuestaWhatsApp.Status.RECHAZADO
    else:
        from django.http import HttpResponseBadRequest
        return HttpResponseBadRequest("Decisión no válida. Use: decision=interesado o decision=rechazado")

    from django.utils import timezone
    propuesta.respondido_en = timezone.now()
    propuesta.save(update_fields=['status', 'respondido_en'])

    from django.shortcuts import redirect
    return redirect(f'/matching/propuesta/respuesta/?pk={pk}&decision={decision}')


def pagina_respuesta(request):
    """
    GET /matching/propuesta/respuesta/?pk=<pk>&decision=interesado|rechazado
    Muestra una página de confirmación según la decisión del agente.
    """
    pk = request.GET.get('pk')
    decision = request.GET.get('decision', '')
    if not pk:
        from django.http import HttpResponseBadRequest
        return HttpResponseBadRequest("Falta parámetro pk")

    propuesta = get_object_or_404(PropuestaWhatsApp, pk=pk)

    from django.shortcuts import render
    return render(request, 'matching/respuesta_propuesta.html', {
        'propuesta': propuesta,
        'decision': decision,
    })


from django.views.generic import TemplateView
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from collections import defaultdict


class PropuestasDashboardView(TemplateView):
    """
    Dashboard de propuestas WhatsApp con estadísticas y gráficos.
    Muestra métricas de hoy, semana, mes y evolución temporal.
    """
    template_name = 'matching/propuestas_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        import json

        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)

        # ── Helper: obtener counts por status ──
        def _contar(queryset):
            return {
                'enviadas': queryset.filter(status=PropuestaWhatsApp.Status.ENVIADA).count(),
                'respondidas': queryset.filter(
                    Q(status=PropuestaWhatsApp.Status.RESPONDIDA) |
                    Q(status=PropuestaWhatsApp.Status.INTERESADO) |
                    Q(status=PropuestaWhatsApp.Status.RECHAZADO) |
                    Q(status=PropuestaWhatsApp.Status.NO_INTERESADO) |
                    Q(status=PropuestaWhatsApp.Status.VISITA_AGENDADA) |
                    Q(status=PropuestaWhatsApp.Status.CERRADA)
                ).count(),
                'aceptadas': queryset.filter(
                    Q(status=PropuestaWhatsApp.Status.INTERESADO) |
                    Q(status=PropuestaWhatsApp.Status.VISITA_AGENDADA) |
                    Q(status=PropuestaWhatsApp.Status.CERRADA)
                ).count(),
                'rechazadas': queryset.filter(
                    Q(status=PropuestaWhatsApp.Status.RECHAZADO) |
                    Q(status=PropuestaWhatsApp.Status.NO_INTERESADO)
                ).count(),
                'pendientes': queryset.filter(status=PropuestaWhatsApp.Status.ENVIADA).count(),
            }

        def _calc_tasas(stats_dict, total):
            if total == 0:
                stats_dict['tasa_respuesta'] = 0
                stats_dict['tasa_aceptacion'] = 0
                stats_dict['tasa_rechazo'] = 0
            else:
                stats_dict['tasa_respuesta'] = round(stats_dict['respondidas'] / total * 100, 1)
                stats_dict['tasa_aceptacion'] = round(stats_dict['aceptadas'] / total * 100, 1)
                stats_dict['tasa_rechazo'] = round(stats_dict['rechazadas'] / total * 100, 1)
            return stats_dict

        # ── Stats ──
        qs_hoy = PropuestaWhatsApp.objects.filter(enviado_en__date=today)
        stats_hoy = _contar(qs_hoy)
        stats_hoy['total'] = qs_hoy.count()
        stats_hoy = _calc_tasas(stats_hoy, stats_hoy['total'])

        qs_semana = PropuestaWhatsApp.objects.filter(enviado_en__date__gte=week_ago)
        stats_semana = _contar(qs_semana)
        stats_semana['total'] = qs_semana.count()
        stats_semana = _calc_tasas(stats_semana, stats_semana['total'])

        qs_mes = PropuestaWhatsApp.objects.filter(enviado_en__date__gte=month_ago)
        stats_mes = _contar(qs_mes)
        stats_mes['total'] = qs_mes.count()
        stats_mes = _calc_tasas(stats_mes, stats_mes['total'])

        # ── Datos para charts ──
        props_por_dia = (
            PropuestaWhatsApp.objects
            .filter(enviado_en__date__gte=month_ago)
            .annotate(dia=TruncDate('enviado_en'))
            .values('dia', 'status')
            .annotate(total=Count('id'))
            .order_by('dia')
        )

        charts = self._generar_charts(props_por_dia, today, week_ago, month_ago)
        context['stats_hoy'] = stats_hoy
        context['stats_semana'] = stats_semana
        context['stats_mes'] = stats_mes
        context['charts'] = charts

        # ── Últimas 20 propuestas ──
        ultimas = PropuestaWhatsApp.objects.select_related('requerimiento').order_by('-enviado_en')[:20]
        context['ultimas_propuestas'] = ultimas
        return context

    def _generar_charts(self, props_por_dia, today, week_ago, month_ago):
        """Genera gráficos matplotlib y retorna dict con base64."""
        from collections import defaultdict
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            import numpy as np
        except ImportError:
            return {'error': 'matplotlib no disponible'}
        
        enviadas_por_dia = defaultdict(int)
        aceptadas_por_dia = defaultdict(int)
        rechazadas_por_dia = defaultdict(int)

        for item in props_por_dia:
            dia = item['dia']
            status = item['status']
            total = item['total']
            if status == PropuestaWhatsApp.Status.ENVIADA:
                enviadas_por_dia[dia] += total
            elif status in (PropuestaWhatsApp.Status.INTERESADO,
                            PropuestaWhatsApp.Status.VISITA_AGENDADA,
                            PropuestaWhatsApp.Status.CERRADA):
                aceptadas_por_dia[dia] += total
            elif status in (PropuestaWhatsApp.Status.RECHAZADO,
                            PropuestaWhatsApp.Status.NO_INTERESADO):
                rechazadas_por_dia[dia] += total

        plt.style.use('dark_background')
        COLOR_BG = '#0d1117'
        COLOR_TEXTO = '#e6edf3'
        COLOR_AZUL = '#58a6ff'
        COLOR_VERDE = '#3fb950'
        COLOR_ROJO = '#f85149'
        COLOR_NARANJA = '#d29922'

        charts = {}

        def fig_to_b64(fig):
            import io, base64
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=100, bbox_inches='tight',
                        facecolor=COLOR_BG)
            plt.close(fig)
            buf.seek(0)
            return f"data:image/png;base64,{base64.b64encode(buf.read()).decode('utf-8')}"

        # ── Chart 1: Evolución semanal (acumulativa) ──
        dias_semana = [today - timedelta(days=i) for i in range(6, -1, -1)]
        dias_labels = [d.strftime('%d/%m') for d in dias_semana]
        # Per-day values
        sem_env_raw = [enviadas_por_dia.get(d, 0) for d in dias_semana]
        sem_acep_raw = [aceptadas_por_dia.get(d, 0) for d in dias_semana]
        sem_rech_raw = [rechazadas_por_dia.get(d, 0) for d in dias_semana]
        # Acumulativos (running total)
        def acumular(arr):
            acc = 0
            result = []
            for v in arr:
                acc += v
                result.append(acc)
            return result
        sem_env = acumular(sem_env_raw)
        sem_acep = acumular(sem_acep_raw)
        sem_rech = acumular(sem_rech_raw)

        fig, ax = plt.subplots(figsize=(7, 3.5))
        ax.set_facecolor(COLOR_BG)
        fig.patch.set_facecolor(COLOR_BG)
        ax.plot(dias_labels, sem_env, color=COLOR_AZUL, marker='o', linewidth=2, label='Enviadas')
        ax.plot(dias_labels, sem_acep, color=COLOR_VERDE, marker='s', linewidth=2, label='Aceptadas')
        ax.plot(dias_labels, sem_rech, color=COLOR_ROJO, marker='x', linewidth=2, label='Rechazadas')
        ax.set_title('Evolución Semanal (Acumulado)', color=COLOR_TEXTO, fontsize=13, fontweight='bold')
        ax.set_ylabel('Propuestas', color=COLOR_TEXTO)
        ax.tick_params(colors=COLOR_TEXTO, labelsize=9)
        ax.legend(loc='upper left', facecolor='#161b22', edgecolor='#30363d', labelcolor=COLOR_TEXTO)
        ax.grid(True, alpha=0.15, color='#8b949e')
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        charts['evolucion_semanal'] = fig_to_b64(fig)

        # ── Chart 2: Evolución mensual (acumulativa) ──
        todos_dias = [month_ago + timedelta(days=i) for i in range(31)]
        intervalos, env_agrup, acep_agrup, rech_agrup = [], [], [], []
        env_acum, acep_acum, rech_acum = 0, 0, 0
        for i in range(0, 31, 3):
            grupo = todos_dias[i:min(i+3, 31)]
            intervalos.append(grupo[0].strftime('%d/%m'))
            env_acum += sum(enviadas_por_dia.get(d, 0) for d in grupo)
            acep_acum += sum(aceptadas_por_dia.get(d, 0) for d in grupo)
            rech_acum += sum(rechazadas_por_dia.get(d, 0) for d in grupo)
            env_agrup.append(env_acum)
            acep_agrup.append(acep_acum)
            rech_agrup.append(rech_acum)

        fig, ax = plt.subplots(figsize=(7, 3.5))
        ax.set_facecolor(COLOR_BG)
        fig.patch.set_facecolor(COLOR_BG)
        ax.plot(intervalos, env_agrup, color=COLOR_AZUL, marker='o', linewidth=2, label='Enviadas')
        ax.plot(intervalos, acep_agrup, color=COLOR_VERDE, marker='s', linewidth=2, label='Aceptadas')
        ax.plot(intervalos, rech_agrup, color=COLOR_ROJO, marker='x', linewidth=2, label='Rechazadas')
        ax.set_title('Evolución Mensual (Acumulado)', color=COLOR_TEXTO, fontsize=13, fontweight='bold')
        ax.set_ylabel('Propuestas', color=COLOR_TEXTO)
        ax.tick_params(colors=COLOR_TEXTO, labelsize=8)
        ax.legend(loc='upper left', facecolor='#161b22', edgecolor='#30363d', labelcolor=COLOR_TEXTO)
        ax.grid(True, alpha=0.15, color='#8b949e')
        plt.xticks(rotation=45, ha='right', fontsize=8)
        plt.tight_layout()
        charts['evolucion_mensual'] = fig_to_b64(fig)

        # ── Chart 3: Barras semanales ──
        fig, ax = plt.subplots(figsize=(7, 3.5))
        ax.set_facecolor(COLOR_BG)
        fig.patch.set_facecolor(COLOR_BG)
        x = np.arange(len(dias_labels))
        width = 0.25
        ax.bar(x - width, sem_env, width, color=COLOR_AZUL, label='Enviadas', alpha=0.9)
        ax.bar(x, sem_acep, width, color=COLOR_VERDE, label='Aceptadas', alpha=0.9)
        ax.bar(x + width, sem_rech, width, color=COLOR_ROJO, label='Rechazadas', alpha=0.9)
        ax.set_title('Propuestas por Día (Semana)', color=COLOR_TEXTO, fontsize=13, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(dias_labels, fontsize=8)
        ax.set_ylabel('Cantidad', color=COLOR_TEXTO)
        ax.tick_params(colors=COLOR_TEXTO, labelsize=9)
        ax.legend(loc='upper left', facecolor='#161b22', edgecolor='#30363d', labelcolor=COLOR_TEXTO)
        ax.grid(True, alpha=0.15, color='#8b949e', axis='y')
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        charts['barras_semana'] = fig_to_b64(fig)

        # ── Chart 4: Distribución de status ──
        status_counts = (
            PropuestaWhatsApp.objects
            .values('status')
            .annotate(total=Count('id'))
            .order_by('-total')
        )
        labels = []
        sizes = []
        colors_list = []
        color_map = {
            'enviada': COLOR_AZUL,
            'respondida': COLOR_NARANJA,
            'interesado': COLOR_VERDE,
            'visita_agendada': '#56d36e',
            'cerrada': '#1a7f37',
            'rechazado': COLOR_ROJO,
            'no_interesado': '#ff7b72',
        }
        status_names = dict(PropuestaWhatsApp.Status.choices)
        for item in status_counts:
            labels.append(status_names.get(item['status'], item['status']))
            sizes.append(item['total'])
            colors_list.append(color_map.get(item['status'], '#8b949e'))

        fig, ax = plt.subplots(figsize=(5, 4))
        ax.set_facecolor(COLOR_BG)
        fig.patch.set_facecolor(COLOR_BG)
        wedges, texts, autotexts = ax.pie(
            sizes, labels=None, autopct='%1.0f%%',
            colors=colors_list, startangle=90,
            wedgeprops={'linewidth': 1, 'edgecolor': COLOR_BG},
        )
        for autotext in autotexts:
            autotext.set_color('#ffffff')
            autotext.set_fontweight('bold')
        ax.legend(wedges, [f'{l} ({s})' for l, s in zip(labels, sizes)],
                  loc='center left', bbox_to_anchor=(1, 0.5),
                  facecolor='#161b22', edgecolor='#30363d',
                  labelcolor=COLOR_TEXTO, fontsize=8)
        ax.set_title('Distribución de Status', color=COLOR_TEXTO, fontsize=13, fontweight='bold')
        plt.tight_layout()
        charts['distribucion_status'] = fig_to_b64(fig)

        return charts


class MatchesDashboardView(TemplateView):
    """
    Dashboard CRM de Matches de Propify.
    Consume la API externa de Propify (api.propify.pe) para mostrar
    los matches del sistema Propify.
    """
    template_name = 'matching/matches_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.utils import timezone
        from datetime import timedelta
        import json

        today = timezone.now().date()

        # ── Par�metros de filtro ──
        view_mode = self.request.GET.get('view', 'all')
        filter_date = self.request.GET.get('date', '')
        requirement_id = self.request.GET.get('requirement_id', '')
        assigned_to = self.request.GET.get('assigned_to', '')
        page = self.request.GET.get('page', 1)

        # ── Cliente API Propify ──
        from .propify_api import get_propify_client
        client = get_propify_client()

        # ── Obtener requirements (TODAS las p�ginas) ──
        # Debe ir PRIMERO para poder construir el autocomplete y filtros
        req_map = {}
        page_req = 1
        while True:
            reqs_data = client.get_requirements(page=page_req, page_size=200)
            if not reqs_data or not reqs_data.get('results'):
                break
            for r in reqs_data['results']:
                req_map[r['id']] = r
            if not reqs_data.get('next'):
                break
            page_req += 1

        # ── Lista de asignados �nicos para autocomplete ──
        unique_assigned = sorted(set(
            r.get('assigned_to_name', '') for r in req_map.values()
            if r.get('assigned_to_name')
        ), key=str.lower)

        # ── Construir filtros y obtener matches ──
        api_filters = {}
        if requirement_id:
            api_filters['requirement_id'] = requirement_id
        if filter_date:
            if view_mode == 'day' or view_mode == 'all':
                # view='all' con fecha → filtrar por día específico
                api_filters['created_at__date'] = filter_date
            elif view_mode == 'week':
                try:
                    from datetime import datetime as dt_mod
                    d = dt_mod.strptime(filter_date, '%Y-%m-%d').date()
                    week_start = d - timedelta(days=d.weekday())
                    week_end = week_start + timedelta(days=6)
                    api_filters['created_at__date__gte'] = week_start.isoformat()
                    api_filters['created_at__date__lte'] = week_end.isoformat()
                except ValueError:
                    pass
            elif view_mode == 'month':
                try:
                    year, month_parts = filter_date.split('-')
                    api_filters['created_at__year'] = year
                    api_filters['created_at__month'] = month_parts
                except ValueError:
                    pass

        matches_data = client.get_matches(page=int(page), page_size=50, **api_filters)

        # ── Procesar datos ──
        matches = matches_data.get('results', []) if matches_data else []
        total_count = matches_data.get('count', 0) if matches_data else 0

        # Enriquecer cada match con datos del requirement
        # y filtrar por asignado (server-side ya que la API no soporta filtro por assigned_to)
        if assigned_to:
            filtered = []
            for m in matches:
                req_info = req_map.get(m.get('requirement'))
                if req_info and req_info.get('assigned_to_name', '').lower() == assigned_to.lower():
                    filtered.append(m)
            matches = filtered
            total_count = len(matches)

        # Enriquecer cada match con datos del requirement
        for m in matches:
            req_info = req_map.get(m.get('requirement'))
            if req_info:
                m['req_code'] = req_info.get('code', '')
                m['req_assigned'] = req_info.get('assigned_to_name', '')
                m['req_operation'] = req_info.get('operation_type_name', '')
                m['req_property_type'] = req_info.get('property_type_name', '')
            else:
                m['req_code'] = ''
                m['req_assigned'] = ''
                m['req_operation'] = ''
                m['req_property_type'] = ''

        # ── Agrupar matches por requirement_id ──
        # Cada requerimiento aparece UNA sola vez con todas sus propiedades
        req_groups = {}
        for m in matches:
            req_id = m.get('requirement')
            if req_id not in req_groups:
                req_groups[req_id] = {
                    'requirement_id': req_id,
                    'req_code': m.get('req_code', ''),
                    'req_assigned': m.get('req_assigned', ''),
                    'req_operation': m.get('req_operation', ''),
                    'req_property_type': m.get('req_property_type', ''),
                    'matches': [],
                    'total_matches': 0,
                    'best_score': 0.0,
                    'first_match': m,
                }
            req_groups[req_id]['matches'].append(m)
            req_groups[req_id]['total_matches'] = len(req_groups[req_id]['matches'])
            score = float(m.get('score', 0) or 0)
            if score > req_groups[req_id]['best_score']:
                req_groups[req_id]['best_score'] = score
                req_groups[req_id]['first_match'] = m

        grouped_matches = sorted(
            req_groups.values(),
            key=lambda g: g['requirement_id'] or 0,
            reverse=True
        )
        total_groups = len(grouped_matches)

        context['total_matches'] = total_count
        context['total_groups'] = total_groups
        context['view_mode'] = view_mode
        context['filter_date'] = filter_date
        context['requirement_id'] = requirement_id
        context['assigned_to'] = assigned_to
        context['assigned_list_json'] = json.dumps(unique_assigned)
        context['grouped_matches'] = grouped_matches
        context['current_page'] = int(page)
        context['total_pages'] = -(-total_count // 50) if total_count else 0
        context['has_next'] = matches_data.get('next') is not None if matches_data else False
        context['has_prev'] = matches_data.get('previous') is not None if matches_data else False

        return context


class PropiedadesMatchesDashboardView(TemplateView):
    """
    Dashboard de Matches por Propiedad (Property-Centric).
    Inverso de MatchesDashboardView.
    Consume la API externa de Propify (api.propify.pe) para mostrar
    los matches agrupados por propiedad en vez de por requerimiento.
    Cada fila = una propiedad, con sus requerimientos matchados como sub-items.
    """
    template_name = 'matching/matches_por_propiedad.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.utils import timezone
        from datetime import timedelta
        import json

        today = timezone.now().date()

        # ── Par�metros de filtro ──
        view_mode = self.request.GET.get('view', 'all')
        filter_date = self.request.GET.get('date', '')
        property_code = self.request.GET.get('property_code', '')
        assigned_to = self.request.GET.get('assigned_to', '')
        page = self.request.GET.get('page', 1)

        # ── Cliente API Propify ──
        from .propify_api import get_propify_client
        client = get_propify_client()

        # ── Obtener requirements para autocomplete y filtros ──
        req_map = {}
        page_req = 1
        while True:
            reqs_data = client.get_requirements(page=page_req, page_size=200)
            if not reqs_data or not reqs_data.get('results'):
                break
            for r in reqs_data['results']:
                req_map[r['id']] = r
            if not reqs_data.get('next'):
                break
            page_req += 1

        # ── Lista de asignados únicos para autocomplete ──
        unique_assigned = sorted(set(
            r.get('assigned_to_name', '') for r in req_map.values()
            if r.get('assigned_to_name')
        ), key=str.lower)

        # ── Obtener IDs de propiedades desde /api/properties/properties/ ──
        all_props = []
        page_props = 1
        while True:
            props_data = client.get_properties_list(page=page_props, page_size=200)
            if not props_data or not props_data.get('results'):
                break
            all_props.extend(props_data['results'])
            if not props_data.get('next'):
                break
            page_props += 1

        # ── Obtener todos los matches ──
        all_matches = _get_cached_all_matches(client)
        total_match_count = len(all_matches)

        for m in all_matches:
            req_info = req_map.get(m.get('requirement'))
            if req_info:
                m['req_code'] = req_info.get('code', '')
                m['req_assigned'] = req_info.get('assigned_to_name', '')
                m['req_operation'] = req_info.get('operation_type_name', '')
                m['req_property_type'] = req_info.get('property_type_name', '')

        match_index = {}
        for m in all_matches:
            pid = m.get('property')
            if pid not in match_index:
                match_index[pid] = []
            match_index[pid].append(m)

        # ── Filtrar solo Disponibles ──
        available_props = [p for p in all_props if p.get('property_status_name') == 'Disponible']

        # Obtener full-detail SOLO para propiedades de la página actual (máximo 50)
        page = int(page)
        start_idx = (page - 1) * 50
        end_idx = start_idx + 50
        page_props = available_props[start_idx:end_idx]

        full_detail_cache = {}
        MEDIA_BASE = "https://propifymedia01.blob.core.windows.net/media"
        prop_images = {}

        for prop in page_props:
            pid = prop.get('id')
            try:
                detail = client.get_property_full_detail(pid)
                if detail:
                    full_detail_cache[pid] = detail
                    # Extraer primera imagen del full-detail
                    media_list = detail.get('media', [])
                    for m_item in media_list:
                        if m_item.get('media_type') == 'image' and pid not in prop_images:
                            img_url = m_item.get('file', '')
                            if img_url:
                                prop_images[pid] = img_url
            except Exception:
                pass

        # ── Construir lista ──
        prop_list = []
        for p in available_props:
            pid = p.get('id')
            detail = full_detail_cache.get(pid, {})
            prop_matches = match_index.get(pid, [])
            best_score = max(
                (float(m.get('score', 0) or 0) for m in prop_matches),
                default=0.0
            )
            # Distrito desde full-detail
            district_val = detail.get('district', '') if detail else ''
            if isinstance(district_val, dict):
                district_name = district_val.get('name', '') or ''
            else:
                district_name = str(district_val) if district_val else p.get('district', '')
            # Precio y moneda desde full-detail
            prop_price = detail.get('price') if detail else p.get('price')
            currency_code = detail.get('currency_code', '') if detail else p.get('currency_code', '')
            currency_symbol = '$' if currency_code and currency_code.upper() == 'USD' else 'S/'

            prop_list.append({
                'property_id': pid,
                'property_code': p.get('code', ''),
                'property_title': p.get('title', ''),
                'property_district_name': district_name,
                'property_price': prop_price,
                'property_price_display': f"{currency_symbol} {float(prop_price):,.0f}" if prop_price else '---',
                'property_currency_name': currency_code,
                'property_image_url': prop_images.get(pid, ''),
                'requirements': prop_matches,
                'total_requirements': len(prop_matches),
                'best_score': best_score,
                'first_match': prop_matches[0] if prop_matches else None,
            })

        # Ordenar por best_score descendente
        prop_list.sort(key=lambda g: g['best_score'], reverse=True)

        # Total de propiedades únicas (para paginación correcta)
        total_unique_props = len(available_props)
        props_per_page = 50
        total_pages = -(-total_unique_props // props_per_page) if total_unique_props else 0

        grouped_propiedades = prop_list  # ya son solo las de la página actual

        has_next = page < total_pages
        has_prev = page > 1

        # ── Datos de pipeline embebidos (TODAS las propiedades, no solo página actual) ──
        pipeline_data = {}
        for pid, reqs_list in match_index.items():
            reqs = []
            for m in reqs_list:
                reqs.append({
                    'requirement_id': m.get('requirement'),
                    'requirement_code': m.get('req_code', ''),
                    'requirement_assigned': m.get('req_assigned', ''),
                    'requirement_operation': m.get('req_operation', ''),
                    'requirement_property_type': m.get('req_property_type', ''),
                    'score': float(m.get('score', 0) or 0),
                    'computed_at': m.get('computed_at', ''),
                })
            reqs.sort(key=lambda r: r['score'], reverse=True)
            pipeline_data[str(pid)] = {
                'property_code': '',
                'property_title': '',
                'property_district': '',
                'property_created_at': '',
                'ramas': reqs,
                'total_ramas': len(reqs),
            }

        context['total_matches'] = total_match_count
        context['total_groups'] = total_unique_props
        context['view_mode'] = view_mode
        context['filter_date'] = filter_date
        context['property_code'] = property_code
        context['assigned_to'] = assigned_to
        context['assigned_list_json'] = json.dumps(unique_assigned)
        context['grouped_propiedades'] = grouped_propiedades
        context['pipeline_data_json'] = json.dumps(pipeline_data)
        context['current_page'] = page
        context['total_pages'] = total_pages
        context['has_next'] = has_next
        context['has_prev'] = has_prev

        return context
