from django.shortcuts import render
from django.http import JsonResponse
from django.db.models import Q, F, FloatField, ExpressionWrapper, Count
from django.db.models.functions import Cast
from django.utils import timezone
from ingestas.models import PropiedadRaw
from propifai.models import PropifaiProperty
import json
import math
import logging

logger = logging.getLogger(__name__)

try:
    from .charts import create_data_quality_summary, calculate_data_quality_metrics
except ImportError as e:
    logger.warning(f"No se pudo importar charts: {e}. Usando funciones dummy.")
    # Funciones dummy como fallback
    def create_data_quality_summary(*args, **kwargs):
        return {"error": "Charts module not available"}
    
    def calculate_data_quality_metrics(*args, **kwargs):
        return {"error": "Charts module not available"}
# FORCE RELOAD - Template heatmap fix


def heatmap_view(request):
    """Vista principal para el heatmap de precio por m² - VERSIÓN ULTRA VISIBLE CON DATOS 100% REALES"""
    # Obtener datos reales de propiedades para el heatmap - SIN DATOS INVENTADOS
    google_maps_api_key = "AIzaSyBrL1QF7vTl9zF8FmCUumfRpFJcaYokO7Q"
    heatmap_points = []
    local_count = 0
    propifai_count = 0
    
    try:
        # Propiedades locales (Remax) - TODAS LAS QUE TIENEN COORDENADAS
        from ingestas.models import PropiedadRaw
        local_props = PropiedadRaw.objects.filter(
            coordenadas__isnull=False
        ).exclude(coordenadas='')  # TODAS las propiedades con coordenadas
        
        # DEBUG: Contar cuántas propiedades hay
        total_props_count = local_props.count()
        print(f"[DEBUG HEATMAP] Total propiedades con coordenadas: {total_props_count}")
        
        props_added = 0
        props_skipped = 0
        
        for prop in local_props:
            try:
                coords = prop.coordenadas.split(',')
                if len(coords) >= 2:
                    lat = float(coords[0].strip())
                    lng = float(coords[1].strip())
                    # Mostrar TODAS las coordenadas, no solo Lima
                    # (sin filtro de bounding box)
                    
                    # Calcular peso basado en rangos de precio/m²
                    weight = 0.5  # Peso por defecto para propiedades sin precio
                    precio_m2 = None
                    
                    # Intentar calcular precio por m²
                    area = None
                    tipo_propiedad = (prop.tipo_propiedad or '').lower().strip() if hasattr(prop, 'tipo_propiedad') else ''
                    # Detectar terrenos con más variantes
                    es_terreno = any(term in tipo_propiedad for term in [
                        'terreno', 'terrenos', 'lote', 'parcela', 'parcel',
                        'land', 'lot', 'plot', 'ground', 'solar', 'vacant'
                    ])
                    
                    # Si es terreno, usar solo área de terreno
                    if es_terreno:
                        if prop.area_terreno and prop.area_terreno > 0:
                            area = float(prop.area_terreno)
                        # Si no hay área de terreno pero sí área construida, no usar área construida para terrenos
                        # (dejar area = None para que no calcule precio/m²)
                    else:
                        # Para otros tipos, priorizar área construida
                        if prop.area_construida and prop.area_construida > 0:
                            area = float(prop.area_construida)
                        elif prop.area_terreno and prop.area_terreno > 0:
                            area = float(prop.area_terreno)
                    
                    # Calcular peso basado en precio - GARANTIZAR QUE TODAS LAS PROPIEDADES SEAN VISIBLES
                    # Peso mínimo para TODAS las propiedades: 1.0 (en lugar de 0.5)
                    weight = 1.0  # Peso mínimo garantizado para visibilidad
                    
                    if prop.precio_usd and prop.precio_usd > 0:
                        precio_val = float(prop.precio_usd)
                        # Usar precio como indicador de valor - ESCALA MEJORADA
                        if precio_val < 30000:
                            weight = 1.2  # Muy bajo pero visible
                        elif precio_val < 60000:
                            weight = 1.5  # Bajo
                        elif precio_val < 100000:
                            weight = 2.0  # Medio-bajo
                        elif precio_val < 200000:
                            weight = 2.5  # Medio
                        elif precio_val < 400000:
                            weight = 3.0  # Alto
                        elif precio_val < 800000:
                            weight = 3.5  # Muy alto
                        else:
                            weight = 4.0  # Extremadamente alto
                        
                        # Si tenemos área, calcular precio/m² para ajuste adicional
                        if area and area > 0:
                            precio_m2 = precio_val / area
                            if precio_m2 > 0 and precio_m2 < 10000:
                                # Ajustar peso basado en precio/m² (máximo 4.0)
                                weight = max(weight, min(precio_m2 / 800, 4.0))
                    
                    # Garantizar que propiedades sin precio también sean visibles
                    # (ya tienen weight = 1.0 por defecto)
                    
                    heatmap_points.append({
                        'lat': lat,
                        'lng': lng,
                        'weight': weight,
                        'precio_m2': precio_m2 if precio_m2 else 0,
                        'fuente': 'local',
                        'tipo': 'Propiedad Real (Remax)',
                        'id': prop.id,
                        'tiene_precio': prop.precio_usd is not None and prop.precio_usd > 0,
                        'tiene_area': area is not None,
                        'precio_usd': float(prop.precio_usd) if prop.precio_usd else None,
                        'area_construida': float(prop.area_construida) if prop.area_construida else None,
                        'area_terreno': float(prop.area_terreno) if prop.area_terreno else None,
                        'direccion': prop.direccion if hasattr(prop, 'direccion') and prop.direccion else None,
                        'tipo_propiedad': prop.tipo_propiedad if hasattr(prop, 'tipo_propiedad') and prop.tipo_propiedad else None,
                        'habitaciones': prop.habitaciones if hasattr(prop, 'habitaciones') else None,
                        'banos': prop.banos if hasattr(prop, 'banos') else None
                    })
                    local_count += 1
                    props_added += 1
                else:
                    props_skipped += 1
            except (ValueError, AttributeError, TypeError) as e:
                props_skipped += 1
                continue
        
        print(f"[DEBUG HEATMAP] Propiedades añadidas: {props_added}, omitidas: {props_skipped}")
    except Exception as e:
        print(f"[DEBUG] Error obteniendo propiedades locales: {e}")
    
    try:
        # Propiedades de Propifai (Propify) - TODAS LAS QUE TIENEN COORDENADAS
        from propifai.models import PropifaiProperty
        propifai_props = PropifaiProperty.objects.filter(
            coordinates__isnull=False
        ).exclude(coordinates='')
        
        propifai_count = 0
        props_added_propifai = 0
        props_skipped_propifai = 0
        
        for prop in propifai_props:
            try:
                coords = prop.coordinates.split(',')
                if len(coords) >= 2:
                    lat = float(coords[0].strip())
                    lng = float(coords[1].strip())
                    # Mostrar TODAS las coordenadas, no solo Lima
                    # (sin filtro de bounding box)
                    
                    # Calcular peso basado en rangos de precio/m²
                    weight = 1.0  # Peso mínimo garantizado para visibilidad
                    
                    # Intentar calcular precio por m²
                    area = None
                    
                    # Detectar terrenos en Propifai - LÓGICA MEJORADA
                    # 1. Buscar en description, title, zoning
                    description = (prop.description or '').lower().strip()
                    title = (prop.title or '').lower().strip()
                    zoning = (prop.zoning or '').lower().strip()
                    
                    # Verificar si contiene términos de terreno
                    textos_busqueda = f'{description} {title} {zoning}'
                    es_terreno_texto = any(term in textos_busqueda for term in [
                        'terreno', 'terrenos', 'lote', 'parcela', 'parcel',
                        'land', 'lot', 'plot', 'ground', 'solar', 'vacant'
                    ])
                    
                    # 2. Heurística mejorada y más agresiva para detectar terrenos
                    built_area_val = prop.built_area if prop.built_area else 0
                    land_area_val = prop.land_area if prop.land_area else 0
                    
                    # LÓGICA SIMPLIFICADA Y MÁS AGRESIVA:
                    # Si tiene land_area y es mayor que built_area, probablemente es terreno
                    # (el usuario insiste que terrenos no deben usar built_area nunca)
                    es_terreno_heuristico = False
                    if land_area_val > 0:
                        # Caso 1: No tiene built_area o es 0 -> muy probable terreno
                        if built_area_val == 0 or built_area_val is None:
                            es_terreno_heuristico = True
                        # Caso 2: land_area es mayor que built_area -> probable terreno
                        elif land_area_val > built_area_val:
                            es_terreno_heuristico = True
                        # Caso 3: Tiene built_area pero land_area es significativo también
                        # (por seguridad, si land_area > 100m², lo consideramos terreno)
                        elif land_area_val > 100:  # Terreno de al menos 100m²
                            es_terreno_heuristico = True
                    
                    # 3. Si es proyecto, definitivamente es terreno para desarrollo
                    es_proyecto = prop.is_project if hasattr(prop, 'is_project') else False
                    if es_proyecto and land_area_val > 0:
                        es_terreno_heuristico = True
                    
                    # Combinar detecciones - si cualquiera dice que es terreno, lo tratamos como terreno
                    es_terreno = es_terreno_texto or es_terreno_heuristico
                    
                    # SI ES TERRENO: usar SOLO land_area (nunca built_area)
                    if es_terreno:
                        if prop.land_area and prop.land_area > 0:
                            area = float(prop.land_area)
                        # Si no hay land_area, NO usar built_area bajo ninguna circunstancia
                        # (dejar area = None, no calcular precio/m²)
                    else:
                        # Para NO terrenos, priorizar built_area con fallback a land_area
                        if prop.built_area and prop.built_area > 0:
                            area = float(prop.built_area)
                        elif prop.land_area and prop.land_area > 0:
                            area = float(prop.land_area)
                    
                    # Calcular peso basado en precio
                    if prop.price and prop.price > 0:
                        precio_val = float(prop.price)
                        # Usar precio como indicador de valor - ESCALA MEJORADA
                        if precio_val < 30000:
                            weight = 1.2  # Muy bajo pero visible
                        elif precio_val < 60000:
                            weight = 1.5  # Bajo
                        elif precio_val < 100000:
                            weight = 2.0  # Medio-bajo
                        elif precio_val < 200000:
                            weight = 2.5  # Medio
                        elif precio_val < 400000:
                            weight = 3.0  # Alto
                        elif precio_val < 800000:
                            weight = 3.5  # Muy alto
                        else:
                            weight = 4.0  # Extremadamente alto
                        
                        # Si tenemos área, calcular precio/m² para ajuste adicional
                        if area and area > 0:
                            precio_m2 = precio_val / area
                            if precio_m2 > 0 and precio_m2 < 10000:
                                # Ajustar peso basado en precio/m² (máximo 4.0)
                                weight = max(weight, min(precio_m2 / 800, 4.0))
                    
                    heatmap_points.append({
                        'lat': lat,
                        'lng': lng,
                        'weight': weight,
                        'precio_m2': precio_m2 if 'precio_m2' in locals() and precio_m2 else 0,
                        'fuente': 'propifai',
                        'tipo': 'Propiedad Real (Propify)',
                        'id': prop.id,
                        'tiene_precio': prop.price is not None and prop.price > 0,
                        'price': float(prop.price) if prop.price else None,
                        'built_area': float(prop.built_area) if prop.built_area else None,
                        'land_area': float(prop.land_area) if prop.land_area else None,
                        'address': prop.real_address if hasattr(prop, 'real_address') and prop.real_address else None,
                        'property_type': prop.zoning if hasattr(prop, 'zoning') and prop.zoning else None,
                        'bedrooms': prop.bedrooms if hasattr(prop, 'bedrooms') else None,
                        'bathrooms': prop.bathrooms if hasattr(prop, 'bathrooms') else None,
                        'title': prop.title if hasattr(prop, 'title') and prop.title else None
                    })
                    propifai_count += 1
                    props_added_propifai += 1
                else:
                    props_skipped_propifai += 1
            except (ValueError, AttributeError, TypeError) as e:
                props_skipped_propifai += 1
                continue
        
        print(f"[DEBUG HEATMAP] Propiedades Propifai añadidas: {props_added_propifai}, omitidas: {props_skipped_propifai}")
        
    except Exception as e:
        print(f"[DEBUG] Error obteniendo propiedades Propifai: {e}")
        print(f"[DEBUG] Detalle del error: {type(e).__name__}: {str(e)}")
        # Continuar sin propiedades Propifai - al menos mostraremos las de Remax
    
    # Convertir a JSON para incrustar en JavaScript
    import json
    heatmap_data_json = json.dumps(heatmap_points)
    
    # Contar propiedades por fuente
    total_count = len(heatmap_points)
    
    # Mostrar mensaje informativo sobre los datos reales
    if not heatmap_points:
        print("[INFO] No se encontraron propiedades válidas para el heatmap - BASE DE DATOS VACÍA O SIN COORDENADAS VÁLIDAS")
    else:
        print(f"[INFO] Heatmap cargado con {total_count} propiedades reales ({local_count} Remax, {propifai_count} Propify)")
        print(f"[DEBUG HEATMAP] JSON size: {len(heatmap_data_json)} bytes, {len(heatmap_points)} points")
        # Mostrar algunas coordenadas de ejemplo
        if heatmap_points:
            print(f"[DEBUG HEATMAP] Ejemplo de coordenadas: {heatmap_points[0]['lat']}, {heatmap_points[0]['lng']} - {heatmap_points[0]['fuente']}")
    
    # Preparar contexto para el template
    context = {
        'heatmap_points': heatmap_points,
        'total_count': total_count,
        'local_count': local_count,
        'propifai_count': propifai_count,
        'heatmap_data_json': heatmap_data_json,
        'google_maps_api_key': google_maps_api_key,
        'title': '🔥 HEATMAP CON DATOS REALES - Precio por m² - El Gran Extractor',
    }
    
    # Usar el template heatmap.html que extiende base.html
    return render(request, 'market_analysis/heatmap.html', context)


