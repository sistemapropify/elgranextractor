// Módulo Heatmap - JavaScript para visualización de precio por m²

// Variables globales
let heatmapMap;
let heatmapLayer = null;
let markersLayer = [];
let currentProperties = [];
let currentFilters = {
    tipo_propiedad: '',
    precio_min: '',
    precio_max: '',
    area_min: '',
    area_max: '',
    fuente: 'todas'
};

// Inicializar mapa de heatmap
function initHeatmapMap() {
    const defaultCenter = { lat: -16.4090, lng: -71.5375 }; // Arequipa, Perú
    
    heatmapMap = new google.maps.Map(document.getElementById('heatmapMap'), {
        center: defaultCenter,
        zoom: 13,
        scrollwheel: true,
        gestureHandling: 'greedy',
        styles: [
            {
                featureType: "poi",
                elementType: "labels",
                stylers: [{ visibility: "off" }]
            }
        ]
    });
    
    // Cargar datos iniciales
    loadHeatmapData();
    
    // Configurar eventos
    setupEventListeners();
}

// Cargar datos del heatmap desde la API
async function loadHeatmapData() {
    try {
        showLoading(true);
        
        // Construir URL con filtros
        const params = new URLSearchParams();
        if (currentFilters.tipo_propiedad) params.append('tipo_propiedad', currentFilters.tipo_propiedad);
        if (currentFilters.precio_min) params.append('precio_min', currentFilters.precio_min);
        if (currentFilters.precio_max) params.append('precio_max', currentFilters.precio_max);
        if (currentFilters.area_min) params.append('area_min', currentFilters.area_min);
        if (currentFilters.area_max) params.append('area_max', currentFilters.area_max);
        if (currentFilters.fuente) params.append('fuente', currentFilters.fuente);
        
        const response = await fetch(`/market-analysis/api/heatmap-data/?${params.toString()}`);
        const data = await response.json();
        
        if (data.success) {
            currentProperties = data.properties;
            updateHeatmapLayer();
            updateStatistics(data.statistics);
            updatePropertiesList(data.properties);
            updateMapPropertyCount(data.properties.length);
        } else {
            showError('Error al cargar datos: ' + (data.error || 'Desconocido'));
        }
    } catch (error) {
        showError('Error de conexión: ' + error.message);
    } finally {
        showLoading(false);
    }
}

// Actualizar capa de heatmap
function updateHeatmapLayer() {
    // Eliminar capa anterior si existe
    if (heatmapLayer) {
        heatmapLayer.setMap(null);
    }
    
    // Eliminar marcadores anteriores
    clearMarkers();
    
    // Verificar si el heatmap está activado
    const heatmapEnabled = document.getElementById('toggleHeatmap').checked;
    const markersEnabled = document.getElementById('toggleMarkers').checked;
    
    // Crear heatmap si está activado
    if (heatmapEnabled && currentProperties.length > 0) {
        const heatmapData = currentProperties.map(prop => {
            return {
                location: new google.maps.LatLng(prop.lat, prop.lng),
                weight: prop.weight || 0.5
            };
        });
        
        heatmapLayer = new google.maps.visualization.HeatmapLayer({
            data: heatmapData,
            map: heatmapMap,
            radius: 30,
            opacity: parseFloat(document.getElementById('heatmapOpacity').value),
            gradient: [
                'rgba(0, 255, 0, 0)',
                'rgba(0, 255, 0, 1)',
                'rgba(255, 255, 0, 1)',
                'rgba(255, 0, 0, 1)'
            ]
        });
    }
    
    // Crear marcadores si están activados
    if (markersEnabled && currentProperties.length > 0) {
        // Limitar a 100 marcadores para rendimiento
        const limitedProperties = currentProperties.slice(0, 100);
        
        limitedProperties.forEach(prop => {
            const markerColor = prop.fuente === 'local' ? '#0d6efd' : '#6f42c1';
            
            const marker = new google.maps.Marker({
                position: { lat: prop.lat, lng: prop.lng },
                map: heatmapMap,
                title: `${prop.tipo_propiedad} - ${prop.precio_m2 ? prop.precio_m2.toFixed(2) + ' USD/m²' : 'Sin precio'}`,
                icon: {
                    path: google.maps.SymbolPath.CIRCLE,
                    fillColor: markerColor,
                    fillOpacity: 0.7,
                    strokeColor: '#ffffff',
                    strokeWeight: 1,
                    scale: 6
                }
            });
            
            // InfoWindow
            const infoWindow = new google.maps.InfoWindow({
                content: `
                    <div class="map-info-window">
                        <div style="border-left: 4px solid ${markerColor}; padding-left: 8px;">
                            <h6 style="margin: 0 0 5px 0;">${prop.tipo_propiedad || 'Propiedad'}</h6>
                            <div style="font-size: 12px; color: #666; margin-bottom: 8px;">
                                Fuente: <strong>${prop.fuente === 'local' ? 'Local' : 'Propifai'}</strong>
                            </div>
                            <p class="mb-1"><strong>Precio/m²: $${prop.precio_m2 ? prop.precio_m2.toFixed(2) : 'N/A'}</strong></p>
                            <p class="mb-1">Precio total: $${prop.precio_usd ? prop.precio_usd.toLocaleString() : 'N/A'}</p>
                            <p class="mb-1">Área: ${prop.area ? prop.area.toFixed(0) + ' m²' : 'N/A'}</p>
                            <p class="mb-1 small text-muted">${prop.fuente === 'local' ? 'Propiedad local' : 'Propiedad Propifai'}</p>
                        </div>
                    </div>
                `
            });
            
            marker.addListener('click', () => {
                infoWindow.open(heatmapMap, marker);
            });
            
            markersLayer.push({ marker, infoWindow });
        });
    }
    
    // Actualizar leyenda
    updateLegend();
}

