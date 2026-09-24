import logging
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

from django.shortcuts import get_object_or_404
from django.db import connections, transaction
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import viewsets, status, generics
from rest_framework.authentication import BaseAuthentication, SessionAuthentication
from rest_framework.decorators import action
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAuthenticated
from rest_framework.views import APIView

from captura.azure_storage import generate_read_sas_url

from .models import ZonaValor, PropiedadValoracion, EstadisticaZona, HistorialPrecioZona
from .serializers import (
    ZonaValorSerializer, PropiedadValoracionSerializer,
    EstadisticaZonaSerializer, HistorialPrecioZonaSerializer,
    EstimacionRequestSerializer, EstimacionResponseSerializer,
    PuntoEnPoligonoRequestSerializer, ZonaEstadisticasSerializer
)
from .services import (
    calcular_precio_m2_zona, estimar_precio_propiedad,
    punto_en_poligono, calcular_area_poligono,
    actualizar_estadisticas_zona, encontrar_zona_por_punto
)


logger = logging.getLogger(__name__)
PROPIFY_MEDIA_BASE_URL = 'https://propifymedia01.blob.core.windows.net/media'
PEN_TO_USD_EXCHANGE_RATE = Decimal('3.44')


class PrometeoSessionAuthentication(BaseAuthentication):
    """Autentica con la sesión propia de Prometeo (request.current_user).

    El sistema no usa la sesión de Django auth (request.user): el login guarda
    el usuario en ``session['user_id']`` y el middleware de ``intelligence`` lo
    deja en ``request.current_user``. Sin esta clase, DRF devuelve 401
    'credentials not provided' en escrituras aunque el usuario esté logueado.
    """
    def authenticate(self, request):
        user = getattr(request, 'current_user', None)
        if user is None:
            return None
        if not getattr(user, 'is_active', False):
            raise AuthenticationFailed('Usuario inactivo.')
        SessionAuthentication().enforce_csrf(request)
        return (user, None)

    def authenticate_header(self, request):
        return 'Session'


class ZonaValorViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar zonas de valor (polígonos) con jerarquía.
    """
    serializer_class = ZonaValorSerializer
    authentication_classes = [PrometeoSessionAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    def get_queryset(self):
        """Filtrar zonas por nivel, jerarquía y otros parámetros."""
        queryset = ZonaValor.objects.filter(activo=True)
        
        # Filtrar por nivel jerárquico
        nivel = self.request.query_params.get('nivel')
        if nivel:
            queryset = queryset.filter(nivel=nivel)
        
        # Filtrar por zona padre (jerarquía)
        parent_id = self.request.query_params.get('parent_id')
        if parent_id:
            queryset = queryset.filter(parent_id=parent_id)
        
        # Filtrar por zona raíz (sin padre)
        raiz = self.request.query_params.get('raiz')
        if raiz and raiz.lower() == 'true':
            queryset = queryset.filter(parent__isnull=True)
        
        # Filtrar por código
        codigo = self.request.query_params.get('codigo')
        if codigo:
            queryset = queryset.filter(codigo__icontains=codigo)
        
        # Filtrar por nombre
        nombre = self.request.query_params.get('nombre')
        if nombre:
            queryset = queryset.filter(nombre_zona__icontains=nombre)
        
        return queryset
    
    @transaction.atomic
    def perform_create(self, serializer):
        """Persist the zone and calculate only values derivable from its polygon."""
        zona = serializer.save()

        area = calcular_area_poligono(zona.coordenadas or [])
        if area:
            zona.area_total = area
            zona.save(update_fields=['area_total', 'fecha_actualizacion'])

        logger.info(
            'Zona de valor creada: id=%s nivel=%s vertices=%s area_m2=%s usuario=%s',
            zona.id,
            zona.nivel,
            len(zona.coordenadas or []),
            zona.area_total,
            getattr(getattr(self.request, 'current_user', None), 'username', None),
        )
    
    @action(detail=True, methods=['get'])
    def estadisticas(self, request, pk=None):
        """Obtener estadísticas detalladas de una zona."""
        zona = self.get_object()
        
        estadisticas_por_tipo = EstadisticaZona.objects.filter(zona=zona)
        historial_precios = HistorialPrecioZona.objects.filter(zona=zona).order_by('-fecha_registro')[:12]
        propiedades_recientes = PropiedadValoracion.objects.filter(zona=zona).order_by('-fecha_calculo')[:10]
        
        data = {
            'zona': ZonaValorSerializer(zona).data,
            'estadisticas_por_tipo': EstadisticaZonaSerializer(estadisticas_por_tipo, many=True).data,
            'historial_precios': HistorialPrecioZonaSerializer(historial_precios, many=True).data,
            'propiedades_recientes': PropiedadValoracionSerializer(propiedades_recientes, many=True).data,
        }
        
        serializer = ZonaEstadisticasSerializer(data)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def actualizar_estadisticas(self, request, pk=None):
        """Forzar actualización de estadísticas de la zona."""
        zona = self.get_object()
        actualizar_estadisticas_zona(zona)
        return Response({'status': 'Estadísticas actualizadas', 'zona': zona.nombre_zona})
    
    @action(detail=True, methods=['get'])
    def jerarquia(self, request, pk=None):
        """Obtener la jerarquía completa de una zona (padres e hijos)."""
        zona = self.get_object()
        
        # Obtener ancestros (padres hacia arriba)
        ancestros = []
        current = zona.parent
        while current:
            ancestros.insert(0, ZonaValorSerializer(current).data)
            current = current.parent
        
        # Obtener descendientes directos (hijos)
        hijos = ZonaValorSerializer(zona.children.all(), many=True).data
        
        # Obtener todas las subzonas (descendientes completos)
        subzonas = []
        def collect_descendants(z):
            for child in z.children.all():
                subzonas.append(ZonaValorSerializer(child).data)
                collect_descendants(child)
        
        collect_descendants(zona)
        
        return Response({
            'zona_actual': ZonaValorSerializer(zona).data,
            'ancestros': ancestros,
            'hijos_directos': hijos,
            'descendientes_totales': subzonas,
            'ruta_jerarquica': zona.get_hierarchy_display(),
            'es_hoja': zona.is_leaf(),
            'nivel': zona.get_nivel_display()
        })
    
    @action(detail=False, methods=['get'])
    def niveles(self, request):
        """Obtener todas las zonas organizadas por nivel jerárquico."""
        niveles = {}
        for nivel_codigo, nivel_nombre in ZonaValor.NIVELES:
            zonas_nivel = ZonaValor.objects.filter(
                activo=True,
                nivel=nivel_codigo
            ).order_by('nombre_zona')
            niveles[nivel_codigo] = {
                'nombre': nivel_nombre,
                'zonas': ZonaValorSerializer(zonas_nivel, many=True).data,
                'cantidad': zonas_nivel.count()
            }
        
        return Response(niveles)
    
    @action(detail=False, methods=['post'])
    def punto_en_zona(self, request):
        """Determinar en qué zona(s) se encuentra un punto, considerando jerarquía."""
        serializer = PuntoEnPoligonoRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        lat = serializer.validated_data['lat']
        lng = serializer.validated_data['lng']
        zona_id = serializer.validated_data.get('zona_id')
        considerar_jerarquia = serializer.validated_data.get('considerar_jerarquia', True)
        
        if zona_id:
            # Verificar si el punto está en una zona específica
            zona = get_object_or_404(ZonaValor, id=zona_id)
            esta_en_zona = punto_en_poligono(lat, lng, zona.coordenadas)
            
            # Si está en la zona y queremos considerar jerarquía, buscar subzonas
            subzonas_contienen = []
            if esta_en_zona and considerar_jerarquia:
                for subzona in zona.children.all():
                    if punto_en_poligono(lat, lng, subzona.coordenadas):
                        subzonas_contienen.append(ZonaValorSerializer(subzona).data)
            
            return Response({
                'esta_en_zona': esta_en_zona,
                'zona': ZonaValorSerializer(zona).data if esta_en_zona else None,
                'subzonas_contienen': subzonas_contienen,
                'cantidad_subzonas': len(subzonas_contienen)
            })
        else:
            # Encontrar todas las zonas que contienen el punto
            zonas = ZonaValor.objects.filter(activo=True)
            zonas_contienen = []
            
            for zona in zonas:
                if punto_en_poligono(lat, lng, zona.coordenadas):
                    zonas_contienen.append(ZonaValorSerializer(zona).data)
            
            # Si se considera jerarquía, organizar por nivel
            if considerar_jerarquia and zonas_contienen:
                # Ordenar por nivel (de más específico a más general)
                niveles_orden = {nivel: i for i, (nivel, _) in enumerate(ZonaValor.NIVELES)}
                zonas_contienen.sort(key=lambda z: niveles_orden.get(z['nivel'], 99))
                
                # Encontrar la zona más específica (último nivel)
                zona_mas_especifica = zonas_contienen[-1] if zonas_contienen else None
                
                return Response({
                    'punto': {'lat': lat, 'lng': lng},
                    'zonas_contienen': zonas_contienen,
                    'cantidad_zonas': len(zonas_contienen),
                    'zona_mas_especifica': zona_mas_especifica,
                    'jerarquia_completa': True
                })
            
            return Response({
                'punto': {'lat': lat, 'lng': lng},
                'zonas_contienen': zonas_contienen,
                'cantidad_zonas': len(zonas_contienen)
            })


class PropiedadValoracionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para consultar valoraciones de propiedades.
    """
    queryset = PropiedadValoracion.objects.select_related('propiedad', 'zona')
    serializer_class = PropiedadValoracionSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    def get_queryset(self):
        """Filtrar por zona o propiedad si se especifica."""
        queryset = super().get_queryset()
        
        zona_id = self.request.query_params.get('zona_id')
        if zona_id:
            queryset = queryset.filter(zona_id=zona_id)
        
        propiedad_id = self.request.query_params.get('propiedad_id')
        if propiedad_id:
            queryset = queryset.filter(propiedad_id=propiedad_id)
        
        es_comparable = self.request.query_params.get('es_comparable')
        if es_comparable is not None:
            queryset = queryset.filter(es_comparable=es_comparable.lower() == 'true')
        
        return queryset


class EstadisticaZonaViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para consultar estadísticas por zona y tipo de propiedad.
    """
    queryset = EstadisticaZona.objects.select_related('zona')
    serializer_class = EstadisticaZonaSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    def get_queryset(self):
        """Filtrar por zona y tipo de propiedad."""
        queryset = super().get_queryset()
        
        zona_id = self.request.query_params.get('zona_id')
        if zona_id:
            queryset = queryset.filter(zona_id=zona_id)
        
        tipo_propiedad = self.request.query_params.get('tipo_propiedad')
        if tipo_propiedad:
            queryset = queryset.filter(tipo_propiedad=tipo_propiedad)
        
        return queryset


class HistorialPrecioZonaViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para consultar historial de precios por zona.
    """
    queryset = HistorialPrecioZona.objects.select_related('zona')
    serializer_class = HistorialPrecioZonaSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    def get_queryset(self):
        """Filtrar por zona y rango de fechas."""
        queryset = super().get_queryset()
        
        zona_id = self.request.query_params.get('zona_id')
        if zona_id:
            queryset = queryset.filter(zona_id=zona_id)
        
        fecha_desde = self.request.query_params.get('fecha_desde')
        fecha_hasta = self.request.query_params.get('fecha_hasta')
        if fecha_desde:
            queryset = queryset.filter(fecha_registro__gte=fecha_desde)
        if fecha_hasta:
            queryset = queryset.filter(fecha_registro__lte=fecha_hasta)
        
        return queryset.order_by('-fecha_registro')