def heatmap_simple_view(request):
    """Vista simplificada del heatmap - versión básica"""
    # Obtener datos básicos para el heatmap simple
    google_maps_api_key = "AIzaSyBrL1QF7vTl9zF8FmCUumfRpFJcaYokO7Q"
    
    # Preparar contexto mínimo
    context = {
        'google_maps_api_key': google_maps_api_key,
        'title': 'Heatmap Simple - El Gran Extractor',
        'total_count': 0,
        'local_count': 0,
        'propifai_count': 0,
        'heatmap_data_json': '[]'
    }
    
    # Usar el template heatmap_simple.html
    return render(request, 'market_analysis/heatmap_simple.html', context)


def heatmap_test_view(request):
    """Vista de prueba del heatmap"""
    # Vista simple para testing
    context = {
        'title': 'Heatmap Test - El Gran Extractor',
        'google_maps_api_key': "AIzaSyBrL1QF7vTl9zF8FmCUumfRpFJcaYokO7Q",
    }
    
    # Usar el template heatmap_test.html si existe, sino heatmap_simple.html
    return render(request, 'market_analysis/heatmap_test.html', context)


def api_heatmap_data(request):
    """API para obtener datos de propiedades para el heatmap - Versión ultra simplificada"""
    try:
        # Obtener parámetros de filtro
        tipo_propiedad = request.GET.get('tipo_propiedad', '')
        precio_min = request.GET.get('precio_min', '')
        precio_max = request.GET.get('precio_max', '')
        area_min = request.GET.get('area_min', '')
        area_max = request.GET.get('area_max', '')
        fuente = request.GET.get('fuente', 'todas')
        debug_mode = request.GET.get('debug', '')
        
        # Por defecto, usar datos REALES de la base de datos
        propiedades = []
        
        try:
            from django.db import connection
            import time
            start_time = time.time()
            
            # Consulta REAL de propiedades locales
            queryset_local = PropiedadRaw.objects.filter(
                coordenadas__isnull=False,
                precio_usd__isnull=False,
                precio_usd__gt=0
            ).exclude(coordenadas='')
            
            # Aplicar filtros si están presentes
            if tipo_propiedad:
                queryset_local = queryset_local.filter(tipo_propiedad__icontains=tipo_propiedad)
            if precio_min:
                queryset_local = queryset_local.filter(precio_usd__gte=float(precio_min))
            if precio_max:
                queryset_local = queryset_local.filter(precio_usd__lte=float(precio_max))
            if area_min:
                queryset_local = queryset_local.filter(
                    Q(area_construida__gte=float(area_min)) | Q(area_terreno__gte=float(area_min))
                )
            if area_max:
                queryset_local = queryset_local.filter(
                    Q(area_construida__lte=float(area_max)) | Q(area_terreno__lte=float(area_max))
                )
            
            # TODAS las propiedades para rendimiento (sin límite)
            # queryset_local = queryset_local  # Sin límite
            
            for prop in queryset_local:
                try:
                    if prop.coordenadas:
                        coords = prop.coordenadas.split(',')
                        if len(coords) >= 2:
                            lat = float(coords[0].strip())
                            lng = float(coords[1].strip())
                            
                            # Calcular área con detección de terrenos
                            area = None
                            tipo_propiedad = (prop.tipo_propiedad or '').lower().strip() if hasattr(prop, 'tipo_propiedad') else ''
                            # Detectar terrenos
                            es_terreno = any(term in tipo_propiedad for term in [
                                'terreno', 'terrenos', 'lote', 'parcela', 'parcel',
                                'land', 'lot', 'plot', 'ground', 'solar', 'vacant'
                            ])
                            
                            # Si es terreno, usar solo área de terreno
                            if es_terreno:
                                if prop.area_terreno and prop.area_terreno > 0:
                                    area = float(prop.area_terreno)
                                # Si no hay área de terreno, no usar área construida para terrenos
                            else:
                                # Para otros tipos, priorizar área construida
                                if prop.area_construida and prop.area_construida > 0:
                                    area = float(prop.area_construida)
                                elif prop.area_terreno and prop.area_terreno > 0:
                                    area = float(prop.area_terreno)
                            
                            precio_m2 = None
                            if area and prop.precio_usd:
                                precio_m2 = float(prop.precio_usd) / area
                            
                            if precio_m2 and precio_m2 > 0 and precio_m2 < 10000:
                                propiedades.append({
                                    'id': prop.id,
                                    'lat': lat,
                                    'lng': lng,
                                    'precio_m2': round(precio_m2, 2),
                                    'precio_usd': float(prop.precio_usd),
                                    'area': area,
                                    'tipo_propiedad': prop.tipo_propiedad or '',
                                    'fuente': 'local',
                                    'weight': min(precio_m2 / 1000, 2.0)
                                })
                except (ValueError, AttributeError, TypeError):
                    continue
            
            # Consulta REAL de propiedades Propifai (si fuente es 'todas' o 'propifai')
            if fuente in ['todas', 'propifai']:
                queryset_propifai = PropifaiProperty.objects.filter(
                    coordinates__isnull=False,
                    price__isnull=False,
                    price__gt=0
                ).exclude(coordinates='')
                
                # Aplicar filtros similares
                if tipo_propiedad:
                    queryset_propifai = queryset_propifai.filter(tipo_propiedad__icontains=tipo_propiedad)
                if precio_min:
                    queryset_propifai = queryset_propifai.filter(price__gte=float(precio_min))
                if precio_max:
                    queryset_propifai = queryset_propifai.filter(price__lte=float(precio_max))
                
                # TODAS las propiedades Propifai (sin límite)
                # queryset_propifai = queryset_propifai  # Sin límite
                
                for prop in queryset_propifai:
                    try:
                        if prop.coordinates:
                            coords = prop.coordinates.split(',')
                            if len(coords) >= 2:
                                lat = float(coords[0].strip())
                                lng = float(coords[1].strip())
                                
                                # Calcular área con detección de terrenos
                                area = None
                                
                                # Detectar terrenos en Propifai
                                description = (prop.description or '').lower().strip()
                                title = (prop.title or '').lower().strip()
                                zoning = (prop.zoning or '').lower().strip()
                                
                                textos_busqueda = f'{description} {title} {zoning}'
                                es_terreno_texto = any(term in textos_busqueda for term in [
                                    'terreno', 'terrenos', 'lote', 'parcela', 'parcel',
                                    'land', 'lot', 'plot', 'ground', 'solar', 'vacant'
                                ])
                                
                                # Heurística basada en áreas
                                built_area_val = prop.built_area if prop.built_area else 0
                                land_area_val = prop.land_area if prop.land_area else 0
                                
                                es_terreno_heuristico = False
                                if land_area_val > 0:
                                    if built_area_val == 0 or built_area_val is None:
                                        es_terreno_heuristico = True
                                    elif land_area_val > built_area_val:
                                        es_terreno_heuristico = True
                                    elif land_area_val > 100:
                                        es_terreno_heuristico = True
                                
                                es_terreno = es_terreno_texto or es_terreno_heuristico
                                
                                # SI ES TERRENO: usar SOLO land_area
                                if es_terreno:
                                    if prop.land_area and prop.land_area > 0:
                                        area = float(prop.land_area)
                                else:
                                    # Para NO terrenos, priorizar built_area
                                    if prop.built_area and prop.built_area > 0:
                                        area = float(prop.built_area)
                                    elif prop.land_area and prop.land_area > 0:
                                        area = float(prop.land_area)
                                
                                precio_m2 = None
                                if area and prop.price:
                                    precio_m2 = float(prop.price) / area
                                
                                if precio_m2 and precio_m2 > 0 and precio_m2 < 10000:
                                    propiedades.append({
                                        'id': prop.id,
                                        'lat': lat,
                                        'lng': lng,
                                        'precio_m2': round(precio_m2, 2),
                                        'precio_usd': float(prop.price),
                                        'area': area,
                                        'tipo_propiedad': prop.property_type or '',
                                        'fuente': 'propifai',
                                        'weight': min(precio_m2 / 1000, 2.0)
                                    })
                    except (ValueError, AttributeError, TypeError):
                        continue
            
            # Calcular tiempo de ejecución
            end_time = time.time()
            execution_time = end_time - start_time
            
            # Si está en modo debug, incluir información adicional
            if debug_mode:
                return JsonResponse({
                    'status': 'success',
                    'data': propiedades,
                    'metadata': {
                        'total': len(propiedades),
                        'execution_time': round(execution_time, 3),
                        'filters': {
                            'tipo_propiedad': tipo_propiedad,
                            'precio_min': precio_min,
                            'precio_max': precio_max,
                            'area_min': area_min,
                            'area_max': area_max,
                            'fuente': fuente
                        }
                    }
                })
            
            return JsonResponse({
                'status': 'success',
                'data': propiedades,
                'total': len(propiedades)
            })
            
        except Exception as e:
            print(f"[ERROR API Heatmap] {e}")
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
            
    except Exception as e:
        print(f"[ERROR API Heatmap - General] {e}")
        return JsonResponse({
            'status': 'error',
            'message': 'Error interno del servidor'
        }, status=500)