// Limpiar marcadores
function clearMarkers() {
    markersLayer.forEach(item => {
        item.marker.setMap(null);
        item.infoWindow.close();
    });
    markersLayer = [];
}

// Actualizar estadísticas en la UI
function updateStatistics(stats) {
    document.getElementById('statTotal').textContent = stats.total || 0;
    document.getElementById('statAvgPriceM2').textContent = stats.precio_m2_promedio ? stats.precio_m2_promedio.toFixed(2) : '0';
    document.getElementById('statMinPriceM2').textContent = stats.precio_m2_min ? stats.precio_m2_min.toFixed(2) : '0';
    document.getElementById('statMaxPriceM2').textContent = stats.precio_m2_max ? stats.precio_m2_max.toFixed(2) : '0';
    document.getElementById('statLocalCount').textContent = stats.local_count || 0;
    document.getElementById('statPropifaiCount').textContent = stats.propifai_count || 0;
}

// Actualizar lista de propiedades
function updatePropertiesList(properties) {
    const container = document.getElementById('propertiesList');
    
    if (properties.length === 0) {
        container.innerHTML = `
            <div class="text-center py-5 text-muted">
                <i class="bi bi-thermometer display-6 mb-3"></i>
                <p class="mb-0">No hay propiedades</p>
                <small>Intenta con otros filtros</small>
            </div>
        `;
        return;
    }
    
    // Ordenar por precio/m² descendente por defecto
    const sortedProperties = [...properties].sort((a, b) => (b.precio_m2 || 0) - (a.precio_m2 || 0));
    
    // Tomar las top 10
    const topProperties = sortedProperties.slice(0, 10);
    
    let html = '';
    topProperties.forEach((prop, index) => {
        const badgeColor = prop.fuente === 'local' ? 'bg-primary' : 'bg-purple';
        const formattedPriceM2 = prop.precio_m2 ? `$${prop.precio_m2.toFixed(2)}` : 'N/A';
        const formattedPrice = prop.precio_usd ? `$${prop.precio_usd.toLocaleString()}` : 'N/A';
        const formattedArea = prop.area ? `${prop.area.toFixed(0)} m²` : 'N/A';
        
        html += `
            <div class="border-bottom p-3">
                <div class="d-flex justify-content-between align-items-start mb-2">
                    <div>
                        <span class="badge ${badgeColor} me-2">${prop.fuente === 'local' ? 'L' : 'P'}</span>
                        <strong>${prop.tipo_propiedad || 'Propiedad'}</strong>
                    </div>
                    <div class="text-end">
                        <div class="fw-bold text-success">${formattedPriceM2}</div>
                        <small class="text-muted">USD/m²</small>
                    </div>
                </div>
                <div class="small text-muted">
                    <div class="d-flex justify-content-between">
                        <span>Precio:</span>
                        <span>${formattedPrice}</span>
                    </div>
                    <div class="d-flex justify-content-between">
                        <span>Área:</span>
                        <span>${formattedArea}</span>
                    </div>
                </div>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

// Actualizar contador de propiedades en el mapa
function updateMapPropertyCount(count) {
    document.getElementById('mapPropertyCount').textContent = count;
}

// Actualizar leyenda
function updateLegend() {
    if (currentProperties.length === 0) {
        document.getElementById('legendMin').textContent = 'Bajo';
        document.getElementById('legendMid').textContent = 'Medio';
        document.getElementById('legendMax').textContent = 'Alto';
        return;
    }
    
    // Calcular rangos de precio/m²
    const prices = currentProperties.map(p => p.precio_m2).filter(p => p > 0);
    if (prices.length > 0) {
        const minPrice = Math.min(...prices);
        const maxPrice = Math.max(...prices);
        const midPrice = (minPrice + maxPrice) / 2;
        
        document.getElementById('legendMin').textContent = `$${minPrice.toFixed(0)}`;
        document.getElementById('legendMid').textContent = `$${midPrice.toFixed(0)}`;
        document.getElementById('legendMax').textContent = `$${maxPrice.toFixed(0)}`;
    }
}

// Configurar event listeners
function setupEventListeners() {
    // Botón de aplicar filtros
    document.getElementById('btnAplicarFiltros').addEventListener('click', applyFilters);
    
    // Botón de refrescar
    document.getElementById('btnRefresh').addEventListener('click', () => {
        loadHeatmapData();
    });
    
    // Botón de ayuda
    document.getElementById('btnHelp').addEventListener('click', () => {
        new bootstrap.Modal(document.getElementById('helpModal')).show();
    });
    
    // Toggle heatmap
    document.getElementById('toggleHeatmap').addEventListener('change', function() {
        document.getElementById('heatmapStatus').textContent = this.checked ? 'ON' : 'OFF';
        document.getElementById('heatmapStatus').className = this.checked ? 'badge bg-success' : 'badge bg-secondary';
        updateHeatmapLayer();
    });
    
    // Toggle marcadores
    document.getElementById('toggleMarkers').addEventListener('change', function() {
        document.getElementById('markersStatus').textContent = this.checked ? 'ON' : 'OFF';
        document.getElementById('markersStatus').className = this.checked ? 'badge bg-success' : 'badge bg-secondary';
        updateHeatmapLayer();
    });
    
    // Control de opacidad
    document.getElementById('heatmapOpacity').addEventListener('input', function() {
        const opacity = parseFloat(this.value);
        document.getElementById('opacityValue').textContent = Math.round(opacity * 100) + '%';
        
        if (heatmapLayer) {
            heatmapLayer.set('opacity', opacity);
        }
    });
    
    // Ordenar lista de propiedades
    document.querySelectorAll('[data-sort]').forEach(item => {
        item.addEventListener('click', function(e) {
            e.preventDefault();
            const sortType = this.getAttribute('data-sort');
            sortPropertiesList(sortType);
        });
    });
    
    // Enter en campos de filtro
    ['filterPrecioMin', 'filterPrecioMax', 'filterAreaMin', 'filterAreaMax'].forEach(id => {
        document.getElementById(id).addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                applyFilters();
            }
        });
    });
}

// Aplicar filtros
function applyFilters() {
    currentFilters = {
        tipo_propiedad: document.getElementById('filterTipoPropiedad').value,
        precio_min: document.getElementById('filterPrecioMin').value,
        precio_max: document.getElementById('filterPrecioMax').value,
        area_min: document.getElementById('filterAreaMin').value,
        area_max: document.getElementById('filterAreaMax').value,
        fuente: document.getElementById('filterFuente').value
    };
    
    loadHeatmapData();
}

// Ordenar lista de propiedades
function sortPropertiesList(sortType) {
    let sortedProperties = [...currentProperties];
    
    switch (sortType) {
        case 'precio_m2_desc':
            sortedProperties.sort((a, b) => (b.precio_m2 || 0) - (a.precio_m2 || 0));
            break;
        case 'precio_m2_asc':
            sortedProperties.sort((a, b) => (a.precio_m2 || 0) - (b.precio_m2 || 0));
            break;
        case 'precio_desc':
            sortedProperties.sort((a, b) => (b.precio_usd || 0) - (a.precio_usd || 0));
            break;
        case 'area_desc':
            sortedProperties.sort((a, b) => (b.area || 0) - (a.area || 0));
            break;
    }
    
    updatePropertiesList(sortedProperties);
}

// Mostrar/ocultar loading
function showLoading(show) {
    const refreshBtn = document.getElementById('btnRefresh');
    if (show) {
        refreshBtn.innerHTML = '<i class="bi bi-arrow-clockwise me-1"></i>Cargando...';
        refreshBtn.disabled = true;
    } else {
        refreshBtn.innerHTML = '<i class="bi bi-arrow-clockwise me-1"></i>Actualizar';
        refreshBtn.disabled = false;
    }
}

// Mostrar error
function showError(message) {
    // Podríamos implementar un sistema de notificaciones más sofisticado
    console.error('Heatmap Error:', message);
    alert('Error: ' + message);
}

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', function() {
    // El mapa se inicializará cuando se cargue la API de Google Maps
    // Esto se manejará en el template principal
});

// Exportar para uso global
window.initHeatmapMap = initHeatmapMap;