class EstimacionPrecioAPIView(APIView):
    """
    Endpoint para estimar el precio de una propiedad basado en su ubicación y características.
    """
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    def post(self, request):
        serializer = EstimacionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        lat = data['lat']
        lng = data['lng']
        
        # Encontrar la zona que contiene el punto
        zona = encontrar_zona_por_punto(lat, lng)
        if not zona:
            return Response(
                {'error': 'El punto no se encuentra dentro de ninguna zona de valor definida.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Obtener propiedades comparables de la zona
        from ingestas.models import PropiedadRaw
        propiedades_zona = PropiedadRaw.objects.filter(
            # Aquí necesitaríamos filtrar por coordenadas dentro del polígono
            # Por simplicidad, asumimos que ya tenemos una relación
        )
        
        # Calcular estimación
        resultado = estimar_precio_propiedad(
            zona=zona,
            metros_cuadrados=data['metros_cuadrados'],
            habitaciones=data.get('habitaciones', 0),
            banos=data.get('banos', 0),
            antiguedad=data.get('antiguedad', 0),
            tipo_propiedad=data.get('tipo_propiedad', 'casa'),
            propiedades_comparables=propiedades_zona
        )
        
        response_serializer = EstimacionResponseSerializer(resultado)
        return Response(response_serializer.data)


class CalcularPrecioM2APIView(APIView):
    """
    Endpoint para calcular el precio por m² de una zona específica.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, zona_id):
        zona = get_object_or_404(ZonaValor, id=zona_id)
        
        # Obtener propiedades de la zona
        from ingestas.models import PropiedadRaw
        propiedades = PropiedadRaw.objects.all()  # Filtrar por zona cuando tengamos la relación
        
        resultado = calcular_precio_m2_zona(propiedades, zona)
        
        # Actualizar estadísticas de la zona
        zona.precio_promedio_m2 = resultado['precio_promedio']
        zona.cantidad_propiedades_analizadas = resultado['cantidad_utilizada']
        zona.save()
        
        # Crear registro en historial
        HistorialPrecioZona.objects.create(
            zona=zona,
            fecha_registro=timezone.now().date(),
            precio_promedio_m2=resultado['precio_promedio'],
            cantidad_propiedades=resultado['cantidad_utilizada'],
            desviacion_estandar=resultado.get('desviacion_estandar'),
            fuente_datos='cálculo_automático'
        )
        
        return Response({
            'zona': zona.nombre_zona,
            'precio_promedio_m2': resultado['precio_promedio'],
            'cantidad_propiedades_utilizadas': resultado['cantidad_utilizada'],
            'metodo': resultado['metodo'],
            'fecha_calculo': timezone.now()
        })


# Import para timezone
from django.utils import timezone

# Import para vistas basadas en funciones
from django.shortcuts import render
from django.http import JsonResponse
from .utils import generar_heatmap_data, obtener_rango_colores


def mapa_heatmap(request):
    """
    Vista para visualización heatmap de precios por m² CON PROPIEDADES REALES.
    """
    context = {
        'title': 'Heatmap de Precios por m² - PROPIEDADES REALES',
        'google_maps_api_key': 'AIzaSyBrL1QF7vTl9zF8FmCUumfRpFJcaYokO7Q',
        'nota': 'Este heatmap ahora muestra propiedades REALES de tu base de datos (Remax y Propify)',
    }
    return render(request, 'cuadrantizacion/heatmap.html', context)


def api_heatmap_data(request):
    """
    API endpoint para obtener datos de heatmap CON PROPIEDADES REALES.
    Reemplaza zonas inventadas por propiedades reales de la base de datos.
    """
    from ingestas.models import PropiedadRaw
    from propifai.models import PropifaiProperty
    from django.db.models import Q
    
    heatmap_data = []
    
    try:
        # Propiedades locales (Remax)
        local_props = PropiedadRaw.objects.filter(
            coordenadas__isnull=False,
            precio_usd__isnull=False,
            precio_usd__gt=0
        ).exclude(coordenadas='')[:100]  # Limitar para rendimiento
        
        for prop in local_props:
            try:
                coords = prop.coordenadas.split(',')
                if len(coords) >= 2:
                    lat = float(coords[0].strip())
                    lng = float(coords[1].strip())
                    
                    # Filtrar coordenadas fuera de Lima
                    if not (-12.2 <= lat <= -11.8 and -77.2 <= lng <= -76.8):
                        continue
                    
                    # Calcular área
                    area = None
                    if prop.area_construida and prop.area_construida > 0:
                        area = float(prop.area_construida)
                    elif prop.area_terreno and prop.area_terreno > 0:
                        area = float(prop.area_terreno)
                    
                    precio_m2 = None
                    if area and prop.precio_usd:
                        precio_m2 = float(prop.precio_usd) / area
                    
                    if precio_m2 and precio_m2 > 0 and precio_m2 < 10000:
                        weight = min(precio_m2 / 2000, 1.0)
                        heatmap_data.append({
                            'lat': lat,
                            'lng': lng,
                            'weight': weight,
                            'precio_m2': precio_m2,
                            'fuente': 'local',
                            'tipo': 'Propiedad Real (Remax)',
                            'id': prop.id
                        })
            except (ValueError, AttributeError, TypeError):
                continue
    except Exception as e:
        print(f"[ERROR] Error obteniendo propiedades locales: {e}")
    
    try:
        # Propiedades de Propifai (Propify)
        propifai_props = PropifaiProperty.objects.filter(
            coordinates__isnull=False,
            price__isnull=False,
            price__gt=0
        ).exclude(coordinates='')[:100]
        
        for prop in propifai_props:
            try:
                coords = prop.coordinates.split(',')
                if len(coords) >= 2:
                    lat = float(coords[0].strip())
                    lng = float(coords[1].strip())
                    
                    # Filtrar coordenadas fuera de Lima
                    if not (-12.2 <= lat <= -11.8 and -77.2 <= lng <= -76.8):
                        continue
                    
                    # Calcular área
                    area = None
                    if prop.built_area and prop.built_area > 0:
                        area = float(prop.built_area)
                    elif prop.land_area and prop.land_area > 0:
                        area = float(prop.land_area)
                    
                    precio_m2 = None
                    if area and prop.price:
                        precio_m2 = float(prop.price) / area
                    
                    if precio_m2 and precio_m2 > 0 and precio_m2 < 10000:
                        weight = min(precio_m2 / 2000, 1.0)
                        heatmap_data.append({
                            'lat': lat,
                            'lng': lng,
                            'weight': weight,
                            'precio_m2': precio_m2,
                            'fuente': 'propifai',
                            'tipo': 'Propiedad Real (Propify)',
                            'id': prop.id
                        })
            except (ValueError, AttributeError, TypeError):
                continue
    except Exception as e:
        print(f"[ERROR] Error obteniendo propiedades Propifai: {e}")
    
    # Si no hay propiedades reales, devolver array vacío (NO datos inventados)
    if not heatmap_data:
        print("[INFO] No se encontraron propiedades reales para el heatmap")
    
    # Calcular estadísticas
    precios_m2 = [d['precio_m2'] for d in heatmap_data if d.get('precio_m2')]
    
    return JsonResponse({
        'heatmap_data': heatmap_data,
        'total_propiedades': len(heatmap_data),
        'total_local': len([d for d in heatmap_data if d.get('fuente') == 'local']),
        'total_propifai': len([d for d in heatmap_data if d.get('fuente') == 'propifai']),
        'rango_precios': {
            'min': min(precios_m2) if precios_m2 else 0,
            'max': max(precios_m2) if precios_m2 else 0,
            'promedio': sum(precios_m2) / len(precios_m2) if precios_m2 else 0
        },
        'nota': 'Datos 100% reales de la base de datos - NO hay propiedades inventadas'
    })


@ensure_csrf_cookie
def mapa_zonas_valor(request):
    """
    Vista principal para el mapa de zonas de valor con jerarquía.
    """
    from .models import ZonaValor
    
    # Obtener todas las zonas activas
    zonas = ZonaValor.objects.filter(activo=True).select_related('parent')
    
    # Organizar zonas por nivel
    zonas_por_nivel = {}
    for nivel_codigo, nivel_nombre in ZonaValor.NIVELES:
        zonas_nivel = zonas.filter(nivel=nivel_codigo)
        zonas_por_nivel[nivel_codigo] = {
            'nombre': nivel_nombre,
            'zonas': zonas_nivel,
            'cantidad': zonas_nivel.count()
        }
    
    # Obtener zonas raíz (sin padre)
    zonas_raiz = zonas.filter(parent__isnull=True)
    
    # Preparar datos para el template
    context = {
        'title': 'Mapa de Zonas de Valor - Jerarquía',
        'google_maps_api_key': 'AIzaSyBrL1QF7vTl9zF8FmCUumfRpFJcaYokO7Q',
        'zonas_por_nivel': zonas_por_nivel,
        'zonas_raiz': zonas_raiz,
        'zonas_todas': zonas,  # Todas las zonas para filtrado dinámico
        'niveles': ZonaValor.NIVELES,
        'total_zonas': zonas.count(),
        'orden_niveles': [nivel[0] for nivel in ZonaValor.NIVELES],  # Lista de códigos en orden
    }
    return render(request, 'cuadrantizacion/mapa_zonas.html', context)


def _normalize_propify_operation(operation_name):
    name = (operation_name or 'Sin operación').strip()
    normalized = name.casefold()
    if any(term in normalized for term in ('alquiler', 'renta', 'arrendamiento')):
        return 'Alquiler', True
    if any(term in normalized for term in ('venta', 'compra')):
        return 'Venta', False
    return name, False


def _sale_price_per_m2(price, area, is_rental):
    if is_rental or price is None or area is None:
        return None
    try:
        area_decimal = Decimal(str(area))
        if area_decimal <= 0:
            return None
        calculated_price = Decimal(str(price)) / area_decimal
        if calculated_price <= 0:
            return None
        return str(calculated_price.quantize(Decimal('0.01')))
    except (InvalidOperation, TypeError, ValueError, ZeroDivisionError):
        return None


def _price_per_m2_in_usd(price_per_m2, currency_id):
    if price_per_m2 is None or currency_id == 1:
        return None
    try:
        converted = Decimal(str(price_per_m2)) / PEN_TO_USD_EXCHANGE_RATE
        if converted <= 0:
            return None
        return str(converted.quantize(Decimal('0.01')))
    except (InvalidOperation, TypeError, ValueError, ZeroDivisionError):
        return None


def _map_image_url(image_url):
    """Return a browser-readable image URL for map property cards."""
    value = str(image_url or '').strip()
    if not value:
        return None
    if '.blob.core.windows.net/' not in value.casefold():
        return value
    try:
        return generate_read_sas_url(value, expiry_minutes=120)
    except Exception:
        # A broken image must never prevent the rest of the map from loading.
        logger.exception('No se pudo firmar una imagen privada para el mapa.')
        return value


def _positive_area(value):
    try:
        return value if value is not None and Decimal(str(value)) > 0 else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def _available_propify_properties():
    """Return visible Propify listings that are currently available and mapped."""
    from propifai.models import PropifaiProperty

    with connections['propifai'].cursor() as cursor:
        cursor.execute("SELECT id, name FROM property_status")
        available_status_ids = [
            status_id
            for status_id, name in cursor.fetchall()
            if (name or '').strip().casefold() in {'available', 'disponible'}
        ]

    if not available_status_ids:
        logger.warning(
            'No se encontraron estados Available/Disponible en property_status; '
            'el mapa de cuadrantizacion no mostrara propiedades Propify.'
        )
        return []

    rows = list(
        PropifaiProperty.objects.using('propifai')
        .filter(
            is_visible=True,
            property_status_id__in=available_status_ids,
            latitude__isnull=False,
            longitude__isnull=False,
        )
        .values(
            'id', 'code', 'title', 'price', 'map_address', 'display_address',
            'latitude', 'longitude', 'property_type_id', 'district_id',
            'currency_id', 'operation_type_id',
        )
        .order_by('id')
    )

    with connections['propifai'].cursor() as cursor:
        cursor.execute("SELECT id, name FROM property_type")
        property_type_map = {row[0]: row[1] for row in cursor.fetchall()}
        cursor.execute("SELECT id, name FROM district")
        district_map = {row[0]: row[1] for row in cursor.fetchall()}
        cursor.execute("SELECT id, name FROM operation_type")
        operation_type_map = {row[0]: row[1] for row in cursor.fetchall()}

    image_map = {}
    specs_map = {}
    property_ids = [row['id'] for row in rows]
    try:
        for offset in range(0, len(property_ids), 500):
            batch = property_ids[offset:offset + 500]
            placeholders = ','.join(['%s'] * len(batch))
            with connections['propifai'].cursor() as cursor:
                cursor.execute(
                    f"""
                        SELECT property_id, MIN([file])
                        FROM property_media
                        WHERE media_type = 'image'
                          AND property_id IN ({placeholders})
                        GROUP BY property_id
                    """,
                    batch,
                )
                image_map.update(dict(cursor.fetchall()))
    except Exception:
        logger.warning(
            'No se pudo cargar property_media para el mapa; se usara la imagen por codigo.',
            exc_info=True,
        )

    try:
        for offset in range(0, len(property_ids), 500):
            batch = property_ids[offset:offset + 500]
            placeholders = ','.join(['%s'] * len(batch))
            with connections['propifai'].cursor() as cursor:
                cursor.execute(
                    f"""
                        SELECT property_id, land_area, built_area, bedrooms, bathrooms, half_bathrooms, unit_location
                        FROM property_specs
                        WHERE property_id IN ({placeholders})
                    """,
                    batch,
                )
                specs_map.update({
                    row[0]: {'land_area': row[1], 'built_area': row[2],
                             'bedrooms':row[3], 'bathrooms':row[4], 'half_bathrooms':row[5], 'unit_location':row[6]}
                    for row in cursor.fetchall()
                })
    except Exception:
        logger.warning(
            'No se pudo cargar property_specs para calcular el precio por m2 del mapa.',
            exc_info=True,
        )

    properties = []
    for row in rows:
        try:
            latitude = float(row['latitude'])
            longitude = float(row['longitude'])
        except (TypeError, ValueError):
            continue

        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            logger.warning(
                'Propiedad Propify %s omitida por coordenadas invalidas: %s, %s',
                row['id'], row['latitude'], row['longitude'],
            )
            continue

        price = row['price']
        property_type = property_type_map.get(row['property_type_id']) or 'Propiedad'
        operation_name = operation_type_map.get(row['operation_type_id'])
        operation_type, is_rental = _normalize_propify_operation(operation_name)
        specs = specs_map.get(row['id'], {})
        land_area = _positive_area(specs.get('land_area'))
        built_area = _positive_area(specs.get('built_area'))
        if 'terreno' in property_type.casefold():
            area = land_area or built_area
            area_source = 'land_area' if land_area else ('built_area' if built_area else None)
        else:
            area = built_area or land_area
            area_source = 'built_area' if built_area else ('land_area' if land_area else None)
        price_per_m2 = _sale_price_per_m2(price, area, is_rental)
        price_per_m2_usd = _price_per_m2_in_usd(price_per_m2, row['currency_id'])
        # Precio por m² de cada superficie, para comparar terreno vs construcción.
        built_price_per_m2 = _sale_price_per_m2(price, built_area, is_rental)
        built_price_per_m2_usd = _price_per_m2_in_usd(
            built_price_per_m2, row['currency_id']
        )
        land_price_per_m2 = _sale_price_per_m2(price, land_area, is_rental)
        land_price_per_m2_usd = _price_per_m2_in_usd(
            land_price_per_m2, row['currency_id']
        )

        image_path = image_map.get(row['id'])
        if image_path and str(image_path).startswith(('http://', 'https://')):
            image_url = str(image_path)
        elif image_path:
            encoded_path = '/'.join(
                quote(part, safe='')
                for part in str(image_path).lstrip('/').split('/')
            )
            image_url = f'{PROPIFY_MEDIA_BASE_URL}/{encoded_path}'
        elif row['code']:
            image_url = f"{PROPIFY_MEDIA_BASE_URL}/{quote(str(row['code']), safe='')}.jpg"
        else:
            image_url = None

        properties.append({
            'id': row['id'],
            'source': 'Propify',
            'bedrooms': specs.get('bedrooms'),
            'bathrooms': specs.get('bathrooms'),
            'half_bathrooms': specs.get('half_bathrooms'),
            'unit_location': specs.get('unit_location'),
            'source_key': 'propify',
            'code': row['code'] or '',
            'title': row['title'] or row['code'] or 'Propiedad Propify',
            'price': str(price) if price is not None else None,
            'address': row['display_address'] or row['map_address'] or '',
            'property_type': property_type,
            'operation_type': operation_type,
            'is_rental': is_rental,
            'district': district_map.get(row['district_id']) or 'Sin distrito',
            'image_url': image_url,
            'url': None,
            'currency_symbol': '$' if row['currency_id'] == 1 else 'S/.',
            'price_per_m2': price_per_m2,
            'price_per_m2_usd': price_per_m2_usd,
            'built_price_per_m2': built_price_per_m2,
            'built_price_per_m2_usd': built_price_per_m2_usd,
            'land_price_per_m2': land_price_per_m2,
            'land_price_per_m2_usd': land_price_per_m2_usd,
            'built_area_m2': str(built_area) if built_area is not None else None,
            'land_area_m2': str(land_area) if land_area is not None else None,
            'area_used': area_source if price_per_m2 is not None else None,
            'lat': latitude,
            'lng': longitude,
            'status': 'Disponible',
            'location_precision': 'Exacta',
        })

    return properties


def _available_scraped_properties(sources=('remax', 'properati')):
    """Return active mapped listings from the supported competitor portals."""
    from ingestas.models import PropiedadesCompetencia, RevisionPropiedadScraping

    reviews = {r.propiedad_id: r.motivo for r in RevisionPropiedadScraping.objects.filter(excluida=True)}

    rows = (
        PropiedadesCompetencia.objects
        .filter(
            fuente__in=sources,
            estado_publicacion='activa',
            latitud__isnull=False,
            longitud__isnull=False,
        )
        .values(
            'id', 'fuente', 'id_origen', 'titulo', 'tipo_inmueble',
            'tipo_operacion', 'precio_soles', 'precio_usd', 'area_m2',
            'area_terreno', 'area_construida',
            'distrito', 'direccion_texto', 'latitud', 'longitud',
            'precision_ubicacion', 'imagen_url',
            'url',
        )
        .order_by('fuente', 'id')
    )

    properties = []
    for row in rows:
        try:
            latitude = float(row['latitud'])
            longitude = float(row['longitud'])
        except (TypeError, ValueError):
            continue
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            logger.warning(
                'Propiedad %s %s omitida por coordenadas invalidas: %s, %s',
                row['fuente'], row['id_origen'], row['latitud'], row['longitud'],
            )
            continue

        source_key = (row['fuente'] or '').strip().casefold()
        source = {'remax': 'Remax', 'properati': 'Properati'}.get(
            source_key, source_key.title()
        )
        operation_type, is_rental = _normalize_propify_operation(row['tipo_operacion'])
        property_type = row['tipo_inmueble'] or 'Propiedad'
        is_land = 'terreno' in property_type.casefold()
        # Igual que en Propify: las dos superficies viajan por separado y la
        # tarjeta del mapa las muestra juntas.
        land_area = _positive_area(row.get('area_terreno'))
        built_area = _positive_area(row.get('area_construida'))
        if land_area is None and built_area is None:
            # Registros antiguos sin superficies separadas: el área principal
            # histórica ocupa el slot que corresponde según el tipo.
            legacy_area = _positive_area(row['area_m2'])
            if is_land:
                land_area = legacy_area
            else:
                built_area = legacy_area
        if is_land:
            area = land_area or built_area
            area_source = 'land_area' if land_area else ('built_area' if built_area else None)
        else:
            area = built_area or land_area
            area_source = 'built_area' if built_area else ('land_area' if land_area else None)

        # Remax normalmente publica soles y USD simultáneamente. Se conserva
        # el precio principal en soles; Properati usa la moneda disponible.
        if row['precio_soles'] is not None and row['precio_soles'] > 0:
            price = row['precio_soles']
            currency_symbol = 'S/.'
            currency_id = 2
        else:
            price = row['precio_usd']
            currency_symbol = '$'
            currency_id = 1

        price_per_m2 = _sale_price_per_m2(price, area, is_rental)
        # Use the portal's USD amount when it exists so every map label is
        # directly comparable. Convert from soles only as a fallback.
        price_per_m2_usd = _sale_price_per_m2(
            row['precio_usd'], area, is_rental
        )
        if price_per_m2_usd is None:
            price_per_m2_usd = _price_per_m2_in_usd(
                price_per_m2, currency_id
            )
        # Precio por m² de cada superficie, para comparar terreno vs construcción.
        built_price_per_m2 = _sale_price_per_m2(price, built_area, is_rental)
        built_price_per_m2_usd = _sale_price_per_m2(
            row['precio_usd'], built_area, is_rental
        )
        if built_price_per_m2_usd is None:
            built_price_per_m2_usd = _price_per_m2_in_usd(
                built_price_per_m2, currency_id
            )
        land_price_per_m2 = _sale_price_per_m2(price, land_area, is_rental)
        land_price_per_m2_usd = _sale_price_per_m2(
            row['precio_usd'], land_area, is_rental
        )
        if land_price_per_m2_usd is None:
            land_price_per_m2_usd = _price_per_m2_in_usd(
                land_price_per_m2, currency_id
            )
        precision = (row['precision_ubicacion'] or 'desconocida').strip().casefold()
        precision_label = {
            'exacta': 'Exacta',
            'aproximada': 'Aproximada',
            'desconocida': 'Desconocida',
        }.get(precision, 'Desconocida')

        properties.append({
            'id': f"{source_key}-{row['id']}",
            'record_id': row['id'],
            'quality_excluded': row['id'] in reviews,
            'quality_exclusion_reason': reviews.get(row['id'], ''),
            '_quality_input': {
                'usd': row['precio_usd'], 'land': row['area_terreno'],
                'built': row['area_construida'],
                'legacy_area': bool(row['area_m2'] and not row['area_terreno'] and not row['area_construida']),
            },
            'source': source,
            'source_key': source_key,
            'code': row['id_origen'] or '',
            'title': row['titulo'] or row['id_origen'] or f'Propiedad {source}',
            'price': str(price) if price is not None else None,
            'address': row['direccion_texto'] or '',
            'property_type': property_type,
            'operation_type': operation_type,
            'is_rental': is_rental,
            'district': row['distrito'] or 'Sin distrito',
            'image_url': _map_image_url(row['imagen_url']),
            'url': row['url'] if str(row['url'] or '').startswith(('http://', 'https://')) else None,
            'currency_symbol': currency_symbol,
            'price_per_m2': price_per_m2,
            'price_per_m2_usd': price_per_m2_usd,
            'built_price_per_m2': built_price_per_m2,
            'built_price_per_m2_usd': built_price_per_m2_usd,
            'land_price_per_m2': land_price_per_m2,
            'land_price_per_m2_usd': land_price_per_m2_usd,
            'built_area_m2': str(built_area) if built_area is not None else None,
            'land_area_m2': str(land_area) if land_area is not None else None,
            'area_used': area_source if price_per_m2 is not None else None,
            'lat': latitude,
            'lng': longitude,
            'status': 'Disponible',
            'location_precision': precision_label,
        })

    return properties


def api_available_map_properties(request):
    """Available Propify, Remax and Properati markers for the zoning map."""
    from .property_quality import annotate_map_quality
    requested_sources = {
        source.strip().casefold()
        for source in request.GET.get('sources', 'propify,remax,properati').split(',')
        if source.strip().casefold() in {'propify', 'remax', 'properati'}
    }
    properties = []
    failed_sources = []
    loaders = []
    if 'propify' in requested_sources:
        loaders.append(('Propify', _available_propify_properties))
    competitor_sources = tuple(
        source for source in ('remax', 'properati') if source in requested_sources
    )
    if competitor_sources:
        source_label = '/'.join(source.title() for source in competitor_sources)
        loaders.append((
            source_label,
            lambda: _available_scraped_properties(competitor_sources),
        ))

    for source, loader in loaders:
        try:
            properties.extend(loader())
        except Exception:
            failed_sources.append(source)
            logger.exception(
                'No se pudieron cargar propiedades %s para cuadrantizacion.', source
            )

    if not properties and failed_sources:
        return JsonResponse({
            'properties': [],
            'total': 0,
            'error': 'No se pudieron cargar las propiedades disponibles.',
            'failed_sources': failed_sources,
        }, status=503)

    quality = annotate_map_quality(properties)
    return JsonResponse({
        'properties': properties,
        'quality_summary': quality,
        'total': len(properties),
        'status_filter': 'Disponible',
        'requested_sources': sorted(requested_sources),
        'failed_sources': failed_sources,
    })


def api_propify_available_properties(request):
    """Markers for the available Propify layer on the zoning map."""
    try:
        properties = _available_propify_properties()
    except Exception:
        logger.exception(
            'No se pudieron cargar las propiedades Propify disponibles para cuadrantizacion.'
        )
        return JsonResponse(
            {
                'properties': [],
                'total': 0,
                'error': 'No se pudieron cargar las propiedades disponibles.',
            },
            status=503,
        )

    return JsonResponse({
        'properties': properties,
        'total': len(properties),
        'status_filter': 'Disponible',
    })


def configurar_jerarquia(request):
    """
    Vista para configurar y crear jerarquías anidadas de zonas.
    Permite anidar padres con hijos visualmente.
    """
    from .models import ZonaValor
    
    # Obtener todas las zonas activas con información jerárquica
    zonas = ZonaValor.objects.filter(activo=True).select_related('parent').order_by('nivel', 'nombre_zona')
    
    # Organizar zonas por nivel para el formulario
    zonas_por_nivel = {}
    for nivel_codigo, nivel_nombre in ZonaValor.NIVELES:
        zonas_nivel = zonas.filter(nivel=nivel_codigo)
        zonas_por_nivel[nivel_codigo] = {
            'nombre': nivel_nombre,
            'zonas': zonas_nivel,
            'cantidad': zonas_nivel.count()
        }
    
    # Construir estructura jerárquica para visualización
    def construir_arbol(zonas_list):
        """Construye una estructura de árbol a partir de las zonas."""
        # Crear diccionario de zonas por ID
        zonas_dict = {zona.id: zona for zona in zonas_list}
        
        # Inicializar árbol
        arbol = []
        zonas_con_hijos = set()
        
        # Primero identificar todas las zonas que tienen hijos
        for zona in zonas_list:
            if zona.parent_id and zona.parent_id in zonas_dict:
                zonas_con_hijos.add(zona.parent_id)
        
        # Construir árbol empezando por las raíces
        for zona in zonas_list:
            if zona.parent_id is None:
                arbol.append({
                    'zona': zona,
                    'hijos': [],
                    'nivel': 0
                })
            elif zona.parent_id not in zonas_dict:
                # Si el padre no está en la lista (inactivo o eliminado), mostrar como raíz
                arbol.append({
                    'zona': zona,
                    'hijos': [],
                    'nivel': 0
                })
        
        # Función recursiva para agregar hijos
        def agregar_hijos(nodo_actual, zonas_restantes, nivel_actual):
            zona_id = nodo_actual['zona'].id
            hijos = [z for z in zonas_restantes if z.parent_id == zona_id]
            
            for hijo in hijos:
                nodo_hijo = {
                    'zona': hijo,
                    'hijos': [],
                    'nivel': nivel_actual + 1
                }
                nodo_actual['hijos'].append(nodo_hijo)
                # Llamada recursiva para hijos de este hijo
                agregar_hijos(nodo_hijo, zonas_restantes, nivel_actual + 1)
        
        # Agregar hijos a cada nodo raíz
        for nodo_raiz in arbol:
            agregar_hijos(nodo_raiz, zonas_list, 0)
        
        return arbol
    
    # Construir árbol jerárquico
    arbol_jerarquico = construir_arbol(list(zonas))
    
    # Estadísticas
    total_zonas = zonas.count()
    zonas_con_hijos = zonas.filter(children__isnull=False).distinct().count()
    zonas_sin_padre = zonas.filter(parent__isnull=True).count()
    
    context = {
        'title': 'Configurar Jerarquía de Zonas',
        'zonas_por_nivel': zonas_por_nivel,
        'arbol_jerarquico': arbol_jerarquico,
        'niveles': ZonaValor.NIVELES,
        'total_zonas': total_zonas,
        'zonas_con_hijos': zonas_con_hijos,
        'zonas_sin_padre': zonas_sin_padre,
        'max_niveles': 6,  # país, departamento, provincia, distrito, zona, subzona
    }
    
    return render(request, 'cuadrantizacion/configurar_jerarquia.html', context)