def dashboard_view(request):
    """Vista para el dashboard del análisis de mercado"""
    print("[DEBUG] dashboard_view llamada")
    title = "Dashboard de Análisis de Mercado"
    
    try:
        # Contar todas las propiedades locales (sin filtrar por coordenadas)
        # Forzar uso de base de datos 'default'
        local_count = PropiedadRaw.objects.using('default').count()
        print(f"[DEBUG] local_count (todas, usando default): {local_count}")
    except Exception as e:
        print(f"[DEBUG] Error en local_count: {e}")
        local_count = 0
    
    try:
        # Contar propiedades Propify (usando coordinates en lugar de lat/lng)
        # Usar base de datos 'propifai' explícitamente
        propifai_count = PropifaiProperty.objects.using('propifai').filter(
            coordinates__isnull=False
        ).exclude(coordinates='').count()
        print(f"[DEBUG] propifai_count: {propifai_count}")
    except Exception as e:
        print(f"[DEBUG] Error en propifai_count: {e}")
        propifai_count = 0
    
    total_count = local_count + propifai_count
    
    context = {
        'title': title,
        'local_count': local_count,
        'propifai_count': propifai_count,
        'total_count': total_count,
    }
    
    print(f"[DEBUG] Contexto: {context}")
    return render(request, 'market_analysis/dashboard.html', context)


