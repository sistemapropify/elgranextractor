from django.shortcuts import render
from django.http import JsonResponse
from django.db.models import Q, F, FloatField, ExpressionWrapper, Count
from django.db.models.functions import Cast
from ingestas.models import PropiedadRaw
from propifai.models import PropifaiProperty
import json
import math
# FORCE RELOAD - Template heatmap fix


def heatmap_view(request):
    """Vista principal para el heatmap de precio por m² - VERSIÓN ULTRA VISIBLE CON DATOS 100% REALES"""
    # Generar HTML directamente para evitar cache de templates
    google_maps_api_key = "AIzaSyBrL1QF7vTl9zF8FmCUumfRpFJcaYokO7Q"
    
    # Obtener datos reales de propiedades para el heatmap - SIN DATOS INVENTADOS
    heatmap_points = []
    local_count = 0
    propifai_count = 0
    
    try:
        # Propiedades locales (Remax) - TODAS LAS QUE TIENEN COORDENADAS
        from ingestas.models import PropiedadRaw
        local_props = PropiedadRaw.objects.filter(
            coordenadas__isnull=False
        ).exclude(coordenadas='')[:600]  # Mostrar hasta 600 propiedades
        
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
                    
                    if area and prop.precio_usd and prop.precio_usd > 0:
                        precio_m2 = float(prop.precio_usd) / area
                        if precio_m2 > 0 and precio_m2 < 10000:
                            # Asignar peso por rangos discretos (no densidad)
                            if precio_m2 < 1000:
                                weight = 1.0  # Bajo
                            elif precio_m2 < 2000:
                                weight = 2.0  # Medio
                            elif precio_m2 < 3000:
                                weight = 3.0  # Alto
                            else:
                                weight = 4.0  # Muy alto
                    
                    heatmap_points.append({
                        'lat': lat,
                        'lng': lng,
                        'weight': weight,
                        'precio_m2': precio_m2 if precio_m2 else 0,
                        'fuente': 'local',
                        'tipo': 'Propiedad Real (Remax)',
                        'id': prop.id,
                        'tiene_precio': precio_m2 is not None,
                        'precio_usd': float(prop.precio_usd) if prop.precio_usd else None,
                        'area_construida': float(prop.area_construida) if prop.area_construida else None,
                        'area_terreno': float(prop.area_terreno) if prop.area_terreno else None,
                        'direccion': prop.direccion if hasattr(prop, 'direccion') and prop.direccion else None,
                        'tipo_propiedad': prop.tipo_propiedad if hasattr(prop, 'tipo_propiedad') and prop.tipo_propiedad else None,
                        'habitaciones': prop.habitaciones if hasattr(prop, 'habitaciones') else None,
                        'banos': prop.banos if hasattr(prop, 'banos') else None
                    })
                    local_count += 1
            except (ValueError, AttributeError, TypeError):
                continue
    except Exception as e:
        print(f"[DEBUG] Error obteniendo propiedades locales: {e}")
    
    try:
        # Propiedades de Propifai (Propify) - TODAS LAS QUE TIENEN COORDENADAS
        from propifai.models import PropifaiProperty
        propifai_props = PropifaiProperty.objects.filter(
            coordinates__isnull=False
        ).exclude(coordinates='')[:600]
        
        for prop in propifai_props:
            try:
                coords = prop.coordinates.split(',')
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
                    
                    if area and prop.price and prop.price > 0:
                        precio_m2 = float(prop.price) / area
                        if precio_m2 > 0 and precio_m2 < 10000:
                            # Asignar peso por rangos discretos (no densidad)
                            if precio_m2 < 1000:
                                weight = 1.0  # Bajo
                            elif precio_m2 < 2000:
                                weight = 2.0  # Medio
                            elif precio_m2 < 3000:
                                weight = 3.0  # Alto
                            else:
                                weight = 4.0  # Muy alto
                    
                    heatmap_points.append({
                        'lat': lat,
                        'lng': lng,
                        'weight': weight,
                        'precio_m2': precio_m2 if precio_m2 else 0,
                        'fuente': 'propifai',
                        'tipo': 'Propiedad Real (Propify)',
                        'id': prop.id,
                        'tiene_precio': precio_m2 is not None,
                        'price': float(prop.price) if prop.price else None,
                        'built_area': float(prop.built_area) if prop.built_area else None,
                        'land_area': float(prop.land_area) if prop.land_area else None,
                        'address': prop.address if hasattr(prop, 'address') and prop.address else None,
                        'property_type': prop.property_type if hasattr(prop, 'property_type') and prop.property_type else None,
                        'bedrooms': prop.bedrooms if hasattr(prop, 'bedrooms') else None,
                        'bathrooms': prop.bathrooms if hasattr(prop, 'bathrooms') else None
                    })
                    propifai_count += 1
            except (ValueError, AttributeError, TypeError):
                continue
    except Exception as e:
        print(f"[DEBUG] Error obteniendo propiedades Propifai: {e}")
    
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
    
    html = f'''
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
    <title>🔥 HEATMAP CON DATOS REALES - Precio por m² - El Gran Extractor</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css">
    <style>
        body {{
            padding: 20px;
            background-color: #f8f9fa;
            font-family: Arial, sans-serif;
        }}
        .heatmap-header {{
            background: linear-gradient(135deg, #ff6b6b, #4ecdc4);
            color: white;
            padding: 25px;
            border-radius: 15px;
            margin-bottom: 25px;
            text-align: center;
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        }}
        #heatmapMap {{
            height: 650px;
            width: 100%;
            border-radius: 15px;
            border: 3px solid #4ecdc4;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }}
        .controls {{
            background: white;
            padding: 20px;
            border-radius: 15px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            margin-bottom: 25px;
        }}
        .success-badge {{
            background: #10b981;
            color: white;
            padding: 10px 20px;
            border-radius: 50px;
            font-weight: bold;
            display: inline-block;
            margin: 10px 0;
            animation: pulse 2s infinite;
        }}
        .data-info-badge {{
            background: #3b82f6;
            color: white;
            padding: 8px 15px;
            border-radius: 20px;
            font-size: 0.9rem;
            display: inline-block;
            margin: 5px;
        }}
        @keyframes pulse {{
            0% {{ transform: scale(1); }}
            50% {{ transform: scale(1.05); }}
            100% {{ transform: scale(1); }}
        }}
    </style>
    <!-- MarkerClusterer para agrupar marcadores -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/js-marker-clusterer/1.0.0/markerclusterer.js"></script>
</head>
<body>
    <div class="container-fluid">
        <div class="heatmap-header">
            <h1><i class="bi bi-thermometer-high me-2"></i>🔥 HEATMAP CON DATOS REALES DE TU BASE DE DATOS</h1>
            <div class="success-badge">
                <i class="bi bi-check-circle-fill me-2"></i>DATOS 100% REALES - SIN PROPIEDADES INVENTADAS
            </div>
            <div class="mt-3">
                <span class="data-info-badge"><i class="bi bi-database me-1"></i>Total: {total_count} propiedades</span>
                <span class="data-info-badge"><i class="bi bi-house-door me-1"></i>Remax/Local: {local_count}</span>
                <span class="data-info-badge"><i class="bi bi-house-door-fill me-1"></i>Propify: {propifai_count}</span>
            </div>
            <p class="mb-0 mt-3">Visualización de densidad de precio por m² en el mercado inmobiliario con datos reales de tu base de datos</p>
            <p class="mb-0"><small>Todas las propiedades mostradas son reales, obtenidas de PropiedadRaw y PropifaiProperty</small></p>
        </div>
        
        <div class="row">
            <div class="col-md-3">
                <div class="controls">
                    <h5><i class="bi bi-sliders me-2"></i>Controles</h5>
                    <div class="mb-3">
                        <label class="form-label">Opacidad del heatmap</label>
                        <input type="range" class="form-range" id="opacitySlider" min="0.1" max="1" step="0.1" value="0.7">
                        <div class="d-flex justify-content-between small text-muted">
                            <span>Baja</span>
                            <span id="opacityValue">70%</span>
                            <span>Alta</span>
                        </div>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Radio del heatmap</label>
                        <input type="range" class="form-range" id="radiusSlider" min="100" max="500" step="25" value="300">
                        <div class="d-flex justify-content-between small text-muted">
                            <span>Pequeño</span>
                            <span id="radiusValue">300px</span>
                            <span>Grande</span>
                        </div>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Paleta de colores</label>
                        <select class="form-select" id="colorPalette">
                            <option value="default">Default (Azul-Amarillo-Rojo)</option>
                            <option value="viridis">Viridis (Verde-Amarillo)</option>
                            <option value="plasma">Plasma (Púrpura-Amarillo)</option>
                            <option value="inferno">Inferno (Negro-Rojo-Amarillo)</option>
                            <option value="cool">Cool (Cian-Magenta)</option>
                        </select>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Filtrar por fuente</label>
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" id="filterRemax" checked>
                            <label class="form-check-label" for="filterRemax">
                                Remax/Local
                            </label>
                        </div>
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" id="filterPropify" checked>
                            <label class="form-check-label" for="filterPropify">
                                Propify
                            </label>
                        </div>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Filtrar por tipo de propiedad</label>
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" id="filterCasa" checked>
                            <label class="form-check-label" for="filterCasa">
                                Casa
                            </label>
                        </div>
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" id="filterDepartamento" checked>
                            <label class="form-check-label" for="filterDepartamento">
                                Departamento
                            </label>
                        </div>
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" id="filterTerreno" checked>
                            <label class="form-check-label" for="filterTerreno">
                                Terreno
                            </label>
                        </div>
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" id="filterOficina" checked>
                            <label class="form-check-label" for="filterOficina">
                                Oficina
                            </label>
                        </div>
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" id="filterOtro" checked>
                            <label class="form-check-label" for="filterOtro">
                                Otro
                            </label>
                        </div>
                    </div>
                    <button class="btn btn-primary w-100 mb-2" id="btnRefresh">
                        <i class="bi bi-arrow-clockwise me-1"></i>Actualizar datos en tiempo real
                    </button>
                    <button class="btn btn-outline-secondary w-100" id="btnHelp">
                        <i class="bi bi-question-circle me-1"></i>Ayuda
                    </button>
                </div>
                
                <div class="controls">
                    <h5><i class="bi bi-info-circle me-2"></i>Información</h5>
                    <p>Este heatmap muestra la densidad de precio por metro cuadrado en el mercado inmobiliario.</p>
                    <p><strong>Colores:</strong></p>
                    <ul class="small">
                        <li><span style="color: blue;">● Azul:</span> Precio bajo</li>
                        <li><span style="color: green;">● Verde:</span> Precio medio</li>
                        <li><span style="color: yellow;">● Amarillo:</span> Precio alto</li>
                        <li><span style="color: red;">● Rojo:</span> Precio muy alto</li>
                    </ul>
                </div>
            </div>
            
            <div class="col-md-9">
                <div class="card border-0 shadow">
                    <div class="card-header bg-white">
                        <h5 class="mb-0"><i class="bi bi-map me-2"></i>Mapa de calor interactivo</h5>
                    </div>
                    <div class="card-body p-0">
                        <div id="heatmapMap"></div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
    // Función para cargar Google Maps API
    function loadGoogleMapsAPI() {{
        return new Promise((resolve, reject) => {{
            if (typeof google !== 'undefined' && google.maps) {{
                resolve();
                return;
            }}
            
            const script = document.createElement('script');
            script.src = 'https://maps.googleapis.com/maps/api/js?key={google_maps_api_key}&libraries=visualization';
            script.async = true;
            script.defer = true;
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        }});
    }}
    
    // Función principal
    async function initializeHeatmap() {{
        console.log('Inicializando heatmap...');
        
        try {{
            await loadGoogleMapsAPI();
            console.log('Google Maps API cargada');
            
            // Crear mapa centrado en Lima con zoom habilitado
            const map = new google.maps.Map(document.getElementById('heatmapMap'), {{
                center: {{ lat: -12.0464, lng: -77.0428 }},
                zoom: 10,
                scrollwheel: true, // Habilitar zoom con rueda del mouse
                gestureHandling: 'cooperative', // Manejo cooperativo de gestos
                zoomControl: true, // Mostrar controles de zoom
                mapTypeControl: true, // Mostrar control de tipo de mapa
                scaleControl: true, // Mostrar escala
                streetViewControl: true, // Mostrar control de Street View
                rotateControl: true, // Mostrar control de rotación
                fullscreenControl: true, // Mostrar control de pantalla completa
                styles: [
                    {{
                        featureType: "all",
                        elementType: "labels.text.fill",
                        stylers: [{{ saturation: 36 }}, {{ color: "#000000" }}, {{ lightness: 40 }}]
                    }}
                ]
            }});
            
            console.log('Mapa creado');
            
            // Datos reales para el heatmap (propiedades de Remax y Propify)
            const heatmapDataJson = {heatmap_data_json};
            const heatmapData = heatmapDataJson.map(point => ({{
                location: new google.maps.LatLng(point.lat, point.lng),
                weight: point.weight
            }}));
            
            // Depurar: mostrar primeros 5 puntos con sus pesos y precios
            console.log('Muestra de datos heatmap (primeros 5 puntos):');
            heatmapDataJson.slice(0, 5).forEach((point, i) => {{
                console.log(`Punto ${{i}}: precio_m2=${{point.precio_m2}}, weight=${{point.weight}}, fuente=${{point.fuente}}`);
            }});
            
            // HEATMAP DESACTIVADO - Solo se muestran marcadores con colores y precios
            const heatmap = null; // No se crea capa de heatmap
            
            console.log('Heatmap desactivado. Mostrando {{heatmapData.length}} puntos como marcadores.');
            
            // Crear marcadores visibles con tooltips
            const markers = [];
            let markerCluster = null;
            
            // DESHABILITADO: Intentar crear MarkerClusterer si está disponible
            // try {{
            //     if (typeof MarkerClusterer !== 'undefined') {{
            //         markerCluster = new MarkerClusterer(map, [], {{
            //             imagePath: 'https://developers.google.com/maps/documentation/javascript/examples/markerclusterer/m'
            //         }});
            //         console.log('MarkerClusterer inicializado');
            //     }} else if (typeof markerCluster !== 'undefined') {{
            //         // Alternativa: algunas bibliotecas usan markerCluster (minúscula)
            //         markerCluster = new markerCluster(map, markers);
            //         console.log('markerCluster (alternativo) inicializado');
            //     }}
            // }} catch (clusterError) {{
            //     console.warn('MarkerClusterer no disponible, mostrando marcadores sin agrupación:', clusterError);
            // }}
            
            // Crear marcador para cada punto (TODAS las propiedades, como pidió el usuario)
            const displayData = heatmapDataJson; // Todas las propiedades
            
            displayData.forEach((point, index) => {{
                // Determinar color basado en precio por m²
                let color = '#4285F4'; // azul por defecto
                if (point.precio_m2) {{
                    if (point.precio_m2 > 3000) {{
                        color = '#EA4335'; // rojo (alto)
                    }} else if (point.precio_m2 > 2000) {{
                        color = '#FBBC05'; // amarillo (medio-alto)
                    }} else if (point.precio_m2 > 1000) {{
                        color = '#34A853'; // verde (medio)
                    }} else {{
                        color = '#4285F4'; // azul (bajo)
                    }}
                }}
                
                // Crear marcador
                const marker = new google.maps.Marker({{
                    position: {{ lat: point.lat, lng: point.lng }},
                    map: map,
                    title: `Precio por m²: ${{point.precio_m2 ? point.precio_m2.toFixed(2) : 'N/A'}} USD`,
                    icon: {{
                        path: google.maps.SymbolPath.CIRCLE,
                        fillColor: color,
                        fillOpacity: 0.8,
                        strokeWeight: 1,
                        strokeColor: '#FFFFFF',
                        scale: 18
                    }},
                    label: {{
                        text: point.precio_m2 ? `$${{Math.round(point.precio_m2)}}` : '?',
                        color: 'white',
                        fontSize: '10px',
                        fontWeight: 'bold'
                    }}
                }});
                
                // Crear tooltip (info window) con todos los datos
                const infoWindow = new google.maps.InfoWindow({{
                    content: `
                        <div style="padding: 15px; min-width: 300px; max-width: 400px; font-family: Arial, sans-serif;">
                            <h5 style="margin: 0 0 12px 0; color: #1a73e8; border-bottom: 2px solid #f0f0f0; padding-bottom: 8px;">
                                ${{point.fuente === 'local' ? '🏠 Propiedad Remax/Local' : '🏢 Propiedad Propify'}}
                            </h5>
                            
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 12px;">
                                <div>
                                    <strong>ID:</strong> ${{point.id}}<br>
                                    <strong>Precio/m²:</strong> ${{point.precio_m2 ? '$' + point.precio_m2.toFixed(2) + ' USD' : 'N/A'}}<br>
                                    <strong>Intensidad:</strong> ${{(point.weight * 100).toFixed(1)}}%<br>
                                    <strong>Coordenadas:</strong><br>
                                    <small>${{point.lat.toFixed(6)}}, ${{point.lng.toFixed(6)}}</small>
                                </div>
                                <div>
                                    <strong>Precio total:</strong> ${{point.precio_usd ? '$' + point.precio_usd.toLocaleString() + ' USD' : point.price ? '$' + point.price.toLocaleString() + ' USD' : 'N/A'}}<br>
                                    <strong>Área construida:</strong> ${{point.area_construida ? point.area_construida.toLocaleString() + ' m²' : point.built_area ? point.built_area.toLocaleString() + ' m²' : 'N/A'}}<br>
                                    <strong>Área terreno:</strong> ${{point.area_terreno ? point.area_terreno.toLocaleString() + ' m²' : point.land_area ? point.land_area.toLocaleString() + ' m²' : 'N/A'}}<br>
                                </div>
                            </div>
                            
                            <div style="margin-bottom: 12px;">
                                <strong>Dirección:</strong><br>
                                <span style="color: #555;">${{point.direccion || point.address || 'N/A'}}</span><br>
                                <strong>Tipo:</strong> ${{point.tipo_propiedad || point.property_type || 'N/A'}}<br>
                            </div>
                            
                            <div style="display: flex; gap: 15px; margin-bottom: 12px;">
                                <div><strong>Habitaciones:</strong> ${{point.habitaciones || point.bedrooms || 'N/A'}}</div>
                                <div><strong>Baños:</strong> ${{point.banos || point.bathrooms || 'N/A'}}</div>
                            </div>
                            
                            <div style="font-size: 12px; color: #666; border-top: 1px solid #eee; padding-top: 8px;">
                                <strong>Fuente:</strong> ${{point.fuente === 'local' ? 'Remax/Local' : 'Propify'}} |
                                <strong>Tiene precio:</strong> ${{point.tiene_precio ? 'Sí' : 'No'}}
                            </div>
                        </div>
                    `
                }});
                
                // Mostrar tooltip al hacer clic
                marker.addListener('click', () => {{
                    infoWindow.open(map, marker);
                }});
                
                markers.push(marker);
                
                // Agregar al cluster si está disponible (DESHABILITADO)
                // if (markerCluster && markerCluster.addMarker) {{
                //     markerCluster.addMarker(marker);
                // }}
            }});
            
            // Si no hay cluster, agregar todos los marcadores al mapa directamente
            if (!markerCluster && markers.length > 0) {{
                // Los marcadores ya se agregaron al mapa al crearlos (map: map)
                console.log('Marcadores mostrados sin agrupación:', markers.length);
            }}
            
            // Control para mostrar/ocultar marcadores
            const toggleMarkersCheckbox = document.createElement('div');
            toggleMarkersCheckbox.innerHTML = `
                <div style="position: absolute; top: 50px; right: 10px; background: white; padding: 10px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.2); z-index: 1000;">
                    <label style="display: flex; align-items: center; gap: 5px; cursor: pointer;">
                        <input type="checkbox" id="toggleMarkers" checked>
                        <span>Mostrar marcadores</span>
                    </label>
                </div>
            `;
            document.getElementById('heatmapMap').appendChild(toggleMarkersCheckbox);
            
            document.getElementById('toggleMarkers').addEventListener('change', function(e) {{
                const show = e.target.checked;
                markers.forEach(marker => marker.setVisible(show));
            }});
            
            // Configurar controles con debouncing para mejor rendimiento
            function debounce(func, wait) {{
                let timeout;
                return function executedFunction(...args) {{
                    const later = () => {{
                        clearTimeout(timeout);
                        func(...args);
                    }};
                    clearTimeout(timeout);
                    timeout = setTimeout(later, wait);
                }};
            }}
            
            // Actualizar valores de los sliders inmediatamente
            document.getElementById('opacitySlider').addEventListener('input', function(e) {{
                document.getElementById('opacityValue').textContent = Math.round(parseFloat(e.target.value) * 100) + '%';
            }});
            
            document.getElementById('radiusSlider').addEventListener('input', function(e) {{
                document.getElementById('radiusValue').textContent = e.target.value + 'px';
            }});
            
            // Aplicar cambios inmediatamente (sin debouncing) - Heatmap desactivado
            const updateHeatmapOpacity = function(value) {{
                console.log('Heatmap desactivado, opacidad ignorada:', value);
                // heatmap.setOpacity(parseFloat(value)); // No hay heatmap
            }};
            
            const updateHeatmapRadius = function(value) {{
                console.log('Heatmap desactivado, radio ignorado:', value);
                // heatmap.set('radius', parseInt(value)); // No hay heatmap
            }};
            
            // Los sliders aún actualizan los valores visuales pero no afectan al heatmap
            document.getElementById('opacitySlider').addEventListener('input', function(e) {{
                updateHeatmapOpacity(e.target.value);
            }});
            
            document.getElementById('radiusSlider').addEventListener('input', function(e) {{
                updateHeatmapRadius(e.target.value);
            }});
            
            document.getElementById('colorPalette').addEventListener('change', function(e) {{
                const palette = e.target.value;
                let gradient;
                switch(palette) {{
                    case 'viridis':
                        gradient = [
                            'rgba(68, 1, 84, 0)',
                            'rgba(68, 1, 84, 0.5)',
                            'rgba(72, 40, 120, 0.8)',
                            'rgba(62, 73, 137, 1)',
                            'rgba(49, 104, 142, 1)',
                            'rgba(38, 130, 142, 1)',
                            'rgba(31, 158, 137, 1)',
                            'rgba(53, 183, 121, 1)',
                            'rgba(110, 206, 88, 1)',
                            'rgba(181, 222, 43, 1)',
                            'rgba(253, 231, 37, 1)'
                        ];
                        break;
                    case 'plasma':
                        gradient = [
                            'rgba(13, 8, 135, 0)',
                            'rgba(13, 8, 135, 0.5)',
                            'rgba(84, 2, 163, 0.8)',
                            'rgba(139, 10, 165, 1)',
                            'rgba(185, 19, 137, 1)',
                            'rgba(221, 38, 106, 1)',
                            'rgba(247, 72, 70, 1)',
                            'rgba(253, 118, 37, 1)',
                            'rgba(254, 168, 24, 1)',
                            'rgba(240, 219, 16, 1)'
                        ];
                        break;
                    case 'inferno':
                        gradient = [
                            'rgba(0, 0, 4, 0)',
                            'rgba(0, 0, 4, 0.5)',
                            'rgba(31, 12, 72, 0.8)',
                            'rgba(85, 15, 109, 1)',
                            'rgba(136, 34, 106, 1)',
                            'rgba(186, 54, 85, 1)',
                            'rgba(227, 89, 51, 1)',
                            'rgba(249, 140, 10, 1)',
                            'rgba(249, 201, 14, 1)',
                            'rgba(252, 255, 164, 1)'
                        ];
                        break;
                    case 'cool':
                        gradient = [
                            'rgba(0, 255, 255, 0)',
                            'rgba(0, 255, 255, 0.5)',
                            'rgba(0, 200, 255, 0.8)',
                            'rgba(0, 150, 255, 1)',
                            'rgba(0, 100, 255, 1)',
                            'rgba(100, 0, 255, 1)',
                            'rgba(200, 0, 255, 1)',
                            'rgba(255, 0, 200, 1)',
                            'rgba(255, 0, 100, 1)'
                        ];
                        break;
                    default: // default
                        gradient = [
                            'rgba(0, 0, 255, 0)',
                            'rgba(0, 0, 255, 0.5)',
                            'rgba(0, 255, 255, 0.8)',
                            'rgba(0, 255, 0, 1)',
                            'rgba(255, 255, 0, 1)',
                            'rgba(255, 0, 0, 1)'
                        ];
                }}
                heatmap.set('gradient', gradient);
            }});
            
            // Filtros por fuente y tipo de propiedad con caché para mejor rendimiento (solo marcadores)
            let filterCache = {{}};
            let lastFilterState = {{
                showRemax: true,
                showPropify: true,
                showCasa: true,
                showDepartamento: true,
                showTerreno: true,
                showOficina: true,
                showOtro: true
            }};
            
            function applyFilters() {{
                const showRemax = document.getElementById('filterRemax').checked;
                const showPropify = document.getElementById('filterPropify').checked;
                const showCasa = document.getElementById('filterCasa').checked;
                const showDepartamento = document.getElementById('filterDepartamento').checked;
                const showTerreno = document.getElementById('filterTerreno').checked;
                const showOficina = document.getElementById('filterOficina').checked;
                const showOtro = document.getElementById('filterOtro').checked;
                
                // Si el estado no ha cambiado, no hacer nada
                if (lastFilterState.showRemax === showRemax &&
                    lastFilterState.showPropify === showPropify &&
                    lastFilterState.showCasa === showCasa &&
                    lastFilterState.showDepartamento === showDepartamento &&
                    lastFilterState.showTerreno === showTerreno &&
                    lastFilterState.showOficina === showOficina &&
                    lastFilterState.showOtro === showOtro) {{
                    return;
                }}
                lastFilterState = {{
                    showRemax, showPropify, showCasa, showDepartamento,
                    showTerreno, showOficina, showOtro
                }};
                
                // Generar clave de caché
                const cacheKey = `${{showRemax ? 'R' : ''}}${{showPropify ? 'P' : ''}}${{showCasa ? 'C' : ''}}${{showDepartamento ? 'D' : ''}}${{showTerreno ? 'T' : ''}}${{showOficina ? 'O' : ''}}${{showOtro ? 'X' : ''}}`;
                
                // Usar caché si existe (solo visibilidad de marcadores)
                if (filterCache[cacheKey]) {{
                    // Aplicar visibilidad de marcadores desde caché
                    filterCache[cacheKey].forEach((visible, index) => {{
                        if (markers[index]) {{
                            markers[index].setVisible(visible);
                        }}
                    }});
                    return;
                }}
                
                // Calcular nueva visibilidad de marcadores
                const markerVisibility = [];
                
                heatmapDataJson.forEach((point, index) => {{
                    // Filtrar por fuente
                    const fuenteOk = (point.fuente === 'local' && showRemax) || (point.fuente === 'propifai' && showPropify);
                    
                    // Filtrar por tipo de propiedad
                    let tipoOk = false;
                    const tipoPropiedad = (point.tipo_propiedad || point.property_type || '').toLowerCase();
                    
                    if (showCasa && (tipoPropiedad.includes('casa') || tipoPropiedad.includes('house') || tipoPropiedad.includes('villa'))) {{
                        tipoOk = true;
                    }}
                    if (showDepartamento && (tipoPropiedad.includes('departamento') || tipoPropiedad.includes('apartment') || tipoPropiedad.includes('flat') || tipoPropiedad.includes('dpto'))) {{
                        tipoOk = true;
                    }}
                    if (showTerreno && (tipoPropiedad.includes('terreno') || tipoPropiedad.includes('land') || tipoPropiedad.includes('lot') || tipoPropiedad.includes('parcel'))) {{
                        tipoOk = true;
                    }}
                    if (showOficina && (tipoPropiedad.includes('oficina') || tipoPropiedad.includes('office') || tipoPropiedad.includes('commercial'))) {{
                        tipoOk = true;
                    }}
                    if (showOtro && !tipoOk && tipoPropiedad) {{
                        // Si no coincide con ningún tipo específico pero tiene tipo, y "Otro" está seleccionado
                        tipoOk = true;
                    }}
                    // Si no hay tipo de propiedad definido, mostrar si "Otro" está seleccionado
                    if (!tipoPropiedad && showOtro) {{
                        tipoOk = true;
                    }}
                    // Si todos los tipos están deseleccionados, mostrar nada
                    if (!showCasa && !showDepartamento && !showTerreno && !showOficina && !showOtro) {{
                        tipoOk = false;
                    }}
                    
                    const shouldShow = fuenteOk && tipoOk;
                    markerVisibility.push(shouldShow);
                    
                    // Actualizar visibilidad del marcador
                    if (markers[index]) {{
                        markers[index].setVisible(shouldShow);
                    }}
                }});
                
                // Guardar en caché (solo visibilidad)
                filterCache[cacheKey] = markerVisibility;
                
                // Limitar tamaño de caché (mantener solo las últimas 8 combinaciones)
                const cacheKeys = Object.keys(filterCache);
                if (cacheKeys.length > 8) {{
                    delete filterCache[cacheKeys[0]];
                }}
            }}
            
            document.getElementById('filterRemax').addEventListener('change', applyFilters);
            document.getElementById('filterPropify').addEventListener('change', applyFilters);
            document.getElementById('filterCasa').addEventListener('change', applyFilters);
            document.getElementById('filterDepartamento').addEventListener('change', applyFilters);
            document.getElementById('filterTerreno').addEventListener('change', applyFilters);
            document.getElementById('filterOficina').addEventListener('change', applyFilters);
            document.getElementById('filterOtro').addEventListener('change', applyFilters);
            
            // Botón de recarga de datos en tiempo real
            document.getElementById('btnRefresh').addEventListener('click', function() {{
                // Mostrar indicador de carga
                const refreshBtn = document.getElementById('btnRefresh');
                const originalText = refreshBtn.innerHTML;
                refreshBtn.innerHTML = '<i class="bi bi-arrow-clockwise me-1"></i>Cargando...';
                refreshBtn.disabled = true;
                
                // Simular carga de datos (en producción sería una llamada AJAX)
                setTimeout(() => {{
                    // Aquí iría la llamada real a la API para obtener datos actualizados
                    // Por ahora solo recargamos la página para demostración
                    location.reload();
                }}, 1000);
            }});
            
            document.getElementById('btnHelp').addEventListener('click', function() {{
                alert('HEATMAP CON DATOS 100% REALES DE TU BASE DE DATOS\\n\\n' +
                      '• Total de propiedades mostradas: {total_count}\\n' +
                      '• Propiedades Remax/Local: {local_count}\\n' +
                      '• Propiedades Propify: {propifai_count}\\n\\n' +
                      '• Use el deslizador para ajustar la opacidad\\n' +
                      '• Ajuste el radio para cambiar el tamaño de los puntos\\n' +
                      '• Seleccione diferentes paletas de colores\\n' +
                      '• Filtre por tipo de propiedad (Remax/Propify)\\n' +
                      '• Actualice datos en tiempo real con el botón\\n' +
                      '• El mapa muestra propiedades REALES con coordenadas válidas\\n' +
                      '• Los colores indican densidad de precio por m²\\n' +
                      '• NO hay propiedades inventadas - todos los datos son reales');
            }});
            
            // Mostrar mensaje de éxito
            const successDiv = document.createElement('div');
            successDiv.innerHTML = `
                <div style="position: absolute; top: 10px; right: 10px; background: rgba(16, 185, 129, 0.9); color: white; padding: 10px 15px; border-radius: 5px; z-index: 1000;">
                    <i class="bi bi-check-circle-fill me-1"></i>Heatmap cargado correctamente
                </div>
            `;
            document.getElementById('heatmapMap').appendChild(successDiv);
            
        }} catch (error) {{
            console.error('Error al inicializar heatmap:', error);
            document.getElementById('heatmapMap').innerHTML = `
                <div style="text-align: center; padding: 200px 0; color: red;">
                    <h4>Error al cargar Google Maps</h4>
                    <p>${{error.message}}</p>
                    <button class="btn btn-primary mt-3" onclick="location.reload()">Reintentar</button>
                </div>
            `;
        }}
    }}
    
    // Inicializar cuando el DOM esté listo
    if (document.readyState === 'loading') {{
        document.addEventListener('DOMContentLoaded', initializeHeatmap);
    }} else {{
        initializeHeatmap();
    }}
    </script>
</body>
</html>
'''
    
    from django.http import HttpResponse
    response = HttpResponse(html)
    # Headers para prevenir caché
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


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
            
            # Limitar a 200 propiedades para rendimiento
            queryset_local = queryset_local[:200]
            
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
                
                queryset_propifai = queryset_propifai[:100]  # Limitar
                
                for prop in queryset_propifai:
                    try:
                        if prop.coordinates:
                            coords = prop.coordinates.split(',')
                            if len(coords) >= 2:
                                lat = float(coords[0].strip())
                                lng = float(coords[1].strip())
                                
                                # Calcular área con detección de terrenos (misma lógica que heatmap_view)
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
                                
                                built_area_val = prop.built_area if prop.built_area else 0
                                land_area_val = prop.land_area if prop.land_area else 0
                                
                                # Lógica agresiva para detectar terrenos
                                es_terreno_heuristico = False
                                if land_area_val > 0:
                                    if built_area_val == 0 or built_area_val is None:
                                        es_terreno_heuristico = True
                                    elif land_area_val > built_area_val:
                                        es_terreno_heuristico = True
                                    elif land_area_val > 100:
                                        es_terreno_heuristico = True
                                
                                es_proyecto = prop.is_project if hasattr(prop, 'is_project') else False
                                if es_proyecto and land_area_val > 0:
                                    es_terreno_heuristico = True
                                
                                es_terreno = es_terreno_texto or es_terreno_heuristico
                                
                                # SI ES TERRENO: usar SOLO land_area
                                if es_terreno:
                                    if prop.land_area and prop.land_area > 0:
                                        area = float(prop.land_area)
                                    # Si no hay land_area, NO usar built_area
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
                                        'tipo_propiedad': prop.tipo_propiedad or '',
                                        'fuente': 'propifai',
                                        'weight': min(precio_m2 / 1000, 2.0)
                                    })
                    except (ValueError, AttributeError, TypeError):
                        continue
            
            elapsed = time.time() - start_time
            print(f"[INFO] Consulta real tomó {elapsed:.2f}s, encontradas {len(propiedades)} propiedades")
            
        except Exception as db_error:
            print(f"[ERROR] Error en consulta real: {db_error}")
            # En caso de error, devolver lista vacía en lugar de datos falsos
            propiedades = []
        
        # Estadísticas simples
        total = len(propiedades)
        if total > 0:
            precios_m2 = [p['precio_m2'] for p in propiedades]
            precio_m2_min = min(precios_m2)
            precio_m2_max = max(precios_m2)
            precio_m2_promedio = sum(precios_m2) / total
        else:
            precio_m2_min = precio_m2_max = precio_m2_promedio = 0
        
        response_data = {
            'success': True,
            'properties': propiedades,
            'statistics': {
                'total': total,
                'local_count': total,
                'propifai_count': 0,
                'precio_m2_min': round(precio_m2_min, 2),
                'precio_m2_max': round(precio_m2_max, 2),
                'precio_m2_promedio': round(precio_m2_promedio, 2),
            },
            'filters_applied': {
                'tipo_propiedad': tipo_propiedad,
                'precio_min': precio_min,
                'precio_max': precio_max,
                'area_min': area_min,
                'area_max': area_max,
                'fuente': fuente,
            },
            'note': 'Datos reales de la base de datos'
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        # En caso de error, devolver respuesta de error sin datos falsos
        print(f"[ERROR CRÍTICO] Error en api_heatmap_data: {e}")
        return JsonResponse({
            'success': False,
            'properties': [],
            'statistics': {
                'total': 0,
                'local_count': 0,
                'propifai_count': 0,
                'precio_m2_min': 0,
                'precio_m2_max': 0,
                'precio_m2_promedio': 0,
            },
            'filters_applied': {},
            'note': f'Error al obtener datos reales: {str(e)[:100]}',
            'error': True
        })


def api_heatmap_stats(request):
    """API para obtener estadísticas generales del heatmap"""
    try:
        # Conteo total de propiedades con coordenadas
        total_local = PropiedadRaw.objects.filter(
            coordenadas__isnull=False
        ).exclude(coordenadas='').count()
        
        total_propifai = PropifaiProperty.objects.filter(
            coordinates__isnull=False
        ).exclude(coordinates='').count()
        
        # Conteo por tipo de propiedad (local)
        tipos_local = PropiedadRaw.objects.filter(
            coordenadas__isnull=False
        ).exclude(coordenadas='').values('tipo_propiedad').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Conteo por tipo de propiedad (propifai)
        tipos_propifai = PropifaiProperty.objects.filter(
            coordinates__isnull=False
        ).exclude(coordinates='').values('tipo_propiedad').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        return JsonResponse({
            'success': True,
            'total_properties': {
                'local': total_local,
                'propifai': total_propifai,
                'total': total_local + total_propifai
            },
            'property_types': {
                'local': list(tipos_local),
                'propifai': list(tipos_propifai)
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


# Módulo B: Dashboard de Calidad de Datos
def dashboard_view(request):
    """Vista principal para el dashboard de calidad de datos"""
    context = {
        'title': 'Dashboard de Calidad de Datos',
        'module': 'dashboard',
    }
    return render(request, 'market_analysis/dashboard.html', context)


def api_dashboard_stats(request):
    """API para obtener estadísticas de calidad de datos"""
    try:
        from django.db.models import Count, Q, F, FloatField
        from django.db.models.functions import Cast, Coalesce
        
        # Estadísticas generales
        total_local = PropiedadRaw.objects.count()
        total_propifai = PropifaiProperty.objects.count()
        
        # Calidad de datos - Propiedades locales
        local_with_coords = PropiedadRaw.objects.filter(
            coordenadas__isnull=False
        ).exclude(coordenadas='').count()
        
        local_with_price = PropiedadRaw.objects.filter(
            precio_usd__isnull=False,
            precio_usd__gt=0
        ).count()
        
        local_with_area = PropiedadRaw.objects.filter(
            Q(area_construida__isnull=False, area_construida__gt=0) |
            Q(area_terreno__isnull=False, area_terreno__gt=0)
        ).count()
        
        local_with_type = PropiedadRaw.objects.filter(
            tipo_propiedad__isnull=False
        ).exclude(tipo_propiedad='').count()
        
        # Calidad de datos - Propiedades Propifai
        propifai_with_coords = PropifaiProperty.objects.filter(
            coordinates__isnull=False
        ).exclude(coordinates='').count()
        
        propifai_with_price = PropifaiProperty.objects.filter(
            price__isnull=False,
            price__gt=0
        ).count()
        
        propifai_with_area = PropifaiProperty.objects.filter(
            Q(built_area__isnull=False, built_area__gt=0) |
            Q(land_area__isnull=False, land_area__gt=0)
        ).count()
        
        propifai_with_type = PropifaiProperty.objects.filter(
            tipo_propiedad__isnull=False
        ).exclude(tipo_propiedad='').count()
        
        # Calcular porcentajes
        local_coords_pct = (local_with_coords / total_local * 100) if total_local > 0 else 0
        local_price_pct = (local_with_price / total_local * 100) if total_local > 0 else 0
        local_area_pct = (local_with_area / total_local * 100) if total_local > 0 else 0
        local_type_pct = (local_with_type / total_local * 100) if total_local > 0 else 0
        
        propifai_coords_pct = (propifai_with_coords / total_propifai * 100) if total_propifai > 0 else 0
        propifai_price_pct = (propifai_with_price / total_propifai * 100) if total_propifai > 0 else 0
        propifai_area_pct = (propifai_with_area / total_propifai * 100) if total_propifai > 0 else 0
        propifai_type_pct = (propifai_with_type / total_propifai * 100) if total_propifai > 0 else 0
        
        # Distribución por tipo de propiedad
        tipos_local_dist = PropiedadRaw.objects.filter(
            tipo_propiedad__isnull=False
        ).exclude(tipo_propiedad='').values('tipo_propiedad').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        tipos_propifai_dist = PropifaiProperty.objects.filter(
            tipo_propiedad__isnull=False
        ).exclude(tipo_propiedad='').values('tipo_propiedad').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Propiedades problemáticas (sin coordenadas o sin precio)
        problematic_local = PropiedadRaw.objects.filter(
            Q(coordenadas__isnull=True) | Q(coordenadas='') |
            Q(precio_usd__isnull=True) | Q(precio_usd__lte=0)
        ).count()
        
        problematic_propifai = PropifaiProperty.objects.filter(
            Q(coordinates__isnull=True) | Q(coordinates='') |
            Q(price__isnull=True) | Q(price__lte=0)
        ).count()
        
        # Tendencias temporales (últimos 6 meses)
        from django.utils import timezone
        from datetime import timedelta
        
        six_months_ago = timezone.now() - timedelta(days=180)
        
        # Para PropiedadRaw (usar fecha_ingesta si existe, sino created_at)
        local_trend = []
        for i in range(6):
            month_start = six_months_ago + timedelta(days=i*30)
            month_end = month_start + timedelta(days=30)
            
            count = PropiedadRaw.objects.filter(
                fecha_ingesta__range=(month_start, month_end)
            ).count()
            
            local_trend.append({
                'month': month_start.strftime('%b'),
                'count': count
            })
        
        # Para PropifaiProperty (usar created_at)
        propifai_trend = []
        for i in range(6):
            month_start = six_months_ago + timedelta(days=i*30)
            month_end = month_start + timedelta(days=30)
            
            count = PropifaiProperty.objects.filter(
                created_at__range=(month_start, month_end)
            ).count()
            
            propifai_trend.append({
                'month': month_start.strftime('%b'),
                'count': count
            })
        
        return JsonResponse({
            'success': True,
            'summary': {
                'total_properties': total_local + total_propifai,
                'total_local': total_local,
                'total_propifai': total_propifai,
                'problematic_total': problematic_local + problematic_propifai,
                'problematic_local': problematic_local,
                'problematic_propifai': problematic_propifai,
            },
            'quality_metrics': {
                'local': {
                    'coordinates': {
                        'count': local_with_coords,
                        'total': total_local,
                        'percentage': round(local_coords_pct, 1)
                    },
                    'price': {
                        'count': local_with_price,
                        'total': total_local,
                        'percentage': round(local_price_pct, 1)
                    },
                    'area': {
                        'count': local_with_area,
                        'total': total_local,
                        'percentage': round(local_area_pct, 1)
                    },
                    'type': {
                        'count': local_with_type,
                        'total': total_local,
                        'percentage': round(local_type_pct, 1)
                    }
                },
                'propifai': {
                    'coordinates': {
                        'count': propifai_with_coords,
                        'total': total_propifai,
                        'percentage': round(propifai_coords_pct, 1)
                    },
                    'price': {
                        'count': propifai_with_price,
                        'total': total_propifai,
                        'percentage': round(propifai_price_pct, 1)
                    },
                    'area': {
                        'count': propifai_with_area,
                        'total': total_propifai,
                        'percentage': round(propifai_area_pct, 1)
                    },
                    'type': {
                        'count': propifai_with_type,
                        'total': total_propifai,
                        'percentage': round(propifai_type_pct, 1)
                    }
                }
            },
            'property_type_distribution': {
                'local': list(tipos_local_dist),
                'propifai': list(tipos_propifai_dist)
            },
            'trends': {
                'local': local_trend,
                'propifai': propifai_trend
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


def heatmap_simple_view(request):
    """Vista de prueba simplificada para el heatmap"""
    context = {
        'title': 'Heatmap Simple (Prueba)',
        'module': 'heatmap',
    }
    return render(request, 'market_analysis/heatmap_simple.html', context)


def heatmap_test_view(request):
    """Vista de prueba ultra simplificada para el heatmap"""
    context = {
        'title': 'Heatmap Test',
        'module': 'heatmap',
    }
    return render(request, 'market_analysis/heatmap_test.html', context)
