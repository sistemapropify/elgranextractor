// Inicialización del heatmap - Cargado después de Google Maps
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM cargado, verificando Google Maps...');
    
    // Verificar que Google Maps esté cargado
    if (typeof google !== 'undefined' && typeof google.maps !== 'undefined') {
        console.log('Google Maps cargado correctamente, inicializando mapa...');
        initHeatmapMap();
    } else {
        console.error('Google Maps no se cargó correctamente');
        console.log('Tipo de google:', typeof google);
        console.log('Tipo de google.maps:', typeof google.maps);
        
        // Mostrar mensaje de error en la página
        const mapContainer = document.getElementById('heatmapMap');
        if (mapContainer) {
            mapContainer.innerHTML = 
                '<div class="alert alert-danger m-3">' +
                '<h5>Error al cargar Google Maps</h5>' +
                '<p>No se pudo cargar la API de Google Maps. Posibles causas:</p>' +
                '<ul>' +
                '<li>La clave API no es válida o ha expirado</li>' +
                '<li>Problemas de conexión a internet</li>' +
                '<li>La biblioteca de visualización no está disponible</li>' +
                '</ul>' +
                '<p>Por favor, verifica la consola del navegador para más detalles.</p>' +
                '</div>';
        }
    }
    
    // Configurar eventos de filtros
    document.getElementById('filterTipoPropiedad')?.addEventListener('change', function() {
        currentFilters.tipo_propiedad = this.value;
        loadHeatmapData();
    });
    
    document.getElementById('filterPrecioMin')?.addEventListener('input', function() {
        currentFilters.precio_min = this.value;
        loadHeatmapData();
    });
    
    document.getElementById('filterPrecioMax')?.addEventListener('input', function() {
        currentFilters.precio_max = this.value;
        loadHeatmapData();
    });
    
    document.getElementById('filterAreaMin')?.addEventListener('input', function() {
        currentFilters.area_min = this.value;
        loadHeatmapData();
    });
    
    document.getElementById('filterAreaMax')?.addEventListener('input', function() {
        currentFilters.area_max = this.value;
        loadHeatmapData();
    });
    
    document.getElementById('filterFuente')?.addEventListener('change', function() {
        currentFilters.fuente = this.value;
        loadHeatmapData();
    });
    
    // Botón de actualizar
    document.getElementById('btnRefresh')?.addEventListener('click', function() {
        loadHeatmapData();
    });
    
    // Modal de ayuda
    document.getElementById('btnHelp')?.addEventListener('click', function() {
        new bootstrap.Modal(document.getElementById('helpModal')).show();
    });
    
    console.log('Eventos configurados correctamente');
});