def api_dashboard_stats(request):
    """API para obtener estadísticas del dashboard."""
    print("[DEBUG] api_dashboard_stats llamada")
    
    try:
        # Contar todas las propiedades locales (sin filtrar por coordenadas)
        # Forzar uso de base de datos 'default'
        local_count = PropiedadRaw.objects.using('default').count()
        print(f"[DEBUG] api local_count (todas, usando default): {local_count}")
    except Exception as e:
        print(f"[DEBUG] Error en local_count: {e}")
        local_count = 0
    
    try:
        # Contar propiedades Propify
        propifai_count = PropifaiProperty.objects.using('propifai').filter(
            coordinates__isnull=False
        ).exclude(coordinates='').count()
    except Exception as e:
        print(f"[DEBUG] Error en propifai_count: {e}")
        propifai_count = 0
    
    total_count = local_count + propifai_count
    
    # Estadísticas adicionales con manejo de errores individual
    try:
        local_with_price = PropiedadRaw.objects.using('default').filter(precio_usd__isnull=False).exclude(precio_usd=0).count()
    except Exception as e:
        print(f"[DEBUG] Error en local_with_price: {e}")
        local_with_price = 0
    
    try:
        propifai_with_price = PropifaiProperty.objects.using('propifai').filter(price__isnull=False).exclude(price=0).count()
    except Exception as e:
        print(f"[DEBUG] Error en propifai_with_price: {e}")
        propifai_with_price = 0
    
    try:
        local_with_area = PropiedadRaw.objects.using('default').filter(area_construida__isnull=False).exclude(area_construida=0).count()
    except Exception as e:
        print(f"[DEBUG] Error en local_with_area: {e}")
        local_with_area = 0
    
    try:
        propifai_with_area = PropifaiProperty.objects.using('propifai').filter(built_area__isnull=False).exclude(built_area=0).count()
    except Exception as e:
        print(f"[DEBUG] Error en propifai_with_area: {e}")
        propifai_with_area = 0
    
    stats = {
        'local_count': local_count,
        'propifai_count': propifai_count,
        'total_count': total_count,
        'local_with_price': local_with_price,
        'propifai_with_price': propifai_with_price,
        'local_with_area': local_with_area,
        'propifai_with_area': propifai_with_area,
    }
    
    print(f"[DEBUG] Stats calculadas: {stats}")
    
    return JsonResponse({
        'success': True,
        'stats': stats,
        'timestamp': timezone.now().isoformat()
    })

