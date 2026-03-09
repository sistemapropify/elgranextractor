from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAuthenticated
from rest_framework.views import APIView

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


class ZonaValorViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar zonas de valor (polígonos) con jerarquía.
    """
    serializer_class = ZonaValorSerializer
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
    
    def perform_create(self, serializer):
        """Calcular área automáticamente al crear una zona y calcular precio inicial."""
        zona = serializer.save()
        
        # Calcular área del polígono
        area = calcular_area_poligono(zona.coordenadas)
        if area:
            zona.area_total = area
        
        # Calcular precio inicial basado en propiedades dentro de la zona
        from .services import calcular_precio_m2_zona
        resultado = calcular_precio_m2_zona(zona.id)
        
        if resultado and resultado.get('precio_promedio_m2'):
            zona.precio_promedio_m2 = resultado['precio_promedio_m2']
            zona.desviacion_estandar_m2 = resultado.get('desviacion_estandar_m2', 0)
            zona.cantidad_propiedades_analizadas = resultado.get('cantidad_propiedades_utilizadas', 0)
        
        zona.save()
    
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