def data_quality_dashboard(request):
    """Vista para el dashboard avanzado de calidad de datos y detección de anomalías."""
    print("[DEBUG] data_quality_dashboard llamada")
    title = "Dashboard de Calidad de Datos y Detección de Anomalías"
    
    try:
        # Obtener métricas de calidad de datos
        metrics = calculate_data_quality_metrics()
        
        # Obtener gráficos de calidad de datos
        charts = create_data_quality_summary()
        print(f"[DEBUG] Charts keys: {list(charts.keys())}")
        
        # Verificar estado de matplotlib
        matplotlib_available = charts.get('matplotlib_available', False)
        matplotlib_status = charts.get('matplotlib_status', 'Desconocido')
        print(f"[DEBUG] Matplotlib disponible: {matplotlib_available}, estado: {matplotlib_status}")
        
        # Contar gráficos válidos
        valid_charts = 0
        for key in ['local_completeness', 'propifai_completeness', 'local_outliers',
                   'propifai_outliers', 'local_duplicates', 'propifai_duplicates',
                   'local_empty_fields', 'propifai_empty_fields']:
            if key in charts and charts[key] and 'data:image' in charts[key]:
                valid_charts += 1
                print(f"[DEBUG] Gráfico {key} válido")
            else:
                print(f"[DEBUG] Gráfico {key} no válido o vacío")
        
        print(f"[DEBUG] Total gráficos válidos: {valid_charts}/8")
        
        # Obtener ejemplos de datos problemáticos
        from market_analysis.charts import get_problematic_examples
        problematic_examples = {
            'local': get_problematic_examples('local', limit=3),
            'propifai': get_problematic_examples('propifai', limit=3)
        }
        
        # Contar total de ejemplos problemáticos
        total_problems = 0
        for source in ['local', 'propifai']:
            for problem_type in problematic_examples[source].values():
                total_problems += len(problem_type)
        
        print(f"[DEBUG] Ejemplos problemáticos encontrados: {total_problems}")
        
        # Estadísticas básicas del dashboard actual
        try:
            local_count = PropiedadRaw.objects.using('default').count()
        except Exception as e:
            logger.error(f"Error en local_count: {e}")
            local_count = 0
            
        try:
            propifai_count = PropifaiProperty.objects.using('propifai').filter(
                coordinates__isnull=False
            ).exclude(coordinates='').count()
        except Exception as e:
            logger.error(f"Error en propifai_count: {e}")
            propifai_count = 0
        
        total_count = local_count + propifai_count
        
        # Calcular puntaje de calidad general
        overall_score = metrics['overall'].get('data_quality_score', 0) if metrics['overall'] else 0
        
        # Determinar estado de calidad
        if overall_score >= 80:
            quality_status = "Excelente"
            quality_color = "success"
        elif overall_score >= 60:
            quality_status = "Buena"
            quality_color = "info"
        elif overall_score >= 40:
            quality_status = "Regular"
            quality_color = "warning"
        else:
            quality_status = "Crítica"
            quality_color = "danger"
        
        # Calcular anchos para las barras de progreso (evitar problemas CSS)
        local_completeness_width = metrics.get('local', {}).get('avg_completeness', 0) or 0
        propifai_completeness_width = metrics.get('propifai', {}).get('avg_completeness', 0) or 0
        
        context = {
            'title': title,
            'local_count': local_count,
            'propifai_count': propifai_count,
            'total_count': total_count,
            'metrics': metrics,
            'charts': charts,
            'overall_score': round(overall_score, 1),
            'quality_status': quality_status,
            'quality_color': quality_color,
            'critical_issues': metrics['overall'].get('critical_issues', 0) if metrics['overall'] else 0,
            'warning_issues': metrics['overall'].get('warning_issues', 0) if metrics['overall'] else 0,
            'local_completeness_width': int(local_completeness_width),
            'propifai_completeness_width': int(propifai_completeness_width),
            'problematic_examples': problematic_examples,
            'total_problems': total_problems,
        }
        
        print(f"[DEBUG] Contexto data_quality_dashboard: {context.keys()}")
        print(f"[DEBUG] Total problemas encontrados: {total_problems}")
        return render(request, 'market_analysis/data_quality_dashboard_fixed.html', context)
        
    except Exception as e:
        logger.error(f"Error en data_quality_dashboard: {e}")
        import traceback
        traceback.print_exc()
        # Contexto de fallback
        context = {
            'title': title,
            'error': str(e),
            'local_count': 0,
            'propifai_count': 0,
            'total_count': 0,
            'overall_score': 0,
            'quality_status': "Error",
            'quality_color': "danger",
            'critical_issues': 1,
            'warning_issues': 0,
            'local_completeness_width': 0,
            'propifai_completeness_width': 0,
            'metrics': {'local': {}, 'propifai': {}, 'overall': {}},
            'charts': {},
        }
        return render(request, 'market_analysis/data_quality_dashboard_fixed.html', context)

def api_data_quality_metrics(request):
    """API para obtener métricas de calidad de datos en formato JSON."""
    try:
        metrics = calculate_data_quality_metrics()
        charts = create_data_quality_summary()
        
        return JsonResponse({
            'success': True,
            'metrics': metrics,
            'charts': list(charts.keys()),  # Solo nombres de gráficos
            'timestamp': timezone.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error en api_data_quality_metrics: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }, status=500)


def api_update_property_field(request):
    """API para actualizar un campo de propiedad desde el dashboard de calidad."""
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'error': 'Método no permitido. Use POST.'
        }, status=405)
    
    try:
        # Obtener datos del formulario
        property_id = request.POST.get('id')
        field_name = request.POST.get('field')
        field_value = request.POST.get('value')
        
        print(f"[DEBUG] api_update_property_field llamado")
        print(f"[DEBUG] Parámetros recibidos: id={property_id}, field={field_name}, value='{field_value}'")
        print(f"[DEBUG] Método: {request.method}, Content-Type: {request.content_type}")
        print(f"[DEBUG] POST data: {dict(request.POST)}")
        
        if not property_id or not field_name:
            print(f"[DEBUG] Error: Faltan parámetros. id={property_id}, field={field_name}")
            return JsonResponse({
                'success': False,
                'error': 'Faltan parámetros: id y field son requeridos.'
            }, status=400)
        
        # Buscar la propiedad en la base de datos local
        try:
            propiedad = PropiedadRaw.objects.get(id=property_id)
        except PropiedadRaw.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': f'Propiedad con ID {property_id} no encontrada.'
            }, status=404)
        
        # Validar y procesar el valor según el campo
        processed_value = None
        
        if field_name == 'coordenadas':
            # Validar formato de coordenadas
            if field_value:
                # Limpiar espacios
                coords = field_value.strip()
                print(f"[DEBUG] Coordenadas recibidas: '{coords}'")
                
                # Verificar formato básico: dos números separados por coma
                parts = coords.split(',')
                if len(parts) != 2:
                    print(f"[DEBUG] Error: Formato inválido, partes encontradas: {len(parts)}")
                    return JsonResponse({
                        'success': False,
                        'error': 'Formato de coordenadas inválido. Use: latitud, longitud (ejemplo: -12.046374, -77.042793)'
                    }, status=400)
                
                try:
                    lat = float(parts[0].strip())
                    lng = float(parts[1].strip())
                    print(f"[DEBUG] Coordenadas parseadas: lat={lat}, lng={lng}")
                    
                    # Validar rangos aproximados para Perú (más flexible)
                    # Perú: latitud entre -18.5 y 0, longitud entre -81.5 y -68.5
                    if not (-18.5 <= lat <= 0) or not (-81.5 <= lng <= -68.5):
                        print(f"[WARNING] Coordenadas fuera de rango Perú: {lat}, {lng}")
                        # Solo advertencia, no error - permitir guardar de todos modos
                        # pero mostrar mensaje informativo
                except ValueError as e:
                    print(f"[DEBUG] Error al convertir a float: {e}")
                    return JsonResponse({
                        'success': False,
                        'error': f'Coordenadas deben ser números válidos. Error: {str(e)}'
                    }, status=400)
                
                processed_value = coords
                print(f"[DEBUG] Valor procesado para coordenadas: {processed_value}")
        
        elif field_name == 'precio_usd':
            # Validar precio
            if not field_value:
                return JsonResponse({
                    'success': False,
                    'error': 'El precio no puede estar vacío.'
                }, status=400)
            
            try:
                precio = float(field_value)
                if precio <= 0:
                    return JsonResponse({
                        'success': False,
                        'error': 'El precio debe ser mayor a 0.'
                    }, status=400)
                processed_value = precio
            except ValueError:
                return JsonResponse({
                    'success': False,
                    'error': 'Precio debe ser un número válido.'
                }, status=400)
        
        elif field_name == 'area_construida':
            # Validar área
            if not field_value:
                return JsonResponse({
                    'success': False,
                    'error': 'El área no puede estar vacía.'
                }, status=400)
            
            try:
                area = float(field_value)
                if area <= 0:
                    return JsonResponse({
                        'success': False,
                        'error': 'El área debe ser mayor a 0.'
                    }, status=400)
                processed_value = area
            except ValueError:
                return JsonResponse({
                    'success': False,
                    'error': 'Área debe ser un número válido.'
                }, status=400)
        
        else:
            return JsonResponse({
                'success': False,
                'error': f'Campo {field_name} no permitido para edición.'
            }, status=400)
        
        # Actualizar el campo
        setattr(propiedad, field_name, processed_value)
        propiedad.save()
        
        # Registrar la acción
        logger.info(f"Campo actualizado: Propiedad {property_id}, campo {field_name} = {processed_value}")
        
        return JsonResponse({
            'success': True,
            'message': f'Campo {field_name} actualizado correctamente.',
            'property_id': property_id,
            'field': field_name,
            'value': processed_value
        })
        
    except Exception as e:
        logger.error(f"Error en api_update_property_field: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


def property_quick_detail(request, property_id):
    """Vista simple para mostrar detalles básicos de una propiedad (alternativa a la vista rota)."""
    try:
        # Buscar la propiedad
        propiedad = PropiedadRaw.objects.get(id=property_id)
        
        # Obtener todos los campos disponibles
        fields = []
        for field in propiedad._meta.fields:
            field_name = field.name
            field_value = getattr(propiedad, field_name)
            
            # Saltar campos vacíos o nulos
            if field_value is None or field_value == '':
                continue
                
            # Formatear valores
            if isinstance(field_value, (int, float)):
                field_value = str(field_value)
            elif isinstance(field_value, bool):
                field_value = "Sí" if field_value else "No"
            elif hasattr(field_value, 'strftime'):  # Fechas
                field_value = field_value.strftime('%Y-%m-%d')
            
            fields.append({
                'name': field_name.replace('_', ' ').title(),
                'value': field_value,
                'original_name': field_name
            })
        
        # Agrupar campos por categoría
        basic_fields = ['id', 'fuente_excel', 'identificador_externo', 'tipo_propiedad', 'subtipo_propiedad', 'descripcion', 'condicion', 'estado', 'operacion', 'tipo_operacion', 'venta_alquiler', 'propiedad_verificada']
        location_fields = ['distrito', 'provincia', 'departamento', 'direccion', 'coordenadas']
        price_fields = ['precio_usd', 'precio_soles', 'moneda', 'precio_original']
        area_fields = ['area_construida', 'area_terreno', 'area_total', 'unidad_area']
        other_fields = ['habitaciones', 'banos', 'estacionamientos', 'antiguedad', 'piso']
        
        # Incluir campos adicionales importantes
        extra_fields = ['subtipo_propiedad', 'fuente_excel', 'identificador_externo', 'portal', 'url_propiedad', 'operacion', 'tipo_operacion', 'venta_alquiler', 'propiedad_verificada']
        for field_name in extra_fields:
            if hasattr(propiedad, field_name):
                field_value = getattr(propiedad, field_name)
                if field_value not in (None, ''):
                    fields.append({
                        'name': field_name.replace('_', ' ').title(),
                        'value': field_value,
                        'original_name': field_name
                    })
        
        # Incluir campos dinámicos de atributos_extras (JSON)
        if propiedad.atributos_extras and isinstance(propiedad.atributos_extras, dict):
            for key, value in propiedad.atributos_extras.items():
                if value not in (None, ''):
                    fields.append({
                        'name': key.replace('_', ' ').title(),
                        'value': str(value),
                        'original_name': key
                    })
        
        # Verificar si se solicita formato JSON
        if request.GET.get('format') == 'json':
            # Preparar datos para JSON
            property_data = {
                'id': propiedad.id,
                'fields': fields,
                'grouped_fields': {
                    'basic': [f for f in fields if f['original_name'] in basic_fields],
                    'location': [f for f in fields if f['original_name'] in location_fields],
                    'price': [f for f in fields if f['original_name'] in price_fields],
                    'area': [f for f in fields if f['original_name'] in area_fields],
                    'other': [f for f in fields if f['original_name'] in other_fields],
                    'extra': [f for f in fields if f['original_name'] in extra_fields]
                }
            }
            return JsonResponse(property_data)
        
        context = {
            'title': f'Propiedad ID: {property_id}',
            'propiedad': propiedad,
            'fields': fields,
            'basic_fields': [f for f in fields if f['original_name'] in basic_fields],
            'location_fields': [f for f in fields if f['original_name'] in location_fields],
            'price_fields': [f for f in fields if f['original_name'] in price_fields],
            'area_fields': [f for f in fields if f['original_name'] in area_fields],
            'other_fields': [f for f in fields if f['original_name'] in other_fields],
        }
        
        return render(request, 'market_analysis/property_quick_detail.html', context)
        
    except PropiedadRaw.DoesNotExist:
        if request.GET.get('format') == 'json':
            return JsonResponse({'error': f'La propiedad con ID {property_id} no existe.'}, status=404)
        return render(request, 'market_analysis/property_quick_detail.html', {
            'title': 'Propiedad no encontrada',
            'error': f'La propiedad con ID {property_id} no existe.'
        })
    except Exception as e:
        logger.error(f"Error en property_quick_detail: {e}")
        if request.GET.get('format') == 'json':
            return JsonResponse({'error': str(e)}, status=500)
        return render(request, 'market_analysis/property_quick_detail.html', {
            'title': 'Error',
            'error': str(e)
